# http://api.ap.org/media/v/docs/Feed_Examples.htm
# http://api.ap.org/media/v/docs/Getting_Content_Updates.htm
import json
from typing import Optional
from pprint import pprint

import requests
from decouple import config
from jmespath import search
from xmltodict import parse

from apps.associated_press.converter import APPhotoConverter, APStoryConverter
from utils.logger import get_logger
from utils.constants import AP_RESULTS_JMESPATH_STR, AP_ASSOCIATIONS_JMESPATH_STR

logger = get_logger()


def fetch_feed(next_page: Optional[str] = None):
    url = "https://api.ap.org/media/v/content/feed"
    params = {"apikey": config("AP_API_KEY")}
    items = {}
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
        items = search(AP_RESULTS_JMESPATH_STR, data) or []
        logger.info(f"{len(items)} items returned from query")
        if not items:
            # this may have been an associations dict from a story rather than one of the results of the og query
            logger.info("fetching photo association from story")
            items = search(AP_ASSOCIATIONS_JMESPATH_STR, data)
    else:
        # LOG Error
        logger.error(f"{res.status_code} {url}")
        next_page = sequence = previous_sequence = None

    # # recurse -- POC, recursion is out of scope
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
        # Convert the XML to JSON. Will use this to compute the shah1 and other ans fields.
        data = parse(res.content).get("nitf", {})
        data = json.loads(json.dumps(data))
        item["content_json"] = data
        converter = APStoryConverter(
            item, org_name=config("ARC_ORG_ID"), website=config("ARC_ORG_WEBSITE"), story_data=res.content
        )
        return converter


def fetch_photo_item(item: dict):
    # AP Photos don't need more info to be parsed, so not bothering to query the url
    converter = APPhotoConverter(item, org_name=config("ARC_ORG_ID"))
    return converter


if __name__ == "__main__":  # pragma: no cover
    # # this is the uri of one of the photos from a story's associations
    # test = fetch_feed(
    #     "https://api.ap.org/media/v/content/28514e83e96c483f8cbac9b3aaabadc4?qt=_dSwUXC5aF&et=1a1aza4c0&ai=95b07bc3a92191b0abea66f851983c59"
    # )

    items = fetch_feed()
    wires = []
    for item in items:
        if item.get("type") == "picture":
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

    pprint(wires)
