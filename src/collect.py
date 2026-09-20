"""RSS 수집 · 정규화."""
import calendar
import concurrent.futures as cf
from datetime import datetime, timezone

import feedparser
import requests

from . import config as C
from .sources import SOURCES, KEYWORDS, PROMO_PATTERNS
from .fingerprint import (
    url_hash, clean_title, simhash, event_key, strip_source_suffix,
)


def _session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": C.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
    })
    return s


def is_promo(title: str) -> bool:
    t = (title or "").lower()
    return any(p in t for p in PROMO_PATTERNS)


def _published(entry):
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc)
            except (ValueError, OverflowError, TypeError):
                continue
    return None


def _entry_source(entry, feed_name):
    """Google News는 <source> 요소에 실제 매체명이 들어 있다."""
    src = entry.get("source")
    if isinstance(src, dict):
        title = (src.get("title") or "").strip()
        if title:
            return title
    if feed_name == "Google News":
        _, suffix = strip_source_suffix(entry.get("title", ""))
        if suffix:
            return suffix
    return feed_name


def fetch_one(sess, src):
    try:
        r = sess.get(src["url"], timeout=C.HTTP_TIMEOUT)
        if r.status_code != 200:
            return src, [], f"HTTP {r.status_code}"
        parsed = feedparser.parse(r.content)
        return src, parsed.entries or [], None
    except Exception as e:  # noqa: BLE001 — 소스 하나의 실패가 전체를 막으면 안 된다
        return src, [], type(e).__name__


def collect():
    """모든 피드를 병렬 수집해 Article dict 리스트로 반환."""
    sess = _session()
    now = datetime.now(timezone.utc)
    articles = []
    seen_ids = set()
    report = []

    with cf.ThreadPoolExecutor(max_workers=C.FETCH_WORKERS) as ex:
        futures = [ex.submit(fetch_one, sess, s) for s in SOURCES]
        for fut in cf.as_completed(futures):
            src, entries, err = fut.result()
            n_ok = 0
            max_age = C.MAX_AGE_HOURS[src["cat"]]

            for e in entries:
                link = (e.get("link") or "").strip()
                title_raw = (e.get("title") or "").strip()
                if not link or not title_raw:
                    continue
                if is_promo(title_raw):
                    continue

                pub = _published(e)
                if pub is None:
                    continue
                age_h = (now - pub).total_seconds() / 3600.0
                if age_h < -3 or age_h > max_age:
                    continue

                guid = (e.get("id") or e.get("guid") or "").strip()
                uh = url_hash(link, guid)
                if uh in seen_ids:
                    continue
                seen_ids.add(uh)

                title, _ = strip_source_suffix(title_raw) if src["name"] == "Google News" else (title_raw, "")
                ct = clean_title(title, drop_source_suffix=False)

                articles.append({
                    "title": title,
                    "url": link,
                    "guid": guid,
                    "source": _entry_source(e, src["name"]),
                    "feed": src["name"],
                    "category": src["cat"],
                    "slot": src.get("slot"),
                    "published": pub,
                    "age_h": age_h,
                    "weight": src["weight"],
                    "url_hash": uh,
                    "clean": ct,
                    "simhash": simhash(ct),
                    "event_key": event_key(title, C.DEDUP_EVENT_TOKENS, drop_source_suffix=False),
                    "summary": (e.get("summary") or "")[:400],
                    "followup": False,
                })
                n_ok += 1

            report.append((src["cat"], src["name"], n_ok, err))

    return articles, report


def keyword_score(art):
    kws = KEYWORDS.get(art["category"], [])
    if not kws:
        return 0.0
    hay = (art["title"] + " " + art["summary"]).lower()
    hits = sum(1 for k in kws if k in hay)
    return min(1.0, hits / 3.0)
