"""Unattended tick, run hourly by GitHub Actions from the repo root (no AI involved at run time).

1. Once per UTC day: append the account's public Bluesky counters to stats.jsonl.
2. Post at most one due item from queue/*.json ({"at": "2026-11-12T15:00:00Z", "text": "..."}),
   never more than 2 per UTC day, then move it to queue/sent/ with the post URI.
   Queue items are written in advance by Claude during a supervised session.
"""
import datetime
import json
import os
import pathlib
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
ACTOR = "unpaid-intern-ai.bsky.social"
now = datetime.datetime.now(datetime.timezone.utc)
today = now.strftime("%Y-%m-%d")

stats = pathlib.Path("stats.jsonl")
lines = stats.read_text().splitlines() if stats.exists() else []
if not any(json.loads(x)["date"] == today for x in lines if x):
    with urllib.request.urlopen(
        "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor=" + ACTOR, timeout=30
    ) as r:
        p = json.load(r)
    lines.append(json.dumps({"date": today, "at": now.strftime("%H:%MZ"), "followers": p["followersCount"],
                             "follows": p["followsCount"], "posts": p["postsCount"]}))
    stats.write_text("\n".join(lines) + "\n")
    print("stats:", lines[-1])

queue, sent = pathlib.Path("queue"), pathlib.Path("queue/sent")
sent.mkdir(parents=True, exist_ok=True)
sent_today = sum(1 for f in sent.glob("*.json") if json.loads(f.read_text()).get("sent_at", "")[:10] == today)
due = sorted(
    (json.loads(f.read_text())["at"], f) for f in queue.glob("*.json")
    if json.loads(f.read_text())["at"] <= now.strftime("%Y-%m-%dT%H:%M:%SZ")
)
if due and sent_today < 2:
    if not os.environ.get("BLUESKY_APP_PASSWORD"):
        print("queue: item due but no credentials configured; skipping")
    else:
        import bsky
        f = due[0][1]
        item = json.loads(f.read_text())
        item["uri"] = bsky.post(bsky.login(), item["text"])
        item["sent_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        (sent / f.name).write_text(json.dumps(item, indent=2) + "\n")
        f.unlink()
        print("queue: posted", f.name, item["uri"])
else:
    print(f"queue: nothing to post (due={len(due)}, sent_today={sent_today})")
