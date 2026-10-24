"""Build the Toronto Tech Events page from events/events.json.

Usage: python3 -I events/build_page.py [--out events/toronto-tech-events.html]

Drops events that have already happened, then fills events/page_template.html.
"""
import argparse
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
TZ = ZoneInfo("America/Toronto")


def short(d):
    return datetime.strptime(d, "%Y-%m-%d").strftime("%b %-d")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "toronto-tech-events.html"))
    a = ap.parse_args()
    today = datetime.now(TZ).date().isoformat()
    events = [e for e in json.load(open(os.path.join(HERE, "events.json"))) if e["date"] >= today]
    events.sort(key=lambda e: (e["date"], datetime.strptime(e["time"], "%I:%M %p").time() if e["time"] else 0))
    data = [{
        "d": e["date"], "t": e["time"], "n": e["name"], "v": e.get("venue", ""), "u": e["url"],
        "x": ", ".join(e.get("x_handles") or []), "c": e.get("category", ""), "w": bool(e.get("pick")),
        "y": e.get("why", ""), "p": e.get("price", ""), "s": ", ".join(e.get("sources") or []),
    } for e in events]
    page = open(os.path.join(HERE, "page_template.html")).read()
    page = (page
            .replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__RANGE__", f"{short(events[0]['date'])} – {short(events[-1]['date'])}" if events else "")
            .replace("__COUNT__", str(len(events)))
            .replace("__UPDATED__", datetime.now(TZ).strftime("%b %-d, %Y")))
    open(a.out, "w").write(page)
    print(f"wrote {len(events)} events to {a.out}")


if __name__ == "__main__":
    main()
