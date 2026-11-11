import shlex
from flask import Flask, request

app = Flask(__name__)


@app.route("/hello")
def hello():
    return shlex.quote(request.args.get("name", "").strip())
