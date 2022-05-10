from flask import Flask, make_response

app = Flask(__name__)


@app.route("/api/ap/one", methods=["GET"])
def handle_ap_wire():
    res = make_response({"message": "hello"})
    return res


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True, threaded=True)
