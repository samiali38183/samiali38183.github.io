import shlex
from flask import Flask, request

app = Flask(__name__)


@app.route("/hello")
def hello():
    name = shlex.quote(request.args.get("name", "").strip())
    return name
