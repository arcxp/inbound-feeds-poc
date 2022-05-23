import unittest.mock as mock
from functools import wraps


# To test any of the process_wire* functions, the @limits() decorator needs to be nullified
def mock_decorator(*args, **kwargs):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            return f(*args, **kwargs)

        return decorated_function

    return decorator


# nullify @limits() decorator used by process-wire* functions
mock.patch("ratelimit.limits", mock_decorator).start()

import http

import freezegun
import pytest
import requests

from apps.associated_press import (
    fetch_feed,
    fetch_photo_item,
    fetch_story_item,
    process_wire_photo,
    process_wire_story,
    run_ap_ingest_wires,
)
from apps.associated_press.converter import APPhotoConverter, APStoryConverter, AssociatedPressBaseConverter
from tests.fixtures.content_elements import TEST_CASES as content_elements_tests


class MockResponse:
    def __init__(self, json_data={}, status_code=200, ok=True, reason="", url="http://mockurl", content="", raise_for_status=None):
        self.json_data = json_data
        self.status_code = status_code
        self.reason = reason
        self.ok = ok
        self.url = url
        self.content = content
        if raise_for_status:
            self.raise_for_status = mock.Mock(side_effect=raise_for_status)

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
        "bylines",
        "firstcreated",
        "versioncreated",
        "originalfilename",
        "description_caption",
        "download_url",
        "priced",
        "pricetag",
    ]:
        assert x in list(items[0].keys())


def test_fetch_feed_401(monkeypatch, test_content):
    def mock_get(*args, **kwargs):
        return MockResponse({}, 401, False)

    monkeypatch.setattr(requests, "get", mock_get)

    items = fetch_feed()
    assert items is None


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
@freezegun.freeze_time("2022-01-01 00:00")  # mocks the use of arrow.utcnow() in the converter
def test_base_converter(ap_type, arc_type):
    converter = AssociatedPressBaseConverter({}, org_name="myorg")
    assert converter.get_arc_type(ap_type) == arc_type
    assert converter.get_arc_id("abc123") == "Y6LNM3BS6XOBZGSCZXJARW2HZM"
    assert converter.get_expiration_date() == "2022-01-04T00:00:00Z"


@freezegun.freeze_time("2022-01-01 00:00")  # mocks the use of arrow.utcnow() in the converter
def test_photo_converter(test_content):
    converter = APPhotoConverter(test_content.get_content("ap_picture_item_test_converter_data.json"), org_name="myorg")
    ans = converter.convert_ans()
    assert ans.get("version") == "0.10.7"
    assert ans.get("type") == "image"
    assert ans.get("owner").get("id") == "myorg"
    assert ans.get("_id") == "4SMRDV6XJETBEANTUQZEXHTJX4"
    assert ans.get("publish_date") == ans.get("display_date") == "2022-05-11T17:47:55Z"
    assert ans.get("distributor") == {"category": "wires", "name": "Associated Press", "mode": "custom"}
    assert ans.get("source") == {
        "name": "Associated Press",
        "system": "Associated Press",
        "source_id": "d718de68c8824b1ba8b8089bfbab5804",
    }
    assert (
        ans.get("caption")
        == "8189587 11.05.2022 Yenisey's goalkeeper Mikhail Oparin pours water in his face during the Russian Cup semifinal soccer match between Spartak Moscow and Yenisey Krasnoyarsk, in Moscow, Russia. Alexey Filippov / Sputnik  via AP"
    )
    assert ans.get("subtitle") == "Russia Soccer Cup Spartak - Yenisey"
    assert ans.get("additional_properties").get("sha1") == "ac40eec930916383cc39ebce51cb036227e2f2fe"
    assert (
        ans.get("additional_properties").get("originalUrl")
        == "https://api.ap.org/media/v/content/6bb4a755875f44338d4a2b12bea5446d.0/download?role=main&qt=QlDpbGcIskF&cid=d718de68c8824b1ba8b8089bfbab5804&pt=NDUyNjd8OTkxMDd8NnwzNXxVU0Q"
    )
    assert ans.get("additional_properties").get("originalName") == "Russia_Soccer_Cup_Spartak_-_Yenisey_17799.jpg"
    assert ans.get("additional_properties").get("expiration_date") == "2022-01-04T00:00:00Z"
    assert (
        ans.get("additional_properties").get("ap_item_url")
        == "https://api.ap.org/media/v/content/6bb4a755875f44338d4a2b12bea5446d?qt=QlDpbGcIskF&et=0a1aza3c0"
    )


@freezegun.freeze_time("2022-01-01 00:00")  # mocks the use of arrow.utcnow() in the converter
def test_story_converter(test_content):
    converter = APStoryConverter(
        test_content.get_content("ap_text_item_test_converter_itemdata.json"),
        org_name="myorg",
        website="mywebsite",
        story_data=test_content.get_content("ap_text_item_test_converter_storydata.xml"),
    )
    ans = converter.convert_ans()
    assert ans.get("version") == "0.10.7"
    assert ans.get("owner").get("id") == "myorg"
    assert ans.get("type") == "story"
    assert ans.get("_id") == "WTMJO4FHXDCGIFKCYNKGZE3UKY"
    assert ans.get("canonical_website") == "mywebsite"
    assert ans.get("source") == {
        "name": "Associated Press",
        "system": "Associated Press",
        "source_id": "933046d59d58616e5f3e2b00cddfceae",
    }
    assert ans.get("publish_date") == ans.get("display_date") == "2022-05-11T04:07:27Z"
    assert ans.get("additional_properties").get("sha1") == "5fb395eeb761d3c337418bd52700128329047e34"
    assert (
        ans.get("additional_properties").get("ap_item_url")
        == "https://api.ap.org/media/v/content/d38703c060c6b066f2bd9012d147c6e1?qt=HNKVoTocLIF&et=17a1aza0c0"
    )
    assert ans.get("headlines").get("basic") == "Ukraine to hold first war crimes trial of captured Russian"
    assert ans.get("credits") == {
        "by": [{"type": "author", "name": "ELENA BECATOROS and JON GAMBRELL", "org": "Associated Press"}]
    }
    assert ans.get("distributor") == {"category": "wires", "name": "Associated Press", "mode": "custom"}
    assert ans.get("workflow").get("status_code") == 1
    assert len(ans.get("content_elements")) == 30

    circulation = converter.get_circulation()
    assert circulation.get("document_id") == "WTMJO4FHXDCGIFKCYNKGZE3UKY"
    assert circulation.get("website_id") == "mywebsite"
    assert circulation.get("website_url") == "/ukraine-to-hold-first-war-crimes-trial-of-captured-russian"
    assert circulation.get("website_primary_section").get("type") == "reference"
    assert circulation.get("website_primary_section").get("referent") == {
        "id": "/sample/wires",
        "type": "section",
        "website": "mywebsite",
    }
    assert circulation.get("website_sections") == [
        {"type": "reference", "referent": {"id": "/sample/wires", "type": "section", "website": "mywebsite"}}
    ]

    delete_operation = converter.get_scheduled_delete_operation()
    assert delete_operation.get("type") == "story_operation"
    assert delete_operation.get("story_id") == "WTMJO4FHXDCGIFKCYNKGZE3UKY"
    assert delete_operation.get("operation") == "delete"
    assert delete_operation.get("date") == "2022-01-04T00:00:00Z"

    associations_urls = converter.get_photo_associations_urls()
    assert associations_urls == [
        "https://api.ap.org/media/v/content/d110254bbaf54b2098e36e3ced474862?qt=HNKVoTocLIF&et=1a1aza3c0&ai=d38703c060c6b066f2bd9012d147c6e1",
        "https://api.ap.org/media/v/content/15667ba3019843fc89c922cc822ffb4b?qt=HNKVoTocLIF&et=0a1aza3c0&ai=d38703c060c6b066f2bd9012d147c6e1",
        "https://api.ap.org/media/v/content/bf1096954ea44abdabcd1bd204991983?qt=HNKVoTocLIF&et=0a1aza3c0&ai=d38703c060c6b066f2bd9012d147c6e1",
    ]

    associations = converter.get_photo_associations()
    assert associations == [
        {"referent": {"id": "5WAHGB4GUQEDL5NXO2YQNKELZY", "type": "image"}, "type": "reference"},
        {"referent": {"id": "ZL7AOJH4MLAS4AHT4K5RYU6Q3A", "type": "image"}, "type": "reference"},
        {"referent": {"id": "YMWMWCQE47HXC5UDJKJEIWD3LY", "type": "image"}, "type": "reference"},
    ]
    assert ans.get("related_content").get("basic") == associations


@pytest.mark.parametrize("source_id, content_elements", content_elements_tests.items())
def test_story_content_elements(source_id, content_elements, test_content):
    converter = APStoryConverter(
        test_content.get_content("ap_text_item_test_converter_itemdata.json"),
        org_name="myorg",
        website="mywebsite",
        story_data=test_content.get_content("ap_text_item_test_converter_storydata.xml"),
    )

    assert converter.get_content_elements(converter.story_data) == content_elements


@mock.patch("apps.associated_press.converter.APStoryConverter")
def test_process_wire_story_incomplete(mock_converter):
    # note: is affected by the mock_decorator function at top of test file.
    mock_converter.get_circulation.return_value = None
    assert (
        process_wire_story(mock_converter, "0 of 0")
        == "Wire story cannot be sent to Draft API without ans and circulation and operations data"
    )

    mock_converter.convert_ans.return_value = None
    assert (
        process_wire_story(mock_converter, "0 of 0")
        == "Wire story cannot be sent to Draft API without ans and circulation and operations data"
    )

    mock_converter.get_scheduled_delete_operation.return_value = None
    assert (
        process_wire_story(mock_converter, "0 of 0")
        == "Wire story cannot be sent to Draft API without ans and circulation and operations data"
    )


@mock.patch("apps.associated_press.converter.APStoryConverter")
def test_process_wire_story_error_draftapi(mock_converter, monkeypatch):
    # note: is affected by the mock_decorator function at top of test file.

    def mock_post(*args, **kwargs):
        return MockResponse(
            json_data={"error_message": "it messed up"},
            status_code=400,
            ok=False,
            raise_for_status=requests.exceptions.RequestException("Response not OK!"),
        )

    monkeypatch.setattr(requests, "post", mock_post)
    mock_converter.get_circulation.return_value = {}
    mock_converter.convert_ans.return_value = {"_id": "123", "source": {"source_id": "abc"}, "headlines": {"basic": "stuff"}}
    mock_converter.get_scheduled_delete_operation.return_value = {}

    assert process_wire_story(mock_converter, "0 of 0") == "Response not OK!"


@mock.patch("requests.post")
@mock.patch("apps.associated_press.converter.APStoryConverter")
def test_process_wire_story_error_operationsapi(mock_converter, mock_post, monkeypatch):
    # note: is affected by the mock_decorator function at top of test file.
    def mock_put(*args, **kwargs):
        return MockResponse(
            json_data={"error_message": "it messed up"},
            status_code=400,
            ok=False,
            raise_for_status=requests.exceptions.RequestException("Response not OK!"),
        )

    monkeypatch.setattr(requests, "put", mock_put)
    mock_converter.get_circulation.return_value = {}
    mock_converter.convert_ans.return_value = {"_id": "123", "source": {"source_id": "abc"}, "headlines": {"basic": "stuff"}}
    mock_converter.get_scheduled_delete_operation.return_value = {}

    assert process_wire_story(mock_converter, "0 of 0") == "Response not OK!"
    assert mock_post.called == True


@mock.patch("requests.put")
@mock.patch("requests.post")
@mock.patch("apps.associated_press.converter.APStoryConverter")
def test_process_wire_story_error_circulationsapi(mock_converter, mock_post, mock_put):
    # note: is affected by the mock_decorator function at top of test file.
    mock_converter.get_circulation.return_value = {}
    mock_converter.convert_ans.return_value = {"_id": "123", "source": {"source_id": "abc"}, "headlines": {"basic": "stuff"}}
    mock_converter.get_scheduled_delete_operation.return_value = {}
    mock_put.side_effect = [
        MockResponse(raise_for_status=lambda: None),
        MockResponse(
            json_data={"error_message": "it messed up"},
            status_code=400,
            ok=False,
            raise_for_status=requests.exceptions.RequestException("Response not OK!"),
        ),
    ]
    assert process_wire_story(mock_converter, "0 of 0") == "Response not OK!"
    assert mock_post.called == True
    assert mock_put.call_count == 2


@mock.patch("requests.put")
@mock.patch("requests.post")
@mock.patch("apps.associated_press.converter.APStoryConverter")
def test_process_wire_story_happy_path(mock_converter, mock_post, mock_put):
    # note: is affected by the mock_decorator function at top of test file.
    mock_converter.get_circulation.return_value = {}
    mock_converter.convert_ans.return_value = {"_id": "123", "source": {"source_id": "abc"}, "headlines": {"basic": "stuff"}}
    mock_converter.get_scheduled_delete_operation.return_value = {}
    assert process_wire_story(mock_converter, "0 of 0") == http.HTTPStatus.CREATED
    assert mock_post.call_count == 1
    assert mock_put.call_count == 2


@mock.patch("apps.associated_press.converter.APPhotoConverter")
def test_process_wire_photo_incomplete(mock_converter):
    # note: is affected by the mock_decorator function at top of test file.
    mock_converter.convert_ans.return_value = None
    assert process_wire_photo(mock_converter, "0 of 0") == "Wire photo cannot be sent to Draft API without ans data"


@mock.patch("requests.post")
@mock.patch("apps.associated_press.converter.APPhotoConverter")
def test_process_wire_photo_error_photoapi(mock_converter, mock_post):
    # note: is affected by the mock_decorator function at top of test file.
    mock_converter.convert_ans.return_value = {
        "_id": "123",
        "source": {"source_id": "abc"},
        "headlines": {"basic": "stuff"},
        "additional_properties": {"sha1": "1a2b3c", "originalUrl": "http://stuff"},
        "caption": "a caption",
    }
    mock_post.side_effect = [MockResponse(raise_for_status=requests.exceptions.RequestException("Response not OK!"))]
    assert process_wire_photo(mock_converter, "0 of 0") == "Response not OK!"
    assert mock_post.called == True


@mock.patch("apps.associated_press.fetch_feed")
def test_run_ap_ingest_wires(mock_fetch_feed, test_content):
    mock_fetch_feed.return_value = test_content.get_content("ap_feed_items.json")
    wires = run_ap_ingest_wires()
    assert len(wires) == 27
    for wire in wires:
        assert isinstance(wire, AssociatedPressBaseConverter)
