import sqlite3
import unittest.mock as mock

import freezegun
import pytest

from utils.inventory import (
    create_connection,
    create_inventory,
    create_table,
    select_inventory_by_sha1,
    select_inventory_by_source,
    update_inventory,
)


@mock.patch("sqlite3.connect")
def test_create_connection(mock_connect):
    create_connection()
    assert mock_connect.call_count == 1

    create_connection("dbfile.db")
    assert mock_connect.call_count == 2


@mock.patch("sqlite3.connect")
def test_create_table(mock_connect):
    create_table(mock_connect)
    assert mock_connect.cursor.call_count == 1


@mock.patch("sqlite3.connect")
def test_update_inventory(mock_connect):
    update_inventory(mock_connect, ("url", "sha1", "date"))
    assert mock_connect.cursor.call_count == 1


@mock.patch("sqlite3.connect")
def test_select_inventory(mock_connect):
    rows = select_inventory_by_source(mock_connect, "source_id")
    assert mock_connect.cursor.call_count == 1

    rows = select_inventory_by_sha1(mock_connect, "sha1")
    assert mock_connect.cursor.call_count == 2


@mock.patch("sqlite3.connect")
def test_create_inventory(mock_connect):
    stuff = (
        "mysourceid1",
        "ABC123",
        "https://apfeedurl/test1",
        "story",
        "aabbaa5434",
        "date",
    )
    create_inventory(mock_connect, stuff)
    assert mock_connect.cursor.call_count == 1
