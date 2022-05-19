# http://api.ap.org/media/v/docs/Feed_Examples.htm
# http://api.ap.org/media/v/docs/Getting_Content_Updates.htm
import json
from http import HTTPStatus
from typing import Optional

import requests
from decouple import config
from jmespath import search
from ratelimit import limits, sleep_and_retry
from xmltodict import parse

from apps.associated_press.converter import APPhotoConverter, APStoryConverter
from utils.constants import (
    AP_ASSOCIATIONS_JMESPATH_STR,
    AP_RESULTS_JMESPATH_STR,
    CIRCULATION_URL,
    DRAFT_API_URL,
    OPERATIONS_URL,
    PHOTO_API_URL,
)
from utils.exceptions import IncompleteWirePhotoException, IncompleteWireStoryException, WirePhotoExistsInArcException
from utils.logger import get_logger

logger = get_logger()


def fetch_feed(next_page: Optional[str] = None):
    url = "https://api.ap.org/media/v/content/feed"
    params = {"apikey": config("AP_API_KEY")}
    items = None
    if next_page:
        url = next_page
    res = requests.get(url, params=params)
    if res.ok:
        data = res.json()
        next_page = search("data.next_page", data) or None
        previous_sequence = search("params.seq", data) or None
        sequence = next_page.split("seq=")[-1] if next_page else None

        # log the sequence ids in the db. useful info when tracing back this task's runs.
        logger.info(
            f"{res.status_code} {url}",
            extra={
                "previous_sequence": previous_sequence,
                "sequence": sequence,
                "next_page": next_page,
            },
        )

        # build data from the relevant keys
        items = search(AP_RESULTS_JMESPATH_STR, data)

        # this may have been an associations dict from a story rather than one of the results of the ap query, requires a different structure to the search string
        if items is None:
            # do not process ap images that incur cost
            priced = search("data.item.renditions.main.priced || data.item.renditions.main.pricetag", data)
            if priced in ["Unlimited", False, None, "false"]:
                items = search(AP_ASSOCIATIONS_JMESPATH_STR, data)
    else:
        logger.error(f"{res.status_code} {url}")
        next_page = sequence = previous_sequence = None

    # # recurse -- POC, recursion is out of scope
    # Recursion of the AP wire like this might be problematic.  Testing suggests this could go on forever.
    # if next_page and sequence:
    #     fetch_feed(next_page)
    # else:
    #     print("ENDING recursion")
    return items


def fetch_story_item(url: str, item: dict):
    params = {"apikey": config("AP_API_KEY")}
    res = requests.get(url, params=params)
    if res.ok:
        # AP stories are XML. Add the XML. The converter will use the XML to parse the content elements.
        # Convert the XML to JSON. Will use this to compute the sha1 and other ans fields.
        data = parse(res.content).get("nitf", {})
        data = json.loads(json.dumps(data))
        item["content_json"] = data
        converter = APStoryConverter(
            item, org_name=config("ARC_ORG_ID"), website=config("ARC_ORG_WEBSITE"), story_data=res.content
        )
        return converter


def fetch_photo_item(item: dict):
    # AP Photos don't need more info than what comes via the feed/query initial request
    # to be parsed, so not bothering to query the full photo url for additional data
    converter = APPhotoConverter(item, org_name=config("ARC_ORG_ID"))
    return converter


def bearer_token():
    if "sandbox." in config("ARC_ORG_ID"):
        token = config("ARC_TOKEN_SANDBOX")
    else:
        token = config("ARC_TOKEN_PRODUCTION")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@sleep_and_retry
@limits(calls=2, period=60)
def process_wire_story(converter: APStoryConverter, count: str):
    logger.info(f"{count} {converter}")
    ans = None
    circulation = None
    operation = None
    org = config("ARC_ORG_ID")
    logger.info("GENERATE ANS & CIRCULATION & OPERATION")
    try:
        ans = converter.convert_ans()
        circulation = converter.get_circulation()
        operation = converter.get_scheduled_delete_operation()
        if ans is None or circulation is None or operation is None:
            raise IncompleteWireStoryException
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
        logger.error(e, extra=extra)
        logger.error(res.json().get("error_message"), extra=extra)
        return str(e)

    logger.info("SEND OPERATION")
    try:
        res = requests.put(OPERATIONS_URL.format(org=org), json=operation, headers=bearer_token())
        res.raise_for_status()
    except Exception as e:
        logger.error(e, extra=extra)
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
        logger.error(res.json().get("error_message"), extra=extra)
        return str(e)

    logger.info("SAVE INVENTORY")
    return HTTPStatus.CREATED


@sleep_and_retry
@limits(calls=5, period=60)
def process_wire_photo(converter: APPhotoConverter, count: str):
    logger.info(f"{count} {converter}")
    ans = None
    sha1 = None
    logger.info("GENERATE ANS")
    try:
        ans = converter.convert_ans()
        if ans is None:
            raise IncompleteWirePhotoException

        logger.info("CHECK INVENTORY - SHA1 EXISTS & IS SAME")
        # TODO this may need to be a function so it can be testing mockable
        inventory_sha1 = 1
        if inventory_sha1 == ans.get("additional_properties").get("sha1"):
            raise WirePhotoExistsInArcException

    except Exception as e:
        logger.error(e, extra={"ans": ans is not None, "sha1": sha1})
        return str(e)

    logger.info("SEND ANS TO PHOTO API")
    try:
        ans["additional_properties"]["originalUrl"] += f"&apikey={config('AP_API_KEY')}"
        res = requests.post(
            PHOTO_API_URL.format(org=config("ARC_ORG_ID"), arc_id=ans.get("_id")), json=ans, headers=bearer_token()
        )
        res.raise_for_status()
    except Exception as e:
        extra = {
            "arc_id": ans.get("_id"),
            "source_id": ans.get("source").get("source_id"),
            "sha1": sha1,
            "caption": ans.get("caption"),
        }
        logger.error(e, extra=extra)
        logger.error(res.json().get("message"), extra=extra)
        return str(e)

    logger.info("SAVE INVENTORY")


def process_wires(converters: list):
    """This will send each wire item into the correct downstream system.
    There is no automatic retry or backoff, except if caused by the rate limiting applied.
    If one step errors, the error will be logged and the item's progress will be halted.
    Only fully successful items are inventoried.
    """
    converters = list(filter(None, converters))
    for index, converter in enumerate(converters):
        count = f"{index} of {len(converters)}"
        if isinstance(converter, APStoryConverter):
            process_wire_story(converter, count)
        elif isinstance(converter, APPhotoConverter):
            process_wire_photo(converter, count)


if __name__ == "__main__":  # pragma: no cover
    # # this is the uri of one of the photos from a story's associations
    # test = fetch_feed(
    #     "https://api.ap.org/media/v/content/28514e83e96c483f8cbac9b3aaabadc4?qt=_dSwUXC5aF&et=1a1aza4c0&ai=95b07bc3a92191b0abea66f851983c59"
    # )

    items = fetch_feed()
    wires = []
    for item in items:
        if item.get("type") == "picture":
            # do not process ap images that incur cost
            if not item.get("priced", False) and item.get("pricetag") in ["Unlimited", None]:
                converter = fetch_photo_item(item)
                wires.append(converter)
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
            logger.info(item.get("type"))

    process_wires(wires)
