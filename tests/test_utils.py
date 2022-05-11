from utils.arc_id import generate_arc_id


def test_arc_id():
    assert generate_arc_id(("abc123")) == "K7MUMMS7VF7S24QQK6CBUHD274"
