import sqlite3
from flask import Flask, request, jsonify

app = Flask(__name__)
db = sqlite3.connect("app.db", check_same_thread=False)


@app.route("/user")
def user():
    uid = request.args.get("id", "")
    cur = db.execute("SELECT name FROM users WHERE id = ?", (uid,))
    return jsonify(cur.fetchall())
