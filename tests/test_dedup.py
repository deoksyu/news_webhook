"""중복 방지 단위 테스트 — 외부 네트워크 없이 동작."""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config as C                                     # noqa: E402
from src.dedup import History, has_progress_signal, KST          # noqa: E402
from src.fingerprint import (                                    # noqa: E402
    normalize_url, url_identity, url_hash, clean_title, strip_source_suffix,
    simhash, hamming, event_key, extract_tokens, entity_overlap,
)

FAILS = []


def check(name, cond, extra=""):
    if cond:
        print(f"  ✓ {name}")
    else:
        print(f"  ✗ {name} {extra}")
        FAILS.append(name)


# ------------------------------------------------------------------ URL
def test_url():
    print("\n[URL 정규화]")
    check("추적 파라미터 제거",
          normalize_url("https://www.bbc.co.uk/news/articles/abc?at_medium=RSS&at_campaign=rss")
          == "https://bbc.co.uk/news/articles/abc")
    check("utm 제거 + 끝 슬래시",
          normalize_url("https://khan.co.kr/article/123/?utm_source=rss&utm_medium=rss")
          == "https://khan.co.kr/article/123")
    check("www / m. / amp 환원",
          normalize_url("https://m.example.com/amp/news/1")
          == "https://example.com/news/1")
    check("같은 기사 다른 파라미터 → 같은 해시",
          url_hash("https://a.com/x?utm_source=rss") == url_hash("https://a.com/x"))
    check("Google News 는 guid 기반 식별",
          url_identity("https://news.google.com/rss/articles/CBMiAAA?oc=5", "CBMiZZZ")
          == "gnews:CBMiZZZ")
    check("Google News 링크가 달라져도 guid 같으면 동일",
          url_hash("https://news.google.com/rss/articles/CBMi111?oc=5", "G1")
          == url_hash("https://news.google.com/rss/articles/CBMi222?oc=5", "G1"))


# ------------------------------------------------------------------ 제목
def test_title():
    print("\n[제목 정규화 · SimHash]")
    check("말머리 제거",
          "속보" not in clean_title("[속보] 北, 탄도미사일 발사"))
    check("Google News 매체 접미 분리",
          strip_source_suffix("AI 규제법 통과 - 연합뉴스") == ("AI 규제법 통과", "연합뉴스"))
    check("숫자 보존", "2" in clean_title("北 탄도미사일 2발 발사"))

    a = simhash(clean_title("北, 탄도미사일 2발 3시간 간격 발사…유엔총회 앞두고 도발(종합3보)"))
    b = simhash(clean_title("[속보] 北, 탄도미사일 2발 3시간 간격 발사…유엔총회 앞두고 도발"))
    check("속보/종합 변형은 근거리", hamming(a, b) <= C.DEDUP_SIMHASH_DISTANCE,
          f"(거리={hamming(a, b)})")

    c = simhash(clean_title("국힘 개헌보다 민생이 먼저"))
    check("무관한 제목은 원거리", hamming(a, c) > C.DEDUP_SIMHASH_DISTANCE,
          f"(거리={hamming(a, c)})")


# ------------------------------------------------------------------ 사건 토큰
def test_tokens():
    print("\n[사건 토큰 · 일반어 필터]")
    t1 = set(extract_tokens("Trump says his planned triumphal arch will double as a military complex"))
    t2 = set(extract_tokens("Trump claims triumphal arch will serve as a top grade military complex"))
    check("같은 사건(다른 매체) → 중복 인정", entity_overlap(t1, t2, 2) >= 2)

    h1 = set(extract_tokens("Houthis say they targeted Saudi capital with ballistic missile"))
    h2 = set(extract_tokens("Moscow targeted with hundreds of drones as Kyiv strikes"))
    check("일반어끼리만 겹치면 중복 아님", entity_overlap(h1, h2, 2) == 0,
          f"(공통={sorted(h1 & h2)})")

    k1 = set(extract_tokens("민주당 “연임 논란 정리됐다…내년 상반기 개헌 국민투표 추진”"))
    k2 = set(extract_tokens("“연임·공소취소 논란 정리는 긍정적…부동산 문제 전임 정부 탓은 아쉬워”"))
    check("한국어 같은 사건 인정", entity_overlap(k1, k2, 2) >= 2,
          f"(공통={sorted(k1 & k2)})")

    check("사건 키 안정성",
          event_key("北 탄도미사일 발사") == event_key("北 탄도미사일 발사"))


# ------------------------------------------------------------------ 진전 신호어
def test_progress():
    print("\n[후속 보도 예외]")
    check("신규 진전 신호어 감지",
          has_progress_signal("대미 투자 협상 타결", "대미 투자 협상 막판 진통"))
    check("이미 있던 신호어는 진전 아님",
          not has_progress_signal("협상 타결 후속 논의", "대미 투자 협상 타결"))
    check("신호어 없으면 False",
          not has_progress_signal("협상 계속 진행 중", "협상 막판 진통"))


# ------------------------------------------------------------------ History
def _art(title, url, guid="", cat="kr"):
    ct = clean_title(title, drop_source_suffix=False)
    return {
        "title": title, "url": url, "guid": guid, "category": cat,
        "source": "테스트", "url_hash": url_hash(url, guid),
        "simhash": simhash(ct), "event_key": event_key(title, 4, False),
        "_etok": set(extract_tokens(title, False)),
    }


def _write_history(path, rows):
    now = datetime.now(timezone.utc)
    entries = []
    for title, url, days_ago, cat in rows:
        a = _art(title, url, cat=cat)
        entries.append({
            "url_hash": a["url_hash"], "url": url,
            "simhash": f'{a["simhash"]:016x}', "event_key": a["event_key"],
            "title": title, "source": "테스트", "category": cat,
            "tokens": sorted(a["_etok"]),
            "sent_at": (now - timedelta(days=days_ago)).astimezone(KST).isoformat(timespec="seconds"),
            "followup_count": 0,
        })
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "entries": entries}, f, ensure_ascii=False)


def test_history():
    print("\n[이력 대조]")
    d = tempfile.mkdtemp()
    p = os.path.join(d, "history.json")

    _write_history(p, [
        ("국힘 개헌보다 민생이 먼저 국민이 믿을 국정부터", "https://yna.co.kr/view/AKR1", 1, "kr"),
        ("Moscow targeted with hundreds of drones as Kyiv strikes", "https://theguardian.com/w/1", 1, "world"),
        ("오래된 기사 탄도미사일 발사", "https://old.example.com/1", 20, "kr"),
    ])
    h = History(p)
    check("이력 로드", len(h.entries) == 3)

    dup, reason, _ = h.check(_art("아무 제목", "https://yna.co.kr/view/AKR1"), "kr")
    check("L1 — 같은 URL 차단", dup and reason == "L1_URL")

    dup, reason, _ = h.check(
        _art("아무 제목", "https://www.yna.co.kr/view/AKR1?utm_source=rss"), "kr")
    check("L1 — 파라미터만 다른 URL도 차단", dup and reason == "L1_URL")

    dup, reason, _ = h.check(
        _art("[속보] 국힘 개헌보다 민생이 먼저 국민이 믿을 국정부터", "https://other.com/9"), "kr")
    check("L2 — 제목 거의 같으면 차단", dup and reason.startswith("L2"), f"({reason})")

    dup, reason, _ = h.check(
        _art("Largest attack on Moscow sees Ukraine fire hundreds of drones",
             "https://bbc.co.uk/n/9", cat="world"), "world")
    check("L3b — 다른 매체 같은 사건 차단", dup and reason.startswith("L3"), f"({reason})")

    dup, reason, _ = h.check(
        _art("Houthis say they targeted Saudi capital with ballistic missile",
             "https://aj.com/9", cat="world"), "world")
    check("L3b — 무관한 사건은 통과", not dup, f"({reason})")

    dup, reason, _ = h.check(_art("탄도미사일 발사", "https://new.example.com/2"), "kr")
    check("시간창 밖(20일 전) 기사는 L3 대상 아님", not dup or reason == "L1_URL", f"({reason})")

    # 후속 보도 예외
    _write_history(p, [("대미 투자 협상 막판 진통 상업적 합리성", "https://yna.co.kr/v/1", 1, "kr")])
    h2 = History(p)
    dup, reason, _ = h2.check(
        _art("대미 투자 협상 상업적 합리성 타결", "https://yna.co.kr/v/2"), "kr")
    check("진전 신호어 있으면 후속 허용", not dup and reason == "L3_FOLLOWUP_ALLOWED", f"({reason})")


def test_persistence():
    print("\n[이력 저장 · 복구]")
    d = tempfile.mkdtemp()
    p = os.path.join(d, "history.json")

    h = History(p)
    check("파일 없으면 콜드 스타트", h.cold_start)

    a = _art("테스트 기사", "https://example.com/1")
    n = h.save([{
        "url_hash": a["url_hash"], "url": a["url"], "simhash": a["simhash"],
        "event_key": a["event_key"], "title": a["title"], "source": "테스트",
        "category": "kr", "tokens": list(a["_etok"]), "followup_count": 0,
    }])
    check("저장 성공", n == 1 and os.path.exists(p))

    h2 = History(p)
    check("재로드 후 차단 동작", h2.check(a, "kr")[0])

    with open(p, "w", encoding="utf-8") as f:
        f.write("{깨진 JSON")
    h3 = History(p)
    check("손상 파일 → 콜드 스타트 폴백", h3.cold_start and h3.corrupt)
    check("손상 원본 보존", os.path.exists(p.replace(".json", ".corrupt.json")))

    # 보존 기간 정리
    _write_history(p, [("아주 오래된 기사", "https://old.com/1", 40, "kr")])
    h4 = History(p)
    left = h4.save([])
    check(f"보존기간({C.HISTORY_RETENTION_DAYS}일) 초과분 정리", left == 0, f"(남은 건수={left})")


if __name__ == "__main__":
    print("=" * 60)
    print("중복 방지 단위 테스트")
    print("=" * 60)
    test_url()
    test_title()
    test_tokens()
    test_progress()
    test_history()
    test_persistence()
    print("\n" + "=" * 60)
    if FAILS:
        print(f"실패 {len(FAILS)}건: {FAILS}")
        sys.exit(1)
    print("전체 통과 ✅")
