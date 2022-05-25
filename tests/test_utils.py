from utils.arc_id import generate_arc_id


def test_arc_id():
    assert generate_arc_id(("abc123")) == "K7MUMMS7VF7S24QQK6CBUHD274"
    assert generate_arc_id(("abc123", "myorg")) == "2RW5JYT4YTKA4CZY6P4CZT6LMQ"
    assert generate_arc_id(("123", "myorg")) == "KQF3BQE3SW26QXPIJFGYUC7TSM"
    assert generate_arc_id((123, "myorg")) == "22LQ4EK6ODJ3U3U5DRHUSQIREM"
