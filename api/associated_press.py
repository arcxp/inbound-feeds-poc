from flask import Flask, make_response
from apps import associated_press as ap
from utils.logger import get_logger

logger = get_logger()
app = Flask(__name__)


@app.route("/api/health", methods=["GET"])
def health():
    res = make_response({"message": "hello"})
    return res


@app.route("/api/ap/test", methods=["GET"])
def handle_ap_test():
    # this is the uri of one of the photos from a story's associations
    test = ap.fetch_feed(
        "https://api.ap.org/media/v/content/28514e83e96c483f8cbac9b3aaabadc4?qt=_dSwUXC5aF&et=1a1aza4c0&ai=95b07bc3a92191b0abea66f851983c59"
    )
    return test


@app.route("/api/ap", methods=["GET"])
def handle_ap_wire():
    # this process will likely take a long time, with no feedback to the browser while it is running.
    # logs will be written to terminal window. inventory database will be updated after every success, as well as in the logs.
    # failures will only be in the logs.

    wires = ap.run_ap_ingest_wires()
    res = make_response({"message": f"{len(wires)} wires processed into arc.  consult logs for details on errors and successes."})
    return res


if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", port=8080, debug=True, threaded=True)
