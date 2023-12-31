# http://api.ap.org/media/v/docs/Feed_Examples.htm
# http://api.ap.org/media/v/docs/Getting_Content_Updates.htm
import json
import arrow
from http import HTTPStatus
from typing import Optional
from sqlite3 import connect

import requests
from decouple import config
from jmespath import search
from ratelimit import limits, sleep_and_retry
from xmltodict import parse

from apps.associated_press.converter import APPhotoConverter, APStoryConverter
from utils import inventory
from utils.constants import (
    AP_ASSOCIATIONS_JMESPATH_STR,
    AP_RESULTS_JMESPATH_STR,
    CIRCULATION_URL,
    DRAFT_API_URL,
    OPERATIONS_URL,
    PHOTO_API_URL,
)
from utils.exceptions import IncompleteWirePhotoException, IncompleteWireStoryException, WireExistsInArcException
from utils.logger import get_logger

logger = get_logger()


def fetch_feed(next_page: Optional[str] = None):
    url = "https://api.ap.org/media/v/content/feed"
    params = {"apikey": config("AP_API_KEY")}
    q = config("AP_QUERY", None)
    items = None
    if next_page:
        url = next_page
    elif q:
        params["q"] = q
        logger.info("Associated Press Query Param", extra={"q": q})
    res = requests.get(url, params=params)
    if res.ok:
        data = res.json()
        next_page = search("data.next_page", data) or None
        previous_sequence = search("params.seq", data) or None
        sequence = next_page.split("seq=")[-1] if next_page else None

        # initial intent was to log the sequence ids in the db in case was  useful info when tracing back this task's runs. decided not to log in db.
        logger.info(
            f"{res.status_code} {url}",
            extra={
                "previous_sequence": previous_sequence,
                "sequence": sequence,
                "next_page": next_page,
            },
        )

        # select relevant data from the results
        items = search(AP_RESULTS_JMESPATH_STR, data)

        # when using next_page variable, the request might bring back a single item rather than an array of items
        # single item result happens when a story has photo "associations" and you're fetching an item of photo data
        # requires a different structure to the jmespath search string
        if items is None:
            # do not process ap images that incur cost
            priced = search("data.item.renditions.main.priced || data.item.renditions.main.pricetag", data)
            if priced in ["Unlimited", False, None, "false"]:
                items = search(AP_ASSOCIATIONS_JMESPATH_STR, data)
            else:
                logger.warning(
                    "Picture excluded because it would incur cost",
                    extra={"source_id": data["data"]["item"]["altids"]["itemid"], "priced": priced},
                )
    else:
        logger.error(f"{res.status_code} {url}")
        next_page = sequence = previous_sequence = None
    return items


def fetch_story_item(url: str, item: dict):
    # AP story text is in XML. The converter will parse the XML to into Ans content elements.
    # Also Convert the XML to JSON and add to source data. Will use this to compute the sha1.
    params = {"apikey": config("AP_API_KEY")}
    res = requests.get(url, params=params)
    if res.ok:
        data = parse(res.content).get("nitf", {})
        data = json.loads(json.dumps(data))
        item["content_json"] = data
        converter = APStoryConverter(
            item,
            org_name=config("ARC_ORG_ID"),
            website=config("ARC_ORG_WEBSITE"),
            section=config("ARC_WEBSITE_SECTION"),
            story_data=res.content,
        )
        return converter


def fetch_photo_item(item: dict):
    # AP Photos don't need more info than what comes via the feed/query initial request
    # to be parsed, so not querying the full photo url for additional data
    converter = APPhotoConverter(item, org_name=config("ARC_ORG_ID"))
    return converter


def bearer_token():
    if "sandbox." in config("ARC_ORG_ID"):
        token = config("ARC_TOKEN_SANDBOX")
    else:
        token = config("ARC_TOKEN_PRODUCTION")

    # Draft API requests require Arc-Priority header to route traffic to appropriate lane
    # request header Arc-Priority: ingestion ... events routed with lower priority.
    #    stories do not show up in the Websked Arc application.
    #    large volumes can be ingested with the ingestion priority safely.
    # request header Arc-Priority: standard ...  events routed with higher priority.
    #    stories do show up in Websked.
    #    take extra precautions with standard priority to not abuse with heavy and frequent traffic,
    #    or the traffic will cause instability and may be subjected to additional throttling by Arc
    priority_header = "ingestion"

    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Arc-Priority": priority_header}


@sleep_and_retry
@limits(calls=2, period=60)
def process_wire_story(converter: APStoryConverter, count: str, conn: connect):
    # apply converter to transform source into ans, send ans into draft api/content api/composer, inventory on success
    logger.info(f"{count} {converter}")
    ans = None
    # a circulation is not required, but circulating wires to a section makes it easier to filter for wires in composer
    # without circulating to a section, you can still filter in Composer for the only stories belonging to the wire
    # by using the distributor values. this POC will demonstrate sending a simple circulation to a single section.
    circulation = None
    # stories ingested by this POC will be unpublished, as is best practice for the ingestion of inbound wires.
    # a content operation is not required, but this POC will demonstrate how to send a future publishing operation
    # the content operation we are sending will delete the wire content once it has aged and become stale
    operation = None
    org = config("ARC_ORG_ID")
    logger.info("GENERATE ANS & CIRCULATION & OPERATION")
    try:
        ans = converter.convert_ans()
        circulation = converter.get_circulation()
        operation = converter.get_scheduled_delete_operation()
        # this POC will enforce circulations and operations data in addition to the ans
        if ans is None or circulation is None or operation is None:
            raise IncompleteWireStoryException

        logger.info("CHECK INVENTORY - DOES SAME SHA1 EXIST?")
        sha1 = inventory.select_inventory_by_sha1(conn, ans.get("additional_properties").get("sha1"))
        if sha1:
            raise WireExistsInArcException

    except Exception as e:
        logger.error(e, extra={"ans": ans is not None, "circulation": circulation is not None, "operation": operation is not None})
        return str(e)

    logger.info("SEND ANS TO DRAFT API")
    extra = {
        "arc_id": ans.get("_id"),
        "source_id": ans.get("source").get("source_id"),
        "headline": ans.get("headlines").get("basic"),
    }
    try:
        res = requests.post(DRAFT_API_URL.format(org=org), json=ans, headers=bearer_token())
        res.raise_for_status()
    except Exception as e:
        # POSTing to an existing arc id in Draft API causes an error, you have to PUT instead.
        if "res" in locals():
            res_error_msg = res.json().get("error_message")
            logger.warning(res_error_msg, extra=extra)

        # Draft API throws specific exception if you POST to a story that already exists: "{Arc Id} is already in-use"
        if "res" in locals() and "is already in-use" in res_error_msg:

            try:
                logger.info("UPDATE DRAFT API")
                # GET current revision of the ans
                url = DRAFT_API_URL.format(org=org) + f"/{ans.get('_id')}"
                res = requests.get(url, headers=bearer_token())
                res.raise_for_status()
                data = res.json()
                revision_id = data.get("draft_revision_id")
                # PUT ans to the revision ID
                params = {"id": revision_id, "document_id": ans.get("_id"), "ans": ans}
                res = requests.put(f"{url}/revision/draft", json=params, headers=bearer_token())
                res.raise_for_status()
            except Exception as ex:
                # If still errors, report on the error
                logger.error(ex, extra=extra)
                if "res" in locals():
                    logger.error(res.json().get("error_message"), extra=extra)
                return str(ex)

        else:
            logger.error(e, extra=extra)
            if "res" in locals():
                logger.error(res.json().get("error_message"), extra=extra)
            return str(e)

    logger.info("SEND OPERATION")
    try:
        res = requests.put(OPERATIONS_URL.format(org=org), json=operation, headers=bearer_token())
        res.raise_for_status()
    except Exception as e:
        logger.error(e, extra=extra)
        if "res" in locals():
            logger.error(res.json().get("error"), extra=extra)
        return str(e)

    logger.info("SEND CIRCULATION")
    try:
        res = requests.put(
            CIRCULATION_URL.format(org=org, arc_id=ans.get("_id"), website=config("ARC_ORG_WEBSITE")),
            json=circulation,
            headers=bearer_token(),
        )
        res.raise_for_status()
    except Exception as e:
        logger.error(e, extra=extra)
        if "res" in locals():
            logger.error(res.json().get("error_message"), extra=extra)
        return str(e)

    logger.info("SAVE INVENTORY")
    inv_item = (
        ans.get("source").get("source_id"),
        ans.get("_id"),
        ans.get("additional_properties").get("ap_item_url"),
        ans.get("type"),
        ans.get("additional_properties").get("sha1"),
        arrow.utcnow().format("YYYY-MM-DD HH:MM:SS.SSS"),
    )
    inventory.create_inventory(conn, inv_item)
    return HTTPStatus.CREATED


@sleep_and_retry
@limits(calls=5, period=60)
def process_wire_photo(converter: APPhotoConverter, count: str, conn: connect):
    # apply converter to transform source into ans, send ans into photo center api/photo center, inventory on success
    logger.info(f"{count} {converter}")
    ans = None
    sha1 = None
    logger.info("GENERATE ANS")
    try:
        ans = converter.convert_ans()
        if ans is None:
            raise IncompleteWirePhotoException

        logger.info("CHECK INVENTORY - DOES SAME SHA1 EXIST?")
        sha1 = inventory.select_inventory_by_sha1(conn, ans.get("additional_properties").get("sha1"))
        if sha1:
            raise WireExistsInArcException

    except Exception as e:
        logger.error(e, extra={"ans": ans is not None, "sha1": sha1})
        return str(e)

    logger.info("SEND ANS TO PHOTO API")
    extra = {
        "arc_id": ans.get("_id"),
        "source_id": ans.get("source").get("source_id"),
        "caption": ans.get("caption"),
    }

    try:
        ans["additional_properties"]["originalUrl"] += f"&apikey={config('AP_API_KEY')}"
        res = requests.post(
            PHOTO_API_URL.format(org=config("ARC_ORG_ID"), arc_id=ans.get("_id")), json=ans, headers=bearer_token()
        )
        res.raise_for_status()

    except Exception as e:
        # POSTing to an existing arc id in Photo Center causes an error, you have to PUT instead.
        logger.warning(e, extra=extra)

        if "409 Client Error: Conflict" in str(e):
            try:
                logger.info("UPDATE PHOTO API")
                url = PHOTO_API_URL.format(org=config("ARC_ORG_ID"), arc_id=ans.get("_id"))
                # GET current revision of the ans from photo center
                res = requests.get(url, headers=bearer_token())
                res.raise_for_status()
                data = res.json()
                # update the photo center ans with local changes to avoid 500 errors from the PUT
                # this is a peculiarity of photo center's api when doing a PUT
                # do not update additional_properties.original_url; the image binary cannot be updated once imported
                data["additional_properties"]["expiration_date"] = ans["additional_properties"]["expiration_date"]
                data["additional_properties"]["ap_item_url"] = ans["additional_properties"]["ap_item_url"]
                data["additional_properties"]["sha1"] = ans["additional_properties"]["sha1"]
                data["caption"] = ans["caption"]
                data["subtitle"] = ans["subtitle"]
                res = requests.put(url, json=data, headers=bearer_token())
                res.raise_for_status()

            except Exception as ex:
                # If still errors, report on the error
                logger.error(ex, extra=extra)
                if "res" in locals():
                    logger.error(res.json().get("error_message"), extra=extra)
                return str(ex)

        else:
            logger.error(e, extra=extra)
            if "res" in locals():
                logger.error(res.json().get("message"), extra=extra)
            return str(e)

    logger.info("SAVE INVENTORY")
    inv_item = (
        ans.get("source").get("source_id"),
        ans.get("_id"),
        ans.get("additional_properties").get("ap_item_url"),
        ans.get("type"),
        ans.get("additional_properties").get("sha1"),
        arrow.utcnow().format("YYYY-MM-DD HH:MM:SS.SSS"),
    )
    inventory.create_inventory(conn, inv_item)
    return HTTPStatus.CREATED


def process_wires(converters: list):
    """This will send each wire item into the correct downstream system.
    There is no automatic retry or backoff, except if caused by the rate limiting.
    If one step errors, the error will be logged and the individual item's progress will be halted.
    The next item in the list will still process.
    Only fully successful items are inventoried.
    """
    converters = list(filter(None, converters))
    conn = inventory.create_connection(config("SQLDB_LOCATION", ":memory:"))
    inventory.create_table(conn)
    for index, converter in enumerate(converters):
        count = f"{index + 1} of {len(converters)}"
        if isinstance(converter, APStoryConverter):
            process_wire_story(converter, count, conn)
        elif isinstance(converter, APPhotoConverter):
            process_wire_photo(converter, count, conn)
    conn.close()


def run_ap_ingest_wires():
    # fetch items in ap feed
    items = fetch_feed()
    wires = []
    # initialize converters for each item in the feed
    for item in items:
        if item.get("type") == "picture":
            # do not process ap images that incur cost
            if item.get("pricetag") in ["Unlimited", "", None]:
                converter = fetch_photo_item(item)
                wires.append(converter)
            else:
                logger.warning(
                    "Picture excluded because it would incur cost",
                    extra={"source_id": item.get("source_id"), "priced": item.get("priced"), "pricetag": item.get("pricetag")},
                )
        elif item.get("type") == "text":
            converter = fetch_story_item(item.get("download_url"), item)
            wires.append(converter)

            # if there are pictures associated with the story, add these converters to the wires array
            urls = converter.get_photo_associations_urls()
            for url in urls:
                item = fetch_feed(url)
                converter = fetch_photo_item(item)
                wires.append(converter)
        else:
            # only process text and story wires. videos incur too much cost.
            logger.error(f"Unprocessable wire type: {item.get('type')}")

    process_wires(wires)
    return wires


if __name__ == "__main__":  # pragma: no cover
    # will run the ap feed and ingest content... this is the same as running from the api endpoint
    run_ap_ingest_wires()

    # # Will test sending one story to Draft API twice, triggering the POST -> PUT behavior
    # from tests.conftest import get_file_fixture
    # item = json.loads(
    #     get_file_fixture("/Users/leep2/Repositories/inbound-feeds-poc/tests/fixtures/ap_text_item_test_converter_itemdata.json")
    # )
    # wires = [fetch_story_item(item.get("download_url"), item)]
    # process_wires(wires) # 1st time through (unless this has been run before)
    # process_wires(wires) # 2nd+ time through

    # # will test sending one photo to Photo Center API twice, triggering the POST -> PUT behavior
    # photo_item = fetch_feed(
    #     "https://api.ap.org/media/v/content/8c3f1bee0c95476aa0efcf39ff28b5d2?qt=7j6M__KC0pF&et=0a1aza3c0&ai=6abc8a67a708c9c90d32022eb08fe544"
    # )
    # photo_converter = fetch_photo_item(photo_item)
    # conn = inventory.create_connection(config("SQLDB_LOCATION", ":memory:"))
    # inventory.create_table(conn)
    # process_wire_photo(photo_converter, "0", conn)
    # process_wire_photo(photo_converter, "1", conn)
    # print(photo_converter)
    # conn.close()
