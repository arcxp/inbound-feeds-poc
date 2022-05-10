import requests

from apps.associated_press import fetch_feed


class MockResponse:
    def __init__(
        self, json_data={}, status_code=200, ok=True, reason="", url="http://mockurl"
    ):
        self.json_data = json_data
        self.status_code = status_code
        self.reason = reason
        self.ok = ok
        self.url = url

    def json(self):
        return self.json_data


def test_fetch_feed_200(monkeypatch, test_content):
    # any arguments may be passed and mock_get() will always return mocked object
    # apply the monkeypatch for requests.get to mock_get
    def mock_get(*args, **kwargs):
        content = test_content.get_content(
            "associated_press_feed_all_entitled_content.json"
        )
        return MockResponse(content, 200)

    monkeypatch.setattr(requests, "get", mock_get)

    items = fetch_feed()
    assert len(items) == 10
    assert list(items[0].keys()) == [
        "type",
        "source_id",
        "url",
        "headline",
        "firstcreated",
        "versioncreated",
        "originalfilename",
        "description_caption",
        "download_url",
    ]


def test_fetch_feed_401(monkeypatch, test_content):
    # any arguments may be passed and mock_get() will always return mocked object
    # apply the monkeypatch for requests.get to mock_get
    def mock_get(*args, **kwargs):
        return MockResponse({}, 401, False)

    monkeypatch.setattr(requests, "get", mock_get)

    items = fetch_feed()
    assert len(items) == 0
