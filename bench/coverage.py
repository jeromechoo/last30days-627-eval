#!/usr/bin/env python3
"""Measure what Diffbot finds that Serper and Brave miss, on the same topics.

Runs the engine's own source functions (grounding.brave_search,
grounding.serper_search, diffbot.search_diffbot + parse_diffbot_response) over
one topic list and one date window, and applies each source's own in-window
date filter, so the numbers reflect what the pipeline would actually keep.

Two budgets:
  engine  - each source as shipped (Brave/Serper count=5, Diffbot depth=default)
  matched - every source capped at the same top-N after filtering (--n)

Keys come from the engine's normal config loader (env / ~/.config/last30days/.env).

Usage:
  python3 bench/coverage.py --topics bench/topics.txt --days 30 --n 10 --out bench/results
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "last30days" / "scripts"))

from lib import diffbot, env, grounding  # noqa: E402

TRACKING = re.compile(r"^(utm_|fbclid|gclid|mc_|ref$|ref_|cmpid|ito|ocid)", re.I)
STOP = {"the", "a", "an", "of", "and", "or", "in", "on", "for", "to", "vs", "with", "new"}


def norm_url(url: str) -> str:
    p = urlparse(url.strip())
    host = p.netloc.lower().removeprefix("www.").removeprefix("m.")
    query = urlencode([(k, v) for k, v in parse_qsl(p.query) if not TRACKING.match(k)])
    path = p.path.rstrip("/") or "/"
    return urlunparse(("", host, path, "", query, ""))


def domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.").removeprefix("m.")


def on_topic(item: dict, topic: str) -> bool:
    """Crude, source-neutral relevance check: every content word of the topic
    (or its stem) appears in the title or snippet."""
    hay = f"{item.get('title', '')} {item.get('snippet', '')}".lower()
    words = [w for w in re.findall(r"[a-z0-9]+", topic.lower()) if w not in STOP]
    return all(w[:5] in hay for w in words) if words else True


def run_source(name: str, topic: str, window: tuple[str, str], cfg: dict, count: int):
    """Return (raw_count, kept_items, seconds, error)."""
    t0 = time.monotonic()
    try:
        if name == "brave":
            # Call the API directly once so we can count raw (pre-date-filter) rows.
            items, _ = grounding.brave_search(topic, window, cfg["BRAVE_API_KEY"], count=count)
            raw = _last_raw.get("brave")
        elif name == "serper":
            items, _ = grounding.serper_search(topic, window, cfg["SERPER_API_KEY"], count=count)
            raw = _last_raw.get("serper")
        else:
            depth = "deep" if count > 5 else "default"
            resp = diffbot.search_diffbot(topic, window[0], window[1], depth=depth,
                                          token=cfg["DIFFBOT_API_KEY"])
            raw = len(resp.get("data") or [])
            items = diffbot.parse_diffbot_response(resp, window[0], window[1])
        return raw, items, time.monotonic() - t0, None
    except Exception as exc:  # keep going; record the failure
        return None, [], time.monotonic() - t0, f"{type(exc).__name__}: {exc}"


# Wrap http.request to observe how many rows each web API returned before the
# engine's date filter dropped undated / out-of-window results.
_last_raw: dict[str, int] = {}
_orig_request = grounding.http.request


def _spy_request(method, url, *a, **kw):
    data = _orig_request(method, url, *a, **kw)
    if "search.brave.com" in url:
        _last_raw["brave"] = len((data or {}).get("web", {}).get("results", []))
    elif "serper.dev" in url:
        _last_raw["serper"] = len((data or {}).get("organic", []))
    return data


grounding.http.request = _spy_request


def summarize(topic: str, by_src: dict[str, list[dict]], n: int | None) -> dict:
    sets, doms, ontopic = {}, {}, {}
    for src, items in by_src.items():
        items = items[:n] if n else items
        sets[src] = {norm_url(i["url"]) for i in items if i.get("url")}
        doms[src] = {domain(i["url"]) for i in items if i.get("url")}
        ontopic[src] = sum(on_topic(i, topic) for i in items)
    others = sets["brave"] | sets["serper"]
    other_doms = doms["brave"] | doms["serper"]
    db_only = sets["diffbot"] - others
    db_items = by_src["diffbot"][:n] if n else by_src["diffbot"]
    db_only_items = [i for i in db_items if norm_url(i["url"]) in db_only]
    return {
        "kept": {s: len(v) for s, v in sets.items()},
        "domains": {s: len(v) for s, v in doms.items()},
        "on_topic": ontopic,
        "union_brave_serper": len(others),
        "diffbot_only": len(db_only),
        "diffbot_only_on_topic": sum(on_topic(i, topic) for i in db_only_items),
        "diffbot_only_new_domains": len(doms["diffbot"] - other_doms),
        "brave_only": len(sets["brave"] - sets["serper"] - sets["diffbot"]),
        "serper_only": len(sets["serper"] - sets["brave"] - sets["diffbot"]),
        "overlap_all3": len(sets["brave"] & sets["serper"] & sets["diffbot"]),
        "diffbot_only_examples": [
            {k: i.get(k) for k in ("title", "url", "date", "source_domain")}
            for i in db_only_items[:5]
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", required=True)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument("--n", type=int, default=10, help="matched top-N budget")
    ap.add_argument("--out", default="bench/results")
    args = ap.parse_args()

    cfg = env.get_config()
    missing = [k for k in ("BRAVE_API_KEY", "SERPER_API_KEY", "DIFFBOT_API_KEY") if not cfg.get(k)]
    if missing:
        print(f"Missing keys: {', '.join(missing)}", file=sys.stderr)
        return 2

    end = date.fromisoformat(args.end)
    window = ((end - timedelta(days=args.days)).isoformat(), end.isoformat())
    topics = [t.strip() for t in Path(args.topics).read_text().splitlines()
              if t.strip() and not t.startswith("#")]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for topic in topics:
        rec = {"topic": topic, "window": window, "runs": {}}
        for budget, count in (("engine", 5), ("matched", args.n)):
            by_src, meta = {}, {}
            for src in ("brave", "serper", "diffbot"):
                raw, items, secs, err = run_source(src, topic, window, cfg, count)
                by_src[src] = items
                meta[src] = {"raw": raw, "kept": len(items), "secs": round(secs, 2), "error": err}
            rec["runs"][budget] = {
                "meta": meta,
                "items": by_src,
                "summary": summarize(topic, by_src, None if budget == "engine" else args.n),
            }
        rows.append(rec)
        s = rec["runs"]["matched"]["summary"]
        print(f"{topic[:40]:40}  kept B/S/D={s['kept']['brave']}/{s['kept']['serper']}/"
              f"{s['kept']['diffbot']}  D-only={s['diffbot_only']} "
              f"(on-topic {s['diffbot_only_on_topic']})", flush=True)

    (out / "raw.json").write_text(json.dumps(rows, indent=2))
    print(f"\nWrote {out / 'raw.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
