#!/usr/bin/env python3
"""Merge YouTube flat-playlist data into episodes.json by fuzzy title matching."""
import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data"

STOP = {
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "with",
    "is", "at", "by", "from", "ep", "episode", "podcast", "video", "official",
    "ft", "feat", "featuring", "vs", "w", "interview", "full",
}


def norm_title(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    words = [w for w in s.split() if w and w not in STOP]
    return " ".join(words)


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def merge(slug: str):
    pdir = BASE / slug
    data = json.loads((pdir / "episodes.json").read_text())
    yt = json.loads((pdir / "yt_flat.json").read_text())
    vids = [v for v in (yt.get("entries") or []) if v.get("id")]

    used = set()
    matched = 0
    for ep in data["episodes"]:
        nt = norm_title(ep["title"])
        best, best_score = None, 0.0
        for v in vids:
            if v["id"] in used:
                continue
            vt = norm_title(v.get("title") or "")
            if not nt or not vt:
                continue
            score = similarity(nt, vt)
            # bonus if one contains the other (long official vs YT titles)
            if nt and vt and (nt in vt or vt in nt):
                score = max(score, 0.92)
            if score > best_score:
                best, best_score = v, score
        if best is not None and best_score >= 0.60:
            ep["ytId"] = best["id"]
            ep["ytTitle"] = best.get("title") or ""
            ep["ytDuration"] = best.get("duration") or 0
            used.add(best["id"])
            matched += 1

    (pdir / "episodes.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    n = len(data["episodes"])
    print(f"{slug}: {matched}/{n} episodes matched to YouTube videos ({n-matched} without ytId)")


if __name__ == "__main__":
    for slug in sys.argv[1:] or ["nopriors", "cogrev", "trainingdata", "unsupervised"]:
        merge(slug)
