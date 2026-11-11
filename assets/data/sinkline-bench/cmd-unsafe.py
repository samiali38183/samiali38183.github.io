import subprocess
from flask import Flask, request

app = Flask(__name__)


@app.route("/ping")
def ping():
    try:
        host = request.args["h"]
    except KeyError:
        host = "localhost"
    subprocess.run("ping -c 1 " + host, shell=True)
    return "sent"
