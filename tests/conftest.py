import codecs
import json
import os
from json.decoder import JSONDecodeError

import pytest

_TEST_FOLDER = os.path.dirname(__file__)
FIXTURE_DIR = os.path.join(_TEST_FOLDER, "fixtures")


# Set up ability to store sample test data and retrieve it for use in mocks
def get_file_fixture(filename):
    with codecs.open(filename) as f:
        return f.read()


# Set up ability to store sample test data and retrieve it for use in mocks
class FixtureRetriever:
    def get_content(self, identifier, **kwargs):
        if isinstance(identifier, str):
            if ".xml" in identifier:
                return get_file_fixture(os.path.join(FIXTURE_DIR, identifier))

            if ".json" in identifier:
                return json.loads(get_file_fixture(os.path.join(FIXTURE_DIR, identifier)))


# Set up ability to store sample test data and retrieve it for use in mocks
@pytest.fixture(scope="session")
def test_content():
    return FixtureRetriever()
