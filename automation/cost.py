"""Estimate what this session's model usage would cost at Anthropic API list prices.

The human runs me on a subscription, so no cash changes hands per token; this is an
"API-equivalent" figure. Reads Claude Code transcripts (~/.claude/projects/-work/*.jsonl), which
are wiped when the container exits, so run this at the END of every session; it upserts one line
per session into /work/log/costs.jsonl. Slight undercount: the final reply isn't written yet.

Prices in $/million tokens (checked 2026-11-11 against Anthropic's model table, cached 2026-11-03):
"""
import glob
import json
import os
import pathlib

PRICES = {  # input, output, cache_read, cache_write_5m, cache_write_1h
    "claude-fable-5-2": (8, 40, 0.20, 10, 16),
    "claude-opus-5-5": (4, 20, 0.20, 5, 8),
    "claude-sonnet-5-5": (2, 10, 0.10, 2.5, 4),
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125, 0.20),
}
OUT = pathlib.Path("/work/log/costs.jsonl")


def session_cost(path):
    msgs = {}
    for line in open(path):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        m = r.get("message") or {}
        if m.get("usage") and m.get("id"):
            msgs[m["id"]] = (m.get("model"), m["usage"], r.get("timestamp"))
    by_model, total, first, last = {}, 0.0, None, None
    for model, u, ts in msgs.values():
        if model not in PRICES:
            by_model.setdefault(model or "unknown", {"calls": 0, "usd": None})["calls"] += 1
            continue
        pi, po, pr, w5, w1 = PRICES[model]
        cc = u.get("cache_creation") or {}
        c1 = cc.get("ephemeral_1h_input_tokens", 0)
        c5 = cc.get("ephemeral_5m_input_tokens", u.get("cache_creation_input_tokens", 0) - c1)
        usd = (
            u.get("input_tokens", 0) * pi + u.get("output_tokens", 0) * po
            + u.get("cache_read_input_tokens", 0) * pr + c5 * w5 + c1 * w1
        ) / 1e6
        b = by_model.setdefault(model, {"calls": 0, "usd": 0.0, "output_tokens": 0})
        b["calls"] += 1
        b["usd"] = round(b["usd"] + usd, 4)
        b["output_tokens"] += u.get("output_tokens", 0)
        total += usd
        if ts:
            first, last = min(first or ts, ts), max(last or ts, ts)
    return {"session": pathlib.Path(path).stem, "first": first, "last": last,
            "usd_api_equiv": round(total, 2), "by_model": by_model}


def main():
    rows = {}
    if OUT.exists():
        rows = {r["session"]: r for r in map(json.loads, OUT.read_text().splitlines()) if r}
    for p in glob.glob(os.path.expanduser("~/.claude/projects/-work/*.jsonl")):
        r = session_cost(p)
        rows[r["session"]] = r
        print(json.dumps(r))
    OUT.write_text("".join(json.dumps(r) + "\n" for r in rows.values()))
    print("total across recorded sessions: $%.2f" % sum(r["usd_api_equiv"] for r in rows.values()))


if __name__ == "__main__":
    main()
