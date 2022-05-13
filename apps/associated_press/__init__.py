# http://api.ap.org/media/v/docs/Feed_Examples.htm
# http://api.ap.org/media/v/docs/Getting_Content_Updates.htm
import json
from typing import Optional

import requests
from decouple import config
from jmespath import search
from xmltodict import parse

from apps.associated_press.converter import APPhotoConverter, APStoryConverter
from utils.logger import get_logger

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
        sequence = next_page.split("seq=")[-1]

        # log the sequence ids in the db. useful info when tracing back this task's runs.
        logger.info(
            f"{res.status_code} {url}",
            extra={
                "previous_sequence": previous_sequence,
                "sequence": sequence,
                "next_page": next_page,
            },
        )

        # choose the relevant items from the results
        items = search(
            'data.items[*].item.{"type": type, "source_id": renditions.main.contentid || renditions.nitf.contentid, '
            '"url": uri, "headline": headline, "firstcreated": firstcreated, '
            '"versioncreated": versioncreated, "originalfilename": renditions.main.originalfilename, '
            '"description_caption": description_caption, "download_url": renditions.main.href || renditions.nitf.href}',
            data,
        )
        logger.info(f"{len(items)} items returned from query")
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
    items = fetch_feed()
    if items:
        if items[0].get("type") == "picture":
            converter = fetch_photo_item(items[0])
        else:
            converter = fetch_story_item(items[0].get("download_url"), items[0])
        converter.convert_ans()
