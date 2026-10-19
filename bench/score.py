"""Score hand-labelled results: story-level novelty of Diffbot vs Brave+Serper."""
import json, re, sys
from difflib import SequenceMatcher
sys.path.insert(0, "bench"); import coverage as c

rows = json.load(open(sys.argv[1])); labels = {}
for line in open(sys.argv[2]):
    if line.startswith("#") or not line.strip(): continue
    parts = line.split(); ti = int(parts[0]); d = {}
    i = 1
    while i < len(parts):
        src = parts[i]; nxt = parts[i+1] if i+1 < len(parts) and parts[i+1] not in "bsd" else ""
        d[src] = nxt; i += 2 if nxt else 1
    labels[ti] = d

def tnorm(t): return re.sub(r"[^a-z0-9 ]", "", re.split(r" [|\-–·] ", t.lower())[0]).strip()
def same(a, b):
    if c.norm_url(a["url"]) == c.norm_url(b["url"]): return True
    ta, tb = tnorm(a["title"]), tnorm(b["title"])
    if min(len(ta), len(tb)) <= 15: return False
    close_len = min(len(ta), len(tb)) / max(len(ta), len(tb)) > 0.6
    return (close_len and (ta in tb or tb in ta)) or SequenceMatcher(None, ta, tb).ratio() > 0.8

tot = {s: {"N": 0, "E": 0, "X": 0} for s in "bsd"}; novel = novel_topics = bs_news = 0
per = []
for ti, r in enumerate(rows):
    it = r["runs"]["matched"]["items"]; L = labels[ti]
    lab = {s: list(zip(it[{"b":"brave","s":"serper","d":"diffbot"}[s]][:10], L.get(s, ""))) for s in "bsd"}
    assert all(len(lab[s]) == len(L.get(s, "")) for s in "bsd"), (ti, {s: (len(lab[s]), len(L.get(s,""))) for s in "bsd"})
    for s in "bsd":
        for _, l in lab[s]: tot[s][l] += 1
    others = [i for i, _ in lab["b"] + lab["s"]]
    others_news = [i for i, l in lab["b"] + lab["s"] if l == "N"]
    # distinct BS news stories
    bsn = []
    for i in others_news:
        if not any(same(i, j) for j in bsn): bsn.append(i)
    dn = [i for i, l in lab["d"] if l == "N"]
    dnov = []
    for i in dn:
        if not any(same(i, j) for j in others) and not any(same(i, j) for j in dnov): dnov.append(i)
    novel += len(dnov); bs_news += len(bsn); novel_topics += bool(dnov)
    per.append((r["topic"], len(bsn), len(dn), len(dnov)))
print(f"{'topic':32} {'B+S news stories':>16} {'D news':>6} {'D-only news':>11} {'+%':>6}")
for t, a, b, n in per:
    print(f"{t[:32]:32} {a:>16} {b:>6} {n:>11} {('+%d%%' % (100*n/a)) if a else 'inf':>6}")
print("\nlabel totals (N/E/X):", {s: tot[s] for s in tot})
print(f"Distinct B+S news stories: {bs_news}; Diffbot-only news stories: {novel} (+{100*novel/bs_news:.0f}%); topics with ≥1 Diffbot-only story: {novel_topics}/{len(rows)}")
