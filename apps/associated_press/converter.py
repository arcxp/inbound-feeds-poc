import copy
import hashlib
import json
import re
from typing import Optional, Union

import arrow
from html2ans.default import Html2Ans
from jmespath import search
from slugify import slugify

from utils.arc_id import generate_arc_id
from utils.exceptions import MismatchedContentTypeException
from utils.logger import get_logger

logger = get_logger()


class AssociatedPressBaseConverter:
    def __init__(
        self, data: dict, *args, org_name: str = None, website: str = None, section: str = None, story_data: bytes = None, **kwargs
    ):
        self.ans_version = "0.10.7"
        self.org_name = org_name
        self.website = website
        self.section = section
        self.converted_ans = {"version": self.ans_version}
        self.source_data = data
        self.story_data = story_data

    def convert_ans(self):
        logger.info(
            f"{self.source_data.get('type')} source data",
            extra={
                "source_id": self.source_data.get("source_id"),
                "headline": self.source_data.get("headline"),
                "firstcreated": self.source_data.get("firstcreated"),
            },
        )
        self.converted_ans.update(
            {
                "_id": self.get_arc_id(self.source_data.get("source_id")),
                "type": self.get_arc_type(self.source_data.get("type")),
                "owner": {"id": self.org_name},
                # the ap dates are already in proper format and don't need to be converted to work in arc
                "publish_date": self.source_data.get("firstcreated"),
                "display_date": self.source_data.get("firstcreated"),
                # usually distributor field would reference an exact id value that is stored in the org's Global Settings.
                # Doing so would change the mapping of the distributor key below.
                # Change to the proper ans format if using a distributor id.
                "distributor": {"category": "wires", "name": "Associated Press", "mode": "custom"},
                "source": {
                    "name": "Associated Press",
                    "system": "Associated Press",
                    "source_id": self.source_data.get("source_id"),
                },
                "additional_properties": {},
            }
        )
        return self.converted_ans

    def get_arc_id(self, source_id: str):
        """arc ids should consist of the content source id and also the arc org id"""
        return generate_arc_id(source_id, self.org_name)

    @staticmethod
    def get_arc_type(ap_type: str):
        """importing images and stories, not galleries or videos"""
        return "image" if ap_type == "picture" else "story" if ap_type == "text" else "unsupported"

    @staticmethod
    def get_expiration_date():
        """generate a date 3 days from today. could be enhanced to have the number of days be an env variable"""
        return str(
            arrow.utcnow().shift(days=3).replace(hour=0, minute=0, second=0, microsecond=0).format("YYYY-MM-DDTHH:mm:ss") + "Z"
        )


class APStoryConverter(AssociatedPressBaseConverter):
    def convert_ans(self):
        """transform AP Story into Arc ANS"""
        self.converted_ans = super().convert_ans()
        if self.converted_ans["type"] != "story":
            raise MismatchedContentTypeException

        self.converted_ans.update(
            {
                "canonical_website": self.website,
                "headlines": {"basic": self.source_data.get("headline", "")},
                "credits": {"by": self.get_byline(self.source_data.get("bylines"))},
                "workflow": {"status_code": 1},  # status_code 1 should be "Draft", but verify
                "additional_properties": {
                    "ap_item_url": self.source_data.get("url"),
                    "sha1": self.get_sha1(),
                },
                "related_content": {"basic": self.get_photo_associations()},
                "content_elements": self.get_content_elements(self.story_data),
            }
        )

        logger.info(
            "text conversion",
            extra={
                "arc_id": self.converted_ans.get("_id"),
                "source_id": self.source_data.get("source_id"),
                "headline": self.source_data.get("headline"),
                "firstcreated": self.source_data.get("firstcreated"),
                "converted_ans": self.converted_ans,
            },
        )

        return self.converted_ans

    def get_circulation(self):
        """The circulations payload needed to post to Draft API"""
        circulation = {
            "document_id": self.get_arc_id(self.source_data.get("source_id")),
            "website_id": self.website,
            "website_url": self.get_website_url(self.source_data.get("headline")),
            "website_primary_section": {
                "type": "reference",
                "referent": {"id": self.section, "type": "section", "website": self.website},
            },
            "website_sections": [
                {"type": "reference", "referent": {"id": self.section, "type": "section", "website": self.website}}
            ],
        }
        logger.info(
            "story circulation",
            extra={
                "arc_id": circulation.get("document_id"),
                "source_id": self.source_data.get("source_id"),
                "headline": self.source_data.get("headline"),
                "firstcreated": self.source_data.get("firstcreated"),
                "circulation": circulation,
            },
        )
        return circulation

    def get_scheduled_delete_operation(self):
        """The payload needed to post to the Content Operations API to delete this item x days in future"""
        scheduled_delete = {
            "type": "story_operation",
            "story_id": self.get_arc_id(self.source_data.get("source_id")),
            "operation": "delete",
            "date": self.get_expiration_date(),
        }
        logger.info(
            "story delete operation",
            extra={
                "arc_id": scheduled_delete.get("story_id"),
                "source_id": self.source_data.get("source_id"),
                "headline": self.source_data.get("headline"),
                "firstcreated": self.source_data.get("firstcreated"),
                "scheduled_delete": scheduled_delete,
            },
        )
        return scheduled_delete

    def get_sha1(self):
        """create a hash value that you can use to determnine later if this object has been updated since it was imported into arc"""
        hash_source = copy.deepcopy(self.source_data)
        # remove items from contributing to the hash if they may change without signaling a substantive change to the actual content
        hash_source.pop("download_url", None)
        hash_source.pop("url", None)
        hash_source.pop("priced", None)
        hash_source.pop("pricetag", None)
        photos = search("associations.*.altids.itemid", hash_source)
        hash_source["associations"] = photos
        hash_source.get("content_json").pop("@version", None)
        hash_source.get("content_json").pop("@change.date", None)
        hash_source.get("content_json").pop("@change.time", None)
        source_data_str = json.dumps(hash_source).encode("utf-8")
        logger.info(
            "computing sha1 hash for story",
            extra={
                "source_id": self.source_data.get("source_id"),
                "headline": self.source_data.get("headline"),
                "firstcreated": self.source_data.get("firstcreated"),
                "hash_str": source_data_str
            },
        )
        return hashlib.sha1(source_data_str).hexdigest()

    def get_byline(self, bylines: list):
        authors = []
        if bylines:
            # replace By in the author name
            for a in bylines:
                compiled = re.compile(re.escape("by"), re.IGNORECASE)
                a["by"] = compiled.sub("", a["by"]).strip()
            # Build in the style of an author that is local to the story, not an author referenced from author service
            authors = [{"type": "author", "name": author.get("by"), "org": author.get("title")} for author in bylines]
        return authors

    def get_website_url(self, headline: str):
        return self.section + "/" + slugify(headline)

    def get_photo_associations_urls(self):
        """return the urls of the photo associations so their full details can be requested"""
        associations = self.source_data.get("associations", None)
        return search("* | [?type == `picture`].uri", associations) or []

    def get_photo_associations(self):
        """write ans references for each of the pictures in a story's associations.
        save original source id in case you need to research in the logs why this image did not import."""
        ids = search("* | [?type == `picture`].altids.itemid", self.source_data.get("associations")) or []
        ids = [
            {
                "referent": {
                    "id": self.get_arc_id(id),
                    "type": "image",
                    "referent_properties": {"additional_properties": {"original": {"source_id": id}}},
                },
                "type": "reference",
                "id": self.get_arc_id(id),
            }
            for id in ids
        ]
        return ids

    def get_content_elements(self, story_data: bytes):
        parser = Html2Ans(ans_version=self.ans_version)
        parser.WRAPPER_TAGS += ["block"]
        parser.EMPTY_STRINGS += ["\\n"]
        content_elements = parser.generate_ans(story_data, "body.content")
        return content_elements


class APPhotoConverter(AssociatedPressBaseConverter):
    def convert_ans(self):
        """Transform AP Photo into Arc ANS"""
        self.converted_ans = super().convert_ans()
        if self.converted_ans["type"] != "image":
            raise MismatchedContentTypeException

        self.converted_ans.update(
            {
                "additional_properties": {
                    "originalName": self.source_data.get("originalfilename"),
                    "originalUrl": self.source_data.get("download_url"),
                    "ap_item_url": self.source_data.get("url"),
                    "expiration_date": self.get_expiration_date(),
                    "sha1": self.get_sha1(),
                },
                "caption": self.source_data.get("description_caption"),
                "subtitle": self.source_data.get("headline"),
            }
        )

        logger.info(
            "photo conversion",
            extra={
                "arc_id": self.converted_ans.get("_id"),
                "source_id": self.source_data.get("source_id"),
                "headline": self.source_data.get("headline"),
                "firstcreated": self.source_data.get("firstcreated"),
                "converted_ans": self.converted_ans,
            },
        )
        return self.converted_ans

    def get_sha1(self):
        """create a hash value that you can use to determnine later if this object has been updated since it was imported into arc"""

        hash_source = copy.deepcopy(self.source_data)
        # remove items from contributing to the hash if they may change without signaling a substantive change to the actual content
        hash_source.pop("download_url", None)
        hash_source.pop("url", None)
        hash_source.pop("priced", None)
        hash_source.pop("pricetag", None)
        source_data_str = json.dumps(hash_source).encode("utf-8")
        logger.info(
            "computing sha1 hash for photo",
            extra={
                "source_id": self.source_data.get("source_id"),
                "headline": self.source_data.get("headline"),
                "firstcreated": self.source_data.get("firstcreated"),
                "hash_str": source_data_str
            },
        )
        hash_object = hashlib.sha1(source_data_str).hexdigest()
        return hash_object
