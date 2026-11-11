"""Bluesky helper for the persona account. Stdlib only.
Credentials: BLUESKY_HANDLE / BLUESKY_APP_PASSWORD from the environment, else ../.env.

  uv run --no-project python tools/bsky.py stats
  uv run --no-project python tools/bsky.py post "text with https://links"   (links become clickable)
  uv run --no-project python tools/bsky.py notifs
  uv run --no-project python tools/bsky.py follow handle1 handle2 ...   (rule: <=10/day, log each with a reason)
"""
import datetime
import json
import os
import pathlib
import re
import sys
import urllib.request

_env = pathlib.Path(__file__).resolve().parent.parent / ".env"
ENV = dict(
    line.strip().split("=", 1)
    for line in (_env.read_text().splitlines() if _env.exists() else [])
    if "=" in line and not line.startswith("#")
)
ENV.update({k: v for k, v in os.environ.items() if k.startswith("BLUESKY_") and v})
PDS = "https://bsky.social/xrpc/"


def call(method, data=None, token=None, params=""):
    req = urllib.request.Request(PDS + method + params)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode()
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def login():
    return call(
        "com.atproto.server.createSession",
        {"identifier": ENV["BLUESKY_HANDLE"].strip(), "password": ENV["BLUESKY_APP_PASSWORD"].strip()},
    )


def facets(text):
    out = []
    for m in re.finditer(r"https?://[^\s)]+", text):
        start = len(text[: m.start()].encode())
        out.append(
            {
                "index": {"byteStart": start, "byteEnd": start + len(m.group().encode())},
                "features": [{"$type": "app.bsky.richtext.facet#link", "uri": m.group()}],
            }
        )
    return out


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def post(s, text):
    if len(text) > 300:
        sys.exit(f"too long: {len(text)} > 300")
    rec = {"$type": "app.bsky.feed.post", "text": text, "createdAt": now(), "langs": ["en"], "facets": facets(text)}
    r = call(
        "com.atproto.repo.createRecord",
        {"repo": s["did"], "collection": "app.bsky.feed.post", "record": rec},
        token=s["accessJwt"],
    )
    return r["uri"]


def main():
    cmd = sys.argv[1]
    s = login()
    if cmd == "stats":
        p = call("app.bsky.actor.getProfile", token=s["accessJwt"], params="?actor=" + s["did"])
        print(json.dumps({k: p.get(k) for k in ("handle", "followersCount", "followsCount", "postsCount")}))
    elif cmd == "notifs":
        n = call("app.bsky.notification.listNotifications", token=s["accessJwt"], params="?limit=30")
        for x in n["notifications"]:
            print(x["indexedAt"], x["reason"], x["author"]["handle"], (x["record"].get("text") or "")[:200])
        print(f"{len(n['notifications'])} notifications")
    elif cmd == "follow":
        for h in sys.argv[2:]:
            p = call("app.bsky.actor.getProfile", token=s["accessJwt"], params="?actor=" + h)
            if p.get("viewer", {}).get("following"):
                print("already following", h)
                continue
            rec = {"$type": "app.bsky.graph.follow", "subject": p["did"], "createdAt": now()}
            call(
                "com.atproto.repo.createRecord",
                {"repo": s["did"], "collection": "app.bsky.graph.follow", "record": rec},
                token=s["accessJwt"],
            )
            print("followed", h, p["did"])
    elif cmd == "post":
        print(post(s, sys.argv[2]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
