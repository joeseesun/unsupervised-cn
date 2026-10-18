#!/usr/bin/env python3
"""Parse official podcast RSS feeds into normalized episodes.json per podcast."""
import json
import re
import html
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from email.utils import parsedate_to_datetime

BASE = Path(__file__).resolve().parent.parent / "data"

ITUNES_NS = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}
ITUNES_NS_ALT = {"itunes": "http://www.itunes.com/dtds/podcast-1.0"}


def find_itunes(el, tag):
    v = el.findtext(f"itunes:{tag}", namespaces=ITUNES_NS)
    if v is None:
        v = el.findtext(f"itunes:{tag}", namespaces=ITUNES_NS_ALT)
    return v


def find_itunes_el(el, tag):
    v = el.find(f"itunes:{tag}", ITUNES_NS)
    if v is None:
        v = el.find(f"itunes:{tag}", ITUNES_NS_ALT)
    return v


def clean_text(s: str) -> str:
    if not s:
        return ""
    # RSS descriptions often contain HTML
    s = re.sub(r"<script.*?</script>", "", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", "", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</p>\s*<p[^>]*>", "\n\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def parse_duration(v) -> int:
    if v is None:
        return 0
    v = str(v).strip()
    if not v:
        return 0
    if ":" in v:
        parts = [int(x) for x in v.split(":")]
        while len(parts) < 3:
            parts.insert(0, 0)
        h, m, s = parts[-3:]
        return h * 3600 + m * 60 + s
    try:
        return int(float(v))
    except ValueError:
        return 0


def parse_feed(slug: str):
    feed_path = BASE / slug / "feed.xml"
    tree = ET.parse(feed_path)
    root = tree.getroot()
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError(f"{slug}: no channel in feed")

    show = {
        "title": (channel.findtext("title") or "").strip(),
        "description": clean_text(channel.findtext("description") or ""),
        "link": (channel.findtext("link") or "").strip(),
        "image": "",
        "author": (channel.findtext("itunes:author", namespaces=ITUNES_NS) or "").strip(),
    }
    it_image = find_itunes_el(channel, "image")
    if it_image is not None:
        show["image"] = it_image.get("href", "")

    episodes = []
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        try:
            date = parsedate_to_datetime(pub).date().isoformat()
        except Exception:
            date = ""
        desc = clean_text(item.findtext("description") or "")
        dur = parse_duration(find_itunes(item, "duration"))
        epnum = find_itunes(item, "episode")
        enc = item.find("enclosure")
        audio = enc.get("url") if enc is not None else ""
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        img = ""
        itimg = find_itunes_el(item, "image")
        if itimg is not None:
            img = itimg.get("href", "")
        episodes.append(
            {
                "id": guid or link or title,
                "title": title,
                "date": date,
                "duration": dur,
                "description": desc,
                "audio": audio,
                "link": link,
                "image": img,
                "epnum": int(epnum) if epnum and epnum.isdigit() else None,
                "ytId": None,
            }
        )

    # newest first
    episodes.sort(key=lambda e: e["date"] or "", reverse=True)
    out = {"slug": slug, "show": show, "episodes": episodes}
    dst = BASE / slug / "episodes.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{slug}: {len(episodes)} episodes -> {dst}")


if __name__ == "__main__":
    for slug in sys.argv[1:] or ["nopriors", "cogrev", "trainingdata", "unsupervised"]:
        parse_feed(slug)
