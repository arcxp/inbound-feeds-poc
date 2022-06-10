import sqlite3
from sqlite3 import Error

import arrow
from decouple import config
from utils.logger import get_logger

logger = get_logger()


def create_connection(dbfile: str = ":memory:"):
    conn = None
    try:
        conn = sqlite3.connect(dbfile)
        logger.info(f"SQLite3 connection created {sqlite3.version} to db {dbfile}")
        return conn
    except Error as e:
        logger.error(e)


def create_table(conn):
    create_table_sql = """CREATE TABLE IF NOT EXISTS ap_feed_inventory (
    source_id    STRING   CONSTRAINT source_id_constraint UNIQUE ON CONFLICT REPLACE
                          NOT NULL,
    arc_id       STRING   CONSTRAINT arc_id_constraint UNIQUE ON CONFLICT FAIL
                          NOT NULL,
    ap_url       STRING,
    arc_type     STRING   NOT NULL,
    sha1         STRING,
    updated_date DATETIME NOT NULL
); """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
    except Error as e:
        logger.error(e)


def create_inventory(conn, inventory):
    sql = """ INSERT INTO ap_feed_inventory(source_id, arc_id, ap_url, arc_type, sha1, updated_date) 
              VALUES (?, ?, ?, ?, ?, ?) """

    cursor = conn.cursor()
    try:
        cursor.execute(sql, inventory)
    except Exception as e:
        # sqlite3.IntegrityError: UNIQUE constraint failed: ap_feed_inventory.arc_id
        sql = """ UPDATE ap_feed_inventory SET ap_url = ?, sha1 = ?, updated_date = ? WHERE source_id = ? """
        cursor.execute(sql, (inventory[2], inventory[4], inventory[5], inventory[0]))
    conn.commit()
    return cursor.lastrowid


def update_inventory(conn, inventory):
    sql = """ UPDATE ap_feed_inventory SET ap_url = ?, sha1 = ?, updated_date = ? WHERE source_id = ? """
    cursor = conn.cursor()
    cursor.execute(sql, inventory)
    conn.commit()
    return cursor.lastrowid


def select_inventory_by_source(conn, source_id):
    sql = "SELECT * FROM ap_feed_inventory WHERE source_id = ?;"
    cursor = conn.cursor()
    cursor.execute(sql, (source_id,))
    rows = cursor.fetchall()
    return rows


def select_inventory_by_sha1(conn, sha1):
    sql = "SELECT sha1 FROM ap_feed_inventory WHERE sha1 = ?;"
    cursor = conn.cursor()
    cursor.execute(sql, (sha1,))
    rows = cursor.fetchall()
    return bool(rows)


if __name__ == "__main__":  # pragma: no cover

    sqldb_location = config("SQLDB_LOCATION", None)
    conn = create_connection(sqldb_location)

    if conn is not None:
        print("create table 1")
        create_table(conn)
    else:
        print("Error! cannot create the database connection.")
    print("create table 2")
    create_table(conn)

    with conn:
        invenory = (
            "mysourceid1",
            "ABC123",
            "https://apfeedurl/test1",
            "story",
            "aabbaa5434",
            arrow.utcnow().format("YYYY-MM-DD HH:MM:SS.SSS"),
        )
        item = create_inventory(conn, invenory)
        print(item)

        rows = select_inventory_by_source(conn, "mysourceid1")
        print(rows)

        sha1_exists = select_inventory_by_sha1(conn, "mysourceid1")
        print(sha1_exists)
        sha1_exists = select_inventory_by_sha1(conn, "aabbaa5434")
        print(sha1_exists)

        inventory = ("https://apfeedurl/test2", "54332abbas5", arrow.utcnow().format("YYYY-MM-DD HH:MM:SS.SSS"), "mysourceid1")
        item = update_inventory(conn, inventory)
        print(item)
        rows = select_inventory_by_source(conn, "mysourceid1")
        print(rows)

        # selects back no rows
        rows = select_inventory_by_source(conn, "nosourceidhere")
        print(rows)

        # # can't recreate existing item: sqlite3.IntegrityError: UNIQUE constraint failed: ap_feed_inventory.arc_id
        # invenory = (
        #     "mysourceid1",
        #     "ABC123",
        #     "",
        #     "",
        #     "",
        #     arrow.utcnow().format("YYYY-MM-DD HH:MM:SS.SSS"),
        # )
        # item = create_inventory(conn, invenory)
