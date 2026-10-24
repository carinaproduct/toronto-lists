"""Show new candidates since the last run, and apply the decisions made about them.

  python3 -I events/review.py                 # list new candidates (likely-tech in full, the rest as titles)
  python3 -I events/review.py --apply D.json  # add kept events to events.json, mark every other new one reviewed

D.json is a list of the events to keep, each:
  {"key": "<candidate key>", "category": "AI|startups|VC|dev|product|data|design|other-tech",
   "pick": true|false, "why": "<one short sentence>", "x_handles": ["..."]}   # x_handles optional
Every other new candidate is added to reviewed.json so it is not shown again.
"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = lambda name: os.path.join(HERE, name)


def load():
    cand = json.load(open(P("candidates.json")))["events"]
    events = json.load(open(P("events.json")))
    reviewed = json.load(open(P("reviewed.json")))
    known = {e["key"] for e in events} | set(reviewed["keys"])
    new = [c for c in cand if c["key"] not in known]
    return cand, events, reviewed, new


def show():
    _, events, _, new = load()
    likely = [c for c in new if c["likely_tech"]]
    other = [c for c in new if not c["likely_tech"]]
    print(f"{len(new)} new candidates: {len(likely)} likely tech, {len(other)} other\n")
    print("=== LIKELY TECH (full detail) ===")
    for c in likely:
        flags = [f for f, on in (("SOLD OUT", c["sold_out"]), ("APPROVAL", c["approval"])) if on]
        print(f"\n[{c['key']}]\n{c['date']} {c['time']} | {c['name']} | {c['source']} | {c['price'] or ''} "
              f"| going: {c['guest_count'] or '-'} {' '.join(flags)}\n  venue: {c['venue']}\n  hosts: {', '.join(h for h in c['hosts'] if h)}"
              f" | X: {', '.join(c['x_handles'])}\n  {c['description'][:350].replace(chr(10), ' ')}")
    print("\n=== OTHER (titles only; keep any that are clearly tech) ===")
    for c in other:
        print(f"[{c['key']}] {c['date']} | {c['name']} | {', '.join(h for h in c['hosts'] if h)}")
    # Events already on the list whose candidate record changed date or time.
    by_key = {c["key"]: c for c in load()[0]}
    moved = [(e, by_key[e["key"]]) for e in events if e["key"] in by_key
             and (e["date"], e["time"]) != (by_key[e["key"]]["date"], by_key[e["key"]]["time"])]
    if moved:
        print("\n=== RESCHEDULED (fixed automatically by --apply) ===")
        for e, c in moved:
            print(f"{e['name']}: {e['date']} {e['time']} -> {c['date']} {c['time']}")


def apply(path):
    cand, events, reviewed, new = load()
    decisions = {d["key"]: d for d in json.load(open(path))}
    by_key = {c["key"]: c for c in cand}
    added = 0
    for c in new:
        d = decisions.get(c["key"])
        if not d and c["source"] == "buildersundays.ca":  # always on the list
            d = {"category": "startups", "pick": True, "why": c["description"][:200]}
        if not d:
            reviewed["keys"].append(c["key"])
            continue
        events.append({
            "key": c["key"], "date": c["date"], "time": c["time"], "name": c["name"], "venue": c["venue"],
            "url": c["url"], "x_handles": d.get("x_handles", c["x_handles"]), "category": d["category"],
            "pick": bool(d["pick"]), "why": d["why"], "price": c["price"], "sources": [c["source"]],
        })
        added += 1
    for e in events:  # keep dates and times current for events already on the list
        c = by_key.get(e["key"])
        if c:
            e["date"], e["time"] = c["date"], c["time"]
    events.sort(key=lambda e: e["date"])
    reviewed["keys"] = sorted(set(reviewed["keys"]))
    json.dump(events, open(P("events.json"), "w"), indent=1, ensure_ascii=False)
    json.dump(reviewed, open(P("reviewed.json"), "w"), indent=0)
    print(f"added {added}, marked {len(new) - added} reviewed, list now {len(events)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply")
    a = ap.parse_args()
    apply(a.apply) if a.apply else show()
