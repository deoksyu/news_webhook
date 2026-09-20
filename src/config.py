"""환경변수 · 상수 정의."""
import os

def _b(name, default=False):
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")

def _i(name, default):
    try:
        return int(os.getenv(name, "").strip())
    except (ValueError, AttributeError):
        return default

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "").strip()

DRY_RUN = _b("DRY_RUN", False)
ITEMS_PER_CATEGORY = _i("ITEMS_PER_CATEGORY", 5)

MAX_AGE_HOURS_NEWS = _i("MAX_AGE_HOURS_NEWS", 24)
MAX_AGE_HOURS_BIZ = _i("MAX_AGE_HOURS_BIZ", 168)

# --- 중복 방지 ---
DEDUP_ENABLED = _b("DEDUP_ENABLED", True)
DEDUP_LOG_ONLY = _b("DEDUP_LOG_ONLY", False)
DEDUP_SIMHASH_DISTANCE = _i("DEDUP_SIMHASH_DISTANCE", 6)
DEDUP_EVENT_TOKENS = _i("DEDUP_EVENT_TOKENS", 4)
HISTORY_RETENTION_DAYS = _i("HISTORY_RETENTION_DAYS", 35)
HISTORY_MAX_ENTRIES = _i("HISTORY_MAX_ENTRIES", 1000)
DEDUP_TOKEN_OVERLAP = _i("DEDUP_TOKEN_OVERLAP", 2)   # L3b: 핵심어 N개 이상 겹치면 같은 사건
SAVE_HISTORY_ON_DRY = _b("SAVE_HISTORY_ON_DRY", False)  # 테스트용

CHECK_LINKS = _b("CHECK_LINKS", True)

# 카테고리
CATEGORIES = ["ai", "biz", "kr", "world"]

CATEGORY_LABEL = {
    "ai":    "🤖 AI 뉴스",
    "biz":   "💡 사업 아이템 · 아이디어 · 성공 사례",
    "kr":    "🇰🇷 국내 시사 · 정치",
    "world": "🌍 세계 시사 · 정치",
}

MAX_AGE_HOURS = {
    "ai": MAX_AGE_HOURS_NEWS,
    "biz": MAX_AGE_HOURS_BIZ,
    "kr": MAX_AGE_HOURS_NEWS,
    "world": MAX_AGE_HOURS_NEWS,
}

# PRD §8.4.2 — 카테고리별 차단 시간창(일)
WINDOW_L1 = 30  # URL 지문: 전역 30일
WINDOW_L2 = {"ai": 7, "biz": 14, "kr": 7, "world": 7}
WINDOW_L3 = {"ai": 3, "biz": 7, "kr": 2, "world": 2}

# 카테고리별 최종 선별에서 동일 매체 최대 허용 건수
MEDIA_CAP = _i("MEDIA_CAP", 2)

# 사업 카테고리 슬롯 배분 (PRD FR-2)
BIZ_SLOTS = [
    ("kr_startup", 2),
    ("global_startup", 1),
    ("local_biz", 1),
    ("trend", 1),
]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

HTTP_TIMEOUT = _i("HTTP_TIMEOUT", 12)
FETCH_WORKERS = _i("FETCH_WORKERS", 12)

HISTORY_PATH = os.getenv("HISTORY_PATH", "state/history.json")
