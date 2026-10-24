"""Collect raw Toronto tech-event candidates from public sources.

Usage: python3 -I events/collect.py [--days 42] [--out events/candidates.json]

Sources (all public, no login):
  - Luma location feed around downtown Toronto (all, tech and AI categories),
    then each event's detail record for venue, hosts and ticket info.
  - Eventbrite Toronto browse pages for a set of tech keywords.
  - Meetup GraphQL event search around Toronto.
  - Shopify Builder Sundays (Toronto) dates from buildersundays.ca.

The output is unfiltered: deciding what is tech-relevant and worth going to is
done afterwards (see events/README.md).
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Toronto")
HERE = __import__("os").path.dirname(__import__("os").path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (toronto-lists event collector)"}
TORONTO = (43.6532, -79.3832)
GTA = re.compile(
    r"toronto|mississauga|brampton|markham|vaughan|richmond hill|oakville|scarborough|"
    r"north york|etobicoke|pickering|ajax|whitby|oshawa|burlington|milton|newmarket",
    re.I,
)
EVENTBRITE_KEYWORDS = [
    "science-and-tech--events", "tech-events", "artificial-intelligence", "ai", "generative-ai",
    "ai-agents", "agentic-ai", "llm", "machine-learning", "data-science", "data-engineering",
    "developer", "python", "javascript", "cloud-computing", "aws", "open-source", "hackathon",
    "startup", "founders", "entrepreneurship", "venture-capital", "pitch-competition", "demo-day",
    "product-management", "product", "product-marketing", "growth-marketing", "b2b-marketing",
    "marketing-technology", "saas", "fintech", "design-thinking", "robotics", "cybersecurity",
]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def fetch(url, data=None, headers=None, tries=3):
    h = dict(UA, **(headers or {}))
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # network hiccups and 429s: back off and retry
            if i == tries - 1:
                log("  fetch failed:", url[:120], e)
                return None
            time.sleep(2 * (i + 1))


def local(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ)


def tiptap_text(node):
    """Flatten Luma's rich-text description into plain text."""
    if isinstance(node, dict):
        own = node.get("text") or ""
        kids = "".join(tiptap_text(c) for c in node.get("content") or [])
        brk = "\n" if node.get("type") in ("paragraph", "heading", "listItem", "list_item") else ""
        return own + kids + brk
    if isinstance(node, list):
        return "".join(tiptap_text(c) for c in node)
    return ""


# ---------------------------------------------------------------- Luma
def luma(start, end):
    slugs = {}
    for cat in (None, "cat-tech", "cat-ai"):
        cursor, pages = None, 0
        while pages < 40:
            q = {"latitude": TORONTO[0], "longitude": TORONTO[1], "pagination_limit": 50}
            if cat:
                q["discover_category_api_id"] = cat
            if cursor:
                q["pagination_cursor"] = cursor
            body = fetch("https://api.lu.ma/discover/get-paginated-events?" + urllib.parse.urlencode(q))
            if not body:
                break
            d = json.loads(body)
            for x in d.get("entries", []):
                ev = x.get("event") or {}
                if ev.get("url") and start <= local(ev["start_at"]).date() <= end:
                    slugs[ev["url"]] = x.get("guest_count")
            pages += 1
            if not d.get("has_more"):
                break
            cursor = d.get("next_cursor")
    # Calendars on the watch-list catch events the location feed leaves out.
    for line in open(HERE + "/luma_calendars.txt"):
        cid = line.split("#", 1)[0].split()[0] if line.split("#", 1)[0].strip() else None
        if not cid:
            continue
        body = fetch(f"https://api.lu.ma/calendar/get-items?calendar_api_id={cid}&period=future&pagination_limit=100")
        for x in (json.loads(body).get("entries", []) if body else []):
            ev = x.get("event") or {}
            if ev.get("url") and start <= local(ev["start_at"]).date() <= end:
                slugs.setdefault(ev["url"], x.get("guest_count"))
    log(f"Luma: {len(slugs)} events in range, fetching details")

    def detail(slug):
        body = fetch("https://api.lu.ma/url?url=" + urllib.parse.quote(slug))
        if not body:
            return None
        try:
            d = json.loads(body)["data"]
        except Exception:
            return None
        ev = d["event"]
        geo = ev.get("geo_address_info") or {}
        where = " ".join(str(geo.get(k) or "") for k in ("full_address", "address", "city", "city_state"))
        if ev.get("location_type") != "offline" or not GTA.search(where):
            return None
        st = local(ev["start_at"])
        ti = d.get("ticket_info") or {}
        cal = d.get("calendar") or {}
        hosts = d.get("hosts") or []
        return {
            "source": "Luma",
            "date": st.strftime("%Y-%m-%d"),
            "time": st.strftime("%-I:%M %p"),
            "name": ev["name"],
            "venue": geo.get("full_address") or geo.get("address") or geo.get("city_state") or "",
            "url": "https://luma.com/" + slug,
            "hosts": [h["name"] for h in hosts if h.get("name")] + ([cal["name"]] if cal.get("name") and not cal.get("is_personal") else []),
            "x_handles": sorted({h.get("twitter_handle") for h in hosts if h.get("twitter_handle")}
                                | ({cal["twitter_handle"]} if cal.get("twitter_handle") else set())),
            "guest_count": d.get("guest_count") or slugs.get(slug),
            "price": "Free" if ti.get("is_free") else "",
            "sold_out": bool(ti.get("is_sold_out")),
            "approval": bool(ti.get("require_approval")),
            "description": tiptap_text(d.get("description_mirror") or {})[:1200].strip(),
        }

    with ThreadPoolExecutor(8) as ex:
        out = [r for r in ex.map(detail, slugs) if r]
    log(f"Luma: {len(out)} in-person GTA events")
    return out


# ---------------------------------------------------------- Eventbrite
def _find_eb_events(o, out):
    if isinstance(o, dict):
        if "start_date" in o and "name" in o and ("url" in o or "id" in o):
            out.append(o)
        for v in o.values():
            _find_eb_events(v, out)
    elif isinstance(o, list):
        for v in o:
            _find_eb_events(v, out)


def eventbrite(start, end):
    found = {}
    for kw in EVENTBRITE_KEYWORDS:
        for page in range(1, 6):
            body = fetch(f"https://www.eventbrite.ca/d/canada--toronto/{kw}/?page={page}")
            m = body and re.search(r"window\.__SERVER_DATA__ = (\{.*?\});\s*\n", body, re.S)
            if not m:
                break
            evs = []
            try:
                _find_eb_events(json.loads(m.group(1)), evs)
            except Exception:
                break
            new = 0
            for e in evs:
                if e.get("is_online_event") or not e.get("start_date"):
                    continue
                if not (start.isoformat() <= e["start_date"] <= end.isoformat()):
                    continue
                pv = e.get("primary_venue") or {}
                addr = (pv.get("address") or {}).get("localized_address_display") or ""
                if not GTA.search(addr + " " + str((pv.get("address") or {}).get("city"))):
                    continue
                url = (e.get("url") or "").split("?")[0]
                if url in found:
                    continue
                tc = e.get("ticket_availability") or {}
                lo = (tc.get("minimum_ticket_price") or {}).get("display")
                hi = (tc.get("maximum_ticket_price") or {}).get("display")
                t = datetime.strptime(e.get("start_time") or "00:00", "%H:%M")
                found[url] = {
                    "source": "Eventbrite",
                    "date": e["start_date"],
                    "time": t.strftime("%-I:%M %p"),
                    "name": e["name"],
                    "venue": ", ".join(x for x in (pv.get("name"), addr) if x),
                    "url": url,
                    "hosts": [(e.get("primary_organizer") or {}).get("name") or ""],
                    "x_handles": [],
                    "guest_count": None,
                    "price": "Free" if tc.get("is_free") else (lo if lo == hi else f"{lo}–{hi}" if lo else ""),
                    "sold_out": bool(tc.get("is_sold_out")),
                    "approval": False,
                    "description": (e.get("summary") or "")[:600],
                }
                new += 1
            if not new and page > 1:
                break
    log(f"Eventbrite: {len(found)} in-person GTA events")
    return list(found.values())


# --------------------------------------------------------------- Meetup
MEETUP_GQL = """query($filter: EventSearchFilter!, $first: Int, $after: String){ eventSearch(filter:$filter, first:$first, after:$after, sort:{sortField: DATETIME}){ pageInfo{hasNextPage endCursor} edges{ node{ title dateTime eventUrl eventType description group{ name urlname topicCategory{ name } } venue{ name address city state } rsvps{ totalCount } feeSettings{ amount currency } } } } }"""
# eventSearch needs a non-empty query (category filters return nothing), and matches fuzzily.
MEETUP_KEYWORDS = [
    "tech", "AI", "artificial intelligence", "machine learning", "LLM", "agents", "data", "developer",
    "software", "python", "javascript", "cloud", "AWS", "Azure", "devops", "startup", "founders",
    "venture capital", "product management", "product", "UX design", "hackathon", "open source",
]


def meetup(start, end):
    found = {}
    for kw in MEETUP_KEYWORDS:
        after = None
        for _ in range(10):
            variables = {"filter": {"lat": TORONTO[0], "lon": TORONTO[1], "radius": 40, "eventType": "PHYSICAL",
                                    "startDateRange": f"{start.isoformat()}T00:00:00-05:00[US/Eastern]",
                                    "endDateRange": f"{end.isoformat()}T23:59:00-05:00[US/Eastern]",
                                    "doConsolidateEvents": False, "query": kw},
                         "first": 100, "after": after}
            body = fetch("https://www.meetup.com/gql2", data=json.dumps({"query": MEETUP_GQL, "variables": variables}).encode(),
                         headers={"Content-Type": "application/json"})
            if not body:
                break
            res = (json.loads(body).get("data") or {}).get("eventSearch") or {}
            for edge in res.get("edges") or []:
                n = edge["node"]
                v = n.get("venue") or {}
                where = " ".join(str(v.get(k) or "") for k in ("address", "city"))
                if n.get("eventType") != "PHYSICAL" or (where.strip() and not GTA.search(where)):
                    continue
                url = n["eventUrl"]
                if url in found:
                    continue
                st = datetime.fromisoformat(n["dateTime"]).astimezone(TZ)
                fee = n.get("feeSettings") or {}
                g = n.get("group") or {}
                found[url] = {
                    "source": "Meetup",
                    "date": st.strftime("%Y-%m-%d"),
                    "time": st.strftime("%-I:%M %p"),
                    "name": n["title"],
                    "venue": ", ".join(x for x in (v.get("name"), v.get("address"), v.get("city")) if x),
                    "url": url,
                    "hosts": [g.get("name") or ""],
                    "group_category": (g.get("topicCategory") or {}).get("name"),
                    "x_handles": [],
                    "guest_count": (n.get("rsvps") or {}).get("totalCount"),
                    "price": f"{fee['amount']} {fee.get('currency', '')}".strip() if fee.get("amount") else "",
                    "sold_out": False,
                    "approval": False,
                    "description": (n.get("description") or "")[:800],
                }
            page = res.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            after = page.get("endCursor")
    # Groups on the watch-list, 15 per request via aliases.
    groups = [l.split("#", 1)[0].strip() for l in open(HERE + "/meetup_groups.txt")]
    groups = [g for g in groups if g]
    fields = ("name events(status: ACTIVE, first: 30, filter:{afterDateTime:\"%sT00:00:00-05:00\", beforeDateTime:\"%sT23:59:00-05:00\"})"
              "{ edges{ node{ title dateTime eventType eventUrl description venue{ name address city state } rsvps{ totalCount } feeSettings{ amount currency } } } }"
              % (start.isoformat(), end.isoformat()))
    for i in range(0, len(groups), 15):
        q = "{ " + " ".join(f'g{j}: groupByUrlname(urlname:"{u}"){{ {fields} }}' for j, u in enumerate(groups[i:i + 15])) + " }"
        body = fetch("https://www.meetup.com/gql2", data=json.dumps({"query": q}).encode(), headers={"Content-Type": "application/json"})
        for g in ((json.loads(body).get("data") or {}).values() if body else []):
            for edge in ((g or {}).get("events") or {}).get("edges") or []:
                n = edge["node"]
                v = n.get("venue") or {}
                if n.get("eventType") != "PHYSICAL" or n["eventUrl"] in found:
                    continue
                st = datetime.fromisoformat(n["dateTime"]).astimezone(TZ)
                fee = n.get("feeSettings") or {}
                found[n["eventUrl"]] = {
                    "source": "Meetup", "date": st.strftime("%Y-%m-%d"), "time": st.strftime("%-I:%M %p"),
                    "name": n["title"], "venue": ", ".join(x for x in (v.get("name"), v.get("address"), v.get("city")) if x),
                    "url": n["eventUrl"], "hosts": [g.get("name") or ""], "group_category": "Technology", "x_handles": [],
                    "guest_count": (n.get("rsvps") or {}).get("totalCount"),
                    "price": f"{fee['amount']} {fee.get('currency', '')}".strip() if fee.get("amount") else "",
                    "sold_out": False, "approval": False, "description": (n.get("description") or "")[:800],
                }
    log(f"Meetup: {len(found)} in-person GTA events")
    return list(found.values())


# ----------------------------------------------------- Builder Sundays
def builder_sundays(start, end):
    body = fetch("https://buildersundays.ca/products/toronto.json")
    if not body:
        return []
    text = html.unescape(re.sub(r"<[^>]+>", " ", json.loads(body)["product"]["body_html"]))
    text = re.sub(r"\s+", " ", text)
    # e.g. "October 25 November 1, 8, 15 & 22 December 6 & 13" plus "back on Jan 10, 2027"
    months = {m: i for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july", "august",
         "september", "october", "november", "december"], 1)}
    upcoming = text.split("Upcoming Dates", 1)[-1].split("off", 1)[0]
    dates = set()
    for mname, nums in re.findall(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+([\d,&\s]+)", upcoming):
        for n in re.findall(r"\d{1,2}", nums):
            for yr in (start.year, start.year + 1):
                try:
                    d = date(yr, months[mname.lower()], int(n))
                except ValueError:
                    continue
                if d.weekday() == 6 and start <= d <= end:
                    dates.add(d)
    out = [{
        "source": "buildersundays.ca",
        "date": d.isoformat(),
        "time": "12:00 PM",
        "name": "Builder Sundays at Shopify",
        "venue": "Shopify Toronto, 620 King St W (10th floor, enter off Waterloo Terrace)",
        "url": "https://buildersundays.ca/products/toronto",
        "hosts": ["Shopify"],
        "x_handles": ["Shopify"],
        "guest_count": None,
        "price": "",
        "sold_out": False,
        "approval": False,
        "description": "12-5 PM co-working for builders at Shopify. Spots release Wednesdays at 12 PM ET for the following Sunday. Schedule: " + upcoming.strip()[:300],
    } for d in sorted(dates)]
    log(f"Builder Sundays: {len(out)} dates")
    return out


TECH = re.compile(
    r"\b(ai|a\.i\.|artificial intelligence|machine learning|ml|llms?|gpt|claude|agent(ic|s)?|data|developers?|dev|"
    r"software|engineer(ing|s)?|code|coding|python|javascript|cloud|aws|azure|gcp|devops|saas|startups?|founders?|"
    r"vc|venture|investors?|pitch|demo day|hackathon|product|ux|design|tech|fintech|crypto|web3|blockchain|robotics|"
    r"quantum|cyber|security|open source|api|gtm|growth|marketing tech|automation|digital)\b",
    re.I,
)


def canonical_url(url):
    """Same event, same key: Eventbrite IDs across .ca/.com, no query strings or trailing slashes."""
    m = re.search(r"eventbrite\.[a-z.]+/e/.*?(\d{9,})", url)
    if m:
        return "eventbrite:" + m.group(1)
    return url.split("?")[0].rstrip("/").replace("https://lu.ma/", "https://luma.com/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=42)
    ap.add_argument("--out", default="events/candidates.json")
    a = ap.parse_args()
    start = datetime.now(TZ).date()
    end = start + timedelta(days=a.days)
    rows = []
    for fn in (builder_sundays, luma, eventbrite, meetup):
        try:
            rows += fn(start, end)
        except Exception as e:  # one broken source should not sink the run
            log(f"{fn.__name__} failed: {e!r}")
    for r in rows:
        r["key"] = canonical_url(r["url"])
        if r["source"] == "buildersundays.ca":  # one shared link for every date
            r["key"] += "#" + r["date"]
        r["likely_tech"] = bool(TECH.search(" ".join([r["name"], r["description"][:400], " ".join(h for h in r["hosts"] if h),
                                                      r.get("group_category") or ""])))
    rows.sort(key=lambda r: (r["date"], datetime.strptime(r["time"], "%I:%M %p").time(), r["name"]))
    json.dump({"collected_at": datetime.now(TZ).isoformat(timespec="minutes"), "start": start.isoformat(),
               "end": end.isoformat(), "events": rows}, open(a.out, "w"), indent=1, ensure_ascii=False)
    log(f"wrote {len(rows)} candidates to {a.out}")


if __name__ == "__main__":
    main()
