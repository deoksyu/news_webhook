"""이전 날 중복 방지 (Cross-day Dedup) — PRD §8.4."""
import json
import os
import shutil
from datetime import datetime, timedelta, timezone

from . import config as C
from .fingerprint import hamming, entity_overlap

KST = timezone(timedelta(hours=9))

# PRD §8.4.4 — 진전 신호어
PROGRESS_SIGNALS = [
    # 한국어
    "타결", "합의", "결렬", "파기", "통과", "부결", "승인", "철회", "사퇴", "해임",
    "구속", "영장", "기소", "선고", "판결", "무죄", "유죄", "사망", "사상자", "확정",
    "개시", "중단", "재개", "인수", "상장", "폐업", "체포", "압수수색", "발표", "출시",
    "공개", "복귀", "취소", "연기", "돌파", "최종",
    # 영어
    "agrees", "deal reached", "collapses", "passes", "rejected", "approved",
    "resigns", "arrested", "indicted", "verdict", "sentenced", "killed",
    "confirmed", "launches", "acquires", "ipo", "wins", "loses", "halts",
    "resumes", "signs", "announces",
]


def _now():
    return datetime.now(timezone.utc)


def _parse_iso(s):
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def has_progress_signal(new_title: str, old_title: str) -> bool:
    """오늘 제목에는 있고 과거 제목에는 없는 진전 신호어가 있는가."""
    n = (new_title or "").lower()
    o = (old_title or "").lower()
    for sig in PROGRESS_SIGNALS:
        s = sig.lower()
        if s in n and s not in o:
            return True
    return False


class History:
    """state/history.json 로드/판정/저장."""

    def __init__(self, path=None):
        self.path = path or C.HISTORY_PATH
        self.entries = []
        self.cold_start = False
        self.corrupt = False
        self._load()
        self._index()

    # ---------------------------------------------------------- I/O
    def _load(self):
        if not os.path.exists(self.path):
            self.cold_start = True
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.entries = data.get("entries", [])
            if not isinstance(self.entries, list):
                raise ValueError("entries is not a list")
        except Exception as e:  # noqa: BLE001 — 어떤 손상이든 콜드 스타트로 폴백
            print(f"[dedup] history 손상 ({e}) → 콜드 스타트")
            try:
                shutil.copy(self.path, self.path.replace(".json", ".corrupt.json"))
            except OSError:
                pass
            self.entries = []
            self.cold_start = True
            self.corrupt = True

    def _index(self):
        """조회 성능을 위해 url_hash 집합과 카테고리별 리스트를 미리 만든다."""
        now = _now()
        self._url_hashes = set()
        self._by_cat = {}
        for e in self.entries:
            dt = _parse_iso(e.get("sent_at", ""))
            if dt is None:
                continue
            age_days = (now - dt).total_seconds() / 86400.0
            e["_age_days"] = age_days
            if age_days <= C.WINDOW_L1:
                self._url_hashes.add(e.get("url_hash"))
            self._by_cat.setdefault(e.get("category", ""), []).append(e)

    def save(self, new_items):
        """발송 성공한 항목만 추가하고 보존 기간을 정리한다."""
        now = _now()
        for it in new_items:
            self.entries.append(
                {
                    "url_hash": it["url_hash"],
                    "url": it["url"],
                    "simhash": f'{it["simhash"]:016x}',
                    "event_key": it["event_key"],
                    "title": it["title"],
                    "source": it["source"],
                    "category": it["category"],
                    "tokens": sorted(it.get("tokens") or []),
                    "sent_at": now.astimezone(KST).isoformat(timespec="seconds"),
                    "followup_count": it.get("followup_count", 0),
                }
            )

        kept = []
        for e in self.entries:
            dt = _parse_iso(e.get("sent_at", ""))
            if dt is None:
                continue
            if (now - dt).total_seconds() / 86400.0 <= C.HISTORY_RETENTION_DAYS:
                e.pop("_age_days", None)
                kept.append(e)
        kept.sort(key=lambda e: e.get("sent_at", ""))
        if len(kept) > C.HISTORY_MAX_ENTRIES:
            kept = kept[-C.HISTORY_MAX_ENTRIES :]

        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "version": 1,
                    "updated_at": now.astimezone(KST).isoformat(timespec="seconds"),
                    "entries": kept,
                },
                f,
                ensure_ascii=False,
                indent=1,
            )
        os.replace(tmp, self.path)
        self.entries = kept
        return len(kept)

    # ---------------------------------------------------------- 판정
    def _recent(self, category, days):
        out = []
        for e in self._by_cat.get(category, []):
            if e.get("_age_days", 1e9) <= days:
                out.append(e)
        return out

    def check(self, art, category, skip_l3=False):
        """(is_dup, reason, matched_entry) — PRD §8.4.3 판정 순서."""
        if art["url_hash"] in self._url_hashes:
            return True, "L1_URL", None

        dist_limit = C.DEDUP_SIMHASH_DISTANCE
        for e in self._recent(category, C.WINDOW_L2.get(category, 7)):
            try:
                old = int(e.get("simhash", "0"), 16)
            except (TypeError, ValueError):
                continue
            d = hamming(art["simhash"], old)
            if d <= dist_limit:
                return True, f"L2_TITLE(d={d})", e

        if not skip_l3:
            atok = art.get("_etok") or set()
            for e in self._recent(category, C.WINDOW_L3.get(category, 2)):
                same_key = art["event_key"] == e.get("event_key")

                # L3b — 핵심어 N개 이상 중복: 제목이 달라도 같은 사건을 잡는다
                overlap = 0
                if atok and e.get("tokens"):
                    overlap = entity_overlap(
                        atok, set(e["tokens"]), C.DEDUP_TOKEN_OVERLAP
                    )
                same_tokens = overlap > 0

                if not (same_key or same_tokens):
                    continue

                if e.get("followup_count", 0) < 1 and has_progress_signal(
                    art["title"], e.get("title", "")
                ):
                    return False, "L3_FOLLOWUP_ALLOWED", e
                shared = ",".join(sorted(atok & set(e.get("tokens") or [])))
                reason = "L3_EVENT" if same_key else f"L3_TOKENS[{shared}]"
                return True, reason, e

        return False, None, None


def filter_articles(articles, category, history, skip_l3=False):
    """중복 제거된 리스트와 통계를 돌려준다."""
    stats = {"L1": 0, "L2": 0, "L3": 0, "followup": 0}
    kept = []
    if not C.DEDUP_ENABLED or history is None:
        return articles, stats

    for art in articles:
        is_dup, reason, matched = history.check(art, category, skip_l3=skip_l3)

        if reason == "L3_FOLLOWUP_ALLOWED":
            art["followup"] = True
            art["followup_count"] = matched.get("followup_count", 0) + 1
            stats["followup"] += 1
            kept.append(art)
            continue

        if is_dup:
            key = reason.split("_")[0].split("(")[0]
            stats[key] = stats.get(key, 0) + 1
            old = f' ~ "{matched["title"][:40]}"({matched["sent_at"][:10]})' if matched else ""
            print(f'  [{category}] BLOCKED {reason} "{art["title"][:45]}"{old}')
            if C.DEDUP_LOG_ONLY:
                kept.append(art)
            continue

        kept.append(art)

    return kept, stats
