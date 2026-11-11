from flask import Flask, request

app = Flask(__name__)


@app.route("/hello")
def hello():
    return request.args.get("name", "").strip()
