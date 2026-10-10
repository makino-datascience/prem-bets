"""Collect football headlines from public RSS feeds and save them as news.json.

Runs inside GitHub Actions with the table job. Each headline links back to the
original article; only the title, a short summary and the picture link are kept.
If a feed can't be read, the others still work.
"""
import datetime
import email.utils
import html
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

FEEDS = [
    # (source name, feed url, every story is Premier League?)
    ("Sky Sports", "https://www.skysports.com/rss/11661", True),
    ("Sky Sports", "https://www.skysports.com/rss/11095", False),
    ("FourFourTwo", "https://www.fourfourtwo.com/feeds/all", False),
]
OUT = os.path.join(os.path.dirname(__file__), "..", "news.json")
STANDINGS = os.path.join(os.path.dirname(__file__), "..", "standings.json")
KEEP = 80
MAX_AGE_DAYS = 4
UA = {"User-Agent": "Mozilla/5.0 (prem-bets news job)"}
NS = {"media": "http://search.yahoo.com/mrss/", "content": "http://purl.org/rss/1.0/modules/content/"}

# Extra names people use for Premier League clubs, on top of the names in standings.json.
EPL_WORDS = ["premier league", "man city", "man utd", "man united", "spurs", "villa", "forest",
             "the gunners", "the reds", "the blues", "toffees", "magpies", "seagulls", "cherries", "black cats"]


def epl_words():
    words = set(EPL_WORDS)
    try:
        with open(STANDINGS) as f:
            for t in json.load(f).get("teams", []):
                for n in (t.get("name"), t.get("shortName")):
                    n = re.sub(r"\b(A?FC)\b", "", n or "").replace("&", "and").strip().lower()
                    n = re.sub(r"\s+", " ", n)
                    if len(n) > 3:
                        words.add(n)
    except (FileNotFoundError, ValueError):
        pass
    return sorted(words)


def clean(text, limit=None):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    if limit and len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "…"
    return text


def image_of(item):
    enc = item.find("enclosure")
    if enc is not None and (enc.get("type") or "").startswith("image") and enc.get("url"):
        return enc.get("url")
    for tag in ("media:content", "media:thumbnail"):
        for el in item.findall(tag, NS):
            if el.get("url") and (el.get("medium") in (None, "image") or (el.get("type") or "").startswith("image")):
                return el.get("url")
    for tag in ("description", "content:encoded"):
        el = item.find(tag, NS)
        if el is not None and el.text:
            m = re.search(r'<img[^>]+src="([^"]+)"', el.text)
            if m:
                return html.unescape(m.group(1))
    return None


def read_feed(source, url, all_epl, words):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        root = ET.fromstring(resp.read())
    items = []
    for it in root.iter("item"):
        title = clean(it.findtext("title"))
        link = (it.findtext("link") or "").strip()
        if not title or not link.startswith("http"):
            continue
        try:
            when = email.utils.parsedate_to_datetime(it.findtext("pubDate") or "")
            if when.tzinfo is None:
                when = when.replace(tzinfo=datetime.timezone.utc)
        except (TypeError, ValueError):
            continue
        summary = clean(it.findtext("description"), 220)
        text = (title + " " + summary).lower()
        items.append({
            "title": title,
            "summary": summary,
            "url": link,
            "image": image_of(it),
            "source": source,
            "published": when.astimezone(datetime.timezone.utc).isoformat(timespec="seconds"),
            "epl": all_epl or any(re.search(r"\b" + re.escape(w) + r"\b", text) for w in words),
        })
    return items


def key(title):
    return re.sub(r"[^a-z0-9]", "", title.lower())[:60]


def main():
    words = epl_words()
    found = {}
    for source, url, all_epl in FEEDS:
        try:
            items = read_feed(source, url, all_epl, words)
            print(f"{source} ({url}): {len(items)} stories")
        except Exception as e:
            print(f"{source} ({url}): couldn't read it ({e})")
            continue
        for item in items:
            k = key(item["title"])
            if k in found:
                found[k]["epl"] = found[k]["epl"] or item["epl"]
                found[k]["image"] = found[k]["image"] or item["image"]
            else:
                found[k] = item

    if not found:
        print("No feeds could be read; keeping the old news.")
        return

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=MAX_AGE_DAYS)
    items = [i for i in found.values() if datetime.datetime.fromisoformat(i["published"]) >= cutoff]
    items.sort(key=lambda i: i["published"], reverse=True)
    items = items[:KEEP]

    try:
        with open(OUT) as f:
            if json.load(f).get("items") == items:
                print("News unchanged.")
                return
    except (FileNotFoundError, ValueError):
        pass

    with open(OUT, "w") as f:
        json.dump({"updatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                   "items": items}, f, indent=1, ensure_ascii=False)
    print(f"Saved {len(items)} stories ({sum(i['epl'] for i in items)} Premier League).")


if __name__ == "__main__":
    main()
