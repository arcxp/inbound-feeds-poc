import copy
import hashlib
import json
from datetime import datetime
from typing import Optional, Union

from jmespath import search
from slugify import slugify

from utils.arc_id import generate_arc_id
from utils.logger import get_logger

logger = get_logger()


class MismatchedContentTypeException(Exception):
    pass


class AssociatedPressBaseConverter:
    def __init__(self, data: dict, *args, org_name: str = None, **kwargs):
        self.ans_version = "0.10.7"
        self.org_name = org_name
        self.converted_ans = {"version": self.ans_version}
        self.source_data = data

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
                "arc_id": self.get_arc_id(self.source_data.get("source_id")),
                "type": self.get_type(self.source_data.get("type")),
                "owner": {"id": self.org_name},
                # trusting that the ap dates don't need to be converted to work in arc, so using as is
                "publish_date": self.source_data.get("firstcreated"),
                "display_date": self.source_data.get("firstcreated"),
                "additional_properties": {},
            }
        )
        return self.converted_ans

    def get_arc_id(self, source_id):
        return generate_arc_id(source_id)

    def get_type(self, type):
        # trusting that am only importing images and stories, not galleries or videos
        return "image" if type == "picture" else "story" if "text" else "unsupported"


class APStoryConverter(AssociatedPressBaseConverter):
    def convert_ans(self):
        super().convert_ans()
        if self.converted_ans["type"] != "story":
            raise MismatchedContentTypeException

        self.converted_ans.update(
            {
                "foo": "bar",
            }
        )
        # additional_properties can be deeply nested, so update these separately
        self.converted_ans["additional_properties"].update({"sha1": self.get_sha1()})

        logger.info(
            "text conversion",
            extra={
                "arc_id": self.converted_ans.get("arc_id"),
                "source_id": self.source_data.get("source_id"),
                "headline": self.source_data.get("headline"),
                "firstcreated": self.source_data.get("firstcreated"),
                "converted_ans": self.converted_ans,
            },
        )
        return self.converted_ans

    def get_sha1(self):
        "create a sha1 that you can use to determnine later if this object has been updated since it was imported into arc"
        logger.info(
            "computing sha1 hash for story",
            extra={
                "source_id": self.source_data.get("source_id"),
                "headline": self.source_data.get("headline"),
                "firstcreated": self.source_data.get("firstcreated"),
            },
        )
        hash_source = copy.deepcopy(self.source_data)
        # remove items from contributing to the hash that may change without signaling a substantive change to the underlying object
        hash_source.pop("download_url", None)
        hash_source.pop("url", None)
        hash_source.pop("content_xml")
        hash_source.get("content_json").pop("@version")
        hash_source.get("content_json").pop("@change.date")
        hash_source.get("content_json").pop("@change.time")
        source_data_str = json.dumps(hash_source).encode("utf-8")
        return hashlib.sha1(source_data_str).hexdigest()


class APPhotoConverter(AssociatedPressBaseConverter):
    def convert_ans(self):
        super().convert_ans()
        if self.converted_ans["type"] != "image":
            raise MismatchedContentTypeException

        self.converted_ans.update(
            {
                "baz": "lurhman",
            }
        )
        # additional_properties can be deeply nested, so update these separately
        self.converted_ans["additional_properties"].update({"sha1": self.get_sha1()})

        logger.info(
            "photo conversion",
            extra={
                "arc_id": self.converted_ans.get("arc_id"),
                "source_id": self.source_data.get("source_id"),
                "headline": self.source_data.get("headline"),
                "firstcreated": self.source_data.get("firstcreated"),
                "converted_ans": self.converted_ans,
            },
        )
        return self.converted_ans

    def get_sha1(self):
        "create a sha1 that you can use to determnine later if this object has been updated since it was imported into arc"
        logger.info(
            "computing sha1 hash for photo",
            extra={
                "source_id": self.source_data.get("source_id"),
                "headline": self.source_data.get("headline"),
                "firstcreated": self.source_data.get("firstcreated"),
            },
        )
        hash_source = copy.deepcopy(self.source_data)
        # remove items from contributing to the hash that may change without signaling a substantive change to the underlying object
        hash_source.pop("download_url", None)
        hash_source.pop("url", None)
        source_data_str = json.dumps(hash_source).encode("utf-8")
        hash_object = hashlib.sha1(source_data_str).hexdigest()
        return hash_object
