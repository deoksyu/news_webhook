"""검증 게이트 — PRD §6.2.

LLM을 쓰지 않는 Mode A에서도 항상 실행한다.
"최종 발송물의 모든 제목·URL이 수집한 원본과 바이트 단위로 같다"를 보증한다.
"""
import concurrent.futures as cf
import re

import requests

from . import config as C

URL_RE = re.compile(r"https?://[^\s\"'<>|]+")


class GuardError(Exception):
    pass


def verify(selected_by_cat, all_articles):
    """V1~V3 — 최종 항목이 원본 기사 집합의 부분집합인지 확인."""
    origin_urls = {a["url"] for a in all_articles}
    origin_titles = {(a["url"], a["title"]) for a in all_articles}

    for cat, items in selected_by_cat.items():
        for it in items:
            if it["url"] not in origin_urls:
                raise GuardError(f"V2 위반: 원본에 없는 URL — {it['url']}")
            if (it["url"], it["title"]) not in origin_titles:
                raise GuardError(f"V3 위반: 제목이 원본과 다름 — {it['title']}")
            if not URL_RE.match(it["url"]):
                raise GuardError(f"V4 위반: URL 형식 아님 — {it['url']}")
    return True


def _head(sess, url):
    try:
        r = sess.head(url, timeout=6, allow_redirects=True)
        if r.status_code in (403, 405, 999):  # HEAD 거부 서버는 통과로 간주
            return True
        return r.status_code < 400
    except requests.RequestException:
        return False


def check_links(articles):
    """살아 있는 링크만 남긴다 (PRD §6.5). Google News 링크는 검사 생략."""
    if not C.CHECK_LINKS or not articles:
        return articles, 0

    sess = requests.Session()
    sess.headers.update({"User-Agent": C.USER_AGENT})

    targets = [a for a in articles if "news.google.com" not in a["url"]]
    ok = {}
    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(_head, sess, a["url"]): a["url"] for a in targets}
        for f in cf.as_completed(futs):
            ok[futs[f]] = f.result()

    kept = [a for a in articles if ok.get(a["url"], True)]
    return kept, len(articles) - len(kept)
