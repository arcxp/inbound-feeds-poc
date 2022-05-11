import unittest.mock as mock

import pytest
import requests

from apps.associated_press import fetch_feed, fetch_photo_item, fetch_story_item
from apps.associated_press.converter import APPhotoConverter, APStoryConverter, AssociatedPressBaseConverter


class MockResponse:
    def __init__(
        self,
        json_data={},
        status_code=200,
        ok=True,
        reason="",
        url="http://mockurl",
        content="",
    ):
        self.json_data = json_data
        self.status_code = status_code
        self.reason = reason
        self.ok = ok
        self.url = url
        self.content = content

    def json(self):
        return self.json_data


def test_fetch_feed_200(monkeypatch, test_content):
    # any arguments may be passed and mock_get() will always return mocked object
    # apply the monkeypatch for requests.get to mock_get
    def mock_get(*args, **kwargs):
        content = test_content.get_content("associated_press_feed_all_entitled_content.json")
        return MockResponse(content, 200)

    monkeypatch.setattr(requests, "get", mock_get)

    items = fetch_feed()
    assert len(items) == 10
    for x in [
        "type",
        "source_id",
        "url",
        "headline",
        "firstcreated",
        "versioncreated",
        "originalfilename",
        "description_caption",
        "download_url",
    ]:
        assert x in list(items[0].keys())


def test_fetch_feed_401(monkeypatch, test_content):
    def mock_get(*args, **kwargs):
        return MockResponse({}, 401, False)

    monkeypatch.setattr(requests, "get", mock_get)

    items = fetch_feed()
    assert len(items) == 0


def test_fetch_story_item(monkeypatch, test_content):
    """test that a request is made (to get story content) and that results of fetch are added to source data"""

    def mock_get(*args, **kwargs):
        content = test_content.get_content("ap_text_story_Election_2022.xml")
        return MockResponse(content=content)

    monkeypatch.setattr(requests, "get", mock_get)

    converter = fetch_story_item("mytesturl", {"item": {"key1": "234"}})
    assert isinstance(converter, APStoryConverter)
    assert list(converter.source_data.keys()) == ["item", "content_json"]
    assert list(converter.source_data["content_json"].keys()) == [
        "@version",
        "@change.date",
        "@change.time",
        "head",
        "body",
    ]


def test_fetch_photo_item():
    converter = fetch_photo_item({"item": {"key1": "234"}})
    assert isinstance(converter, APPhotoConverter)
    assert list(converter.source_data.keys()) == ["item"]


@pytest.mark.parametrize(
    "ap_type, arc_type",
    [("text", "story"), ("picture", "image"), ("video", "unsupported")],
)
def test_base_converter(ap_type, arc_type):
    converter = AssociatedPressBaseConverter({}, org_name="myorg")
    assert converter.get_type(ap_type) == arc_type
    assert converter.get_arc_id("abc123") == "K7MUMMS7VF7S24QQK6CBUHD274"


def test_photo_converter(test_content):
    converter = APPhotoConverter(test_content.get_content("ap_picture_item_test_converter_data.json"), org_name="myorg")
    ans = converter.convert_ans()
    assert ans.get("version") == "0.10.7"
    assert ans.get("owner").get("id") == "myorg"
    assert ans.get("_id") == "L5Q6DEVOVAC4AB5U3XIX6UFGNQ"
    assert ans.get("publish_date") == ans.get("display_date") == "2022-05-11T17:47:55Z"
    assert ans.get("additional_properties").get("sha1") == "997d71cbbadee68948d4d24ef0222da6f4d17d5d"


def test_story_convertertest_content(test_content):
    converter = APStoryConverter(
        test_content.get_content("ap_text_item_test_converter_itemdata.json"),
        org_name="myorg",
        story_data=test_content.get_content("ap_text_item_test_converter_storydata.xml"),
    )
    ans = converter.convert_ans()
    assert ans.get("version") == "0.10.7"
    assert ans.get("owner").get("id") == "myorg"
    assert ans.get("_id") == 'ZFCHSR4DKLMYSW3O3JC7NDCWMA'
    assert ans.get("publish_date") == ans.get("display_date") == '2022-05-11T04:07:27Z'
    assert ans.get("additional_properties").get("sha1") == 'f34492e539bb74928ecd2593aebbbb4535d39273'
