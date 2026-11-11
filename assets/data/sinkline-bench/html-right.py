from flask import Flask, request
from markupsafe import escape

app = Flask(__name__)


@app.route("/hello")
def hello():
    return escape(request.args.get("name", "").strip())
