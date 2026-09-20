"""오케스트레이션 — 수집 → 중복제거 → 선별 → 검증 → 슬랙 발송."""
import json
import sys
import traceback

from . import config as C
from . import rank, slack, guard
from .collect import collect
from .dedup import History, filter_articles


def run():
    print("=" * 70)
    print("daily-brief-bot")
    print(f"  DRY_RUN={C.DRY_RUN}  DEDUP_ENABLED={C.DEDUP_ENABLED}  "
          f"DEDUP_LOG_ONLY={C.DEDUP_LOG_ONLY}")
    print("=" * 70)

    # 1) 수집
    articles, report = collect()
    ok_sources = sum(1 for _, _, n, err in report if err is None and n > 0)
    print(f"\n[수집] 총 {len(articles)}건 / 소스 {len(report)}개 중 {ok_sources}개 정상")
    for cat, name, n, err in sorted(report):
        if err:
            print(f"   ✗ [{cat}] {name}: {err}")
        elif n == 0:
            print(f"   · [{cat}] {name}: 0건 (시간창 밖)")

    rank.annotate_tokens(articles)

    # 2) 이력 로드
    history = History() if C.DEDUP_ENABLED else None
    if history and history.cold_start:
        print("\n[중복] 발송 이력 없음 — 콜드 스타트")
    elif history:
        print(f"\n[중복] 이력 {len(history.entries)}건 로드")

    # 3) 카테고리별 중복 제거 + 선별
    selected = {}
    taken_events = set()
    taken_etok = []
    total_blocked = 0
    N = C.ITEMS_PER_CATEGORY
    BUFFER = 3   # 죽은 링크를 대비해 여유분을 더 뽑고 검증 후 잘라낸다

    for cat in C.CATEGORIES:
        pool = [a for a in articles if a["category"] == cat]
        kept, stats = filter_articles(pool, cat, history)
        blocked = stats["L1"] + stats["L2"] + stats["L3"]

        picked = rank.select(kept, cat, N + BUFFER, taken_events, taken_etok)

        # 폴백: 부족하면 L3(사건 키) 차단만 한시적으로 해제
        if len(picked) < N and stats["L3"] > 0:
            kept2, stats2 = filter_articles(pool, cat, history, skip_l3=True)
            picked = rank.select(kept2, cat, N + BUFFER, taken_events, taken_etok)
            print(f"   ↻ [{cat}] 후보 부족 → L3 차단 해제 후 재선별")
            blocked = stats2["L1"] + stats2["L2"]

        # 링크 생존 확인 후 상위 N건만 확정
        alive, dropped = guard.check_links(picked)
        if dropped:
            print(f"   ⚠ [{cat}] 죽은 링크 {dropped}건 제외")
        final = alive[:N]
        selected[cat] = final

        for a in final:
            taken_events.add(a["event_key"])
            taken_etok.append(a["_etok"])

        total_blocked += blocked
        print(f"   [{cat}] 후보 {len(pool)}건 → L1차단 {stats['L1']}, "
              f"L2차단 {stats['L2']}, L3차단 {stats['L3']}, "
              f"후속허용 {stats['followup']} → 최종 {len(final)}건")

    # 5) 검증 게이트
    guard.verify(selected, articles)
    print("\n[검증] V1~V4 통과 — 모든 제목·URL이 수집 원본과 일치")

    total = sum(len(v) for v in selected.values())
    meta = {
        "sources_ok": ok_sources,
        "candidates": len(articles),
        "blocked": total_blocked,
        "total": total,
        "cold_start": bool(history and history.cold_start),
        "log_only": C.DEDUP_LOG_ONLY,
    }

    header, blocks = slack.build_blocks(selected, meta)
    payload = {"text": header, "blocks": blocks, "unfurl_links": False,
               "unfurl_media": False}

    def _persist():
        if history is None or C.DEDUP_LOG_ONLY:
            return
        items = []
        for cat in C.CATEGORIES:
            for a in selected[cat]:
                items.append({
                    "url_hash": a["url_hash"], "url": a["url"],
                    "simhash": a["simhash"], "event_key": a["event_key"],
                    "title": a["title"], "source": a["source"],
                    "category": cat, "tokens": list(a.get("_etok") or []),
                    "followup_count": a.get("followup_count", 0),
                })
        n = history.save(items)
        print(f"[이력] {len(items)}건 추가 → 총 {n}건 보관")

    # 6) 발송
    if C.DRY_RUN:
        print("\n[DRY_RUN] 슬랙 전송 생략. 선별 결과:\n")
        for cat in C.CATEGORIES:
            print(f"── {C.CATEGORY_LABEL[cat]}")
            for i, a in enumerate(selected[cat], 1):
                flag = "🔁" if a.get("followup") else "  "
                print(f"  {i}. {flag} {a['title'][:62]}")
                print(f"        {a['source']} · {a['url'][:95]}")
            print()
        print(f"[DRY_RUN] payload {len(json.dumps(payload))} bytes / "
              f"blocks {len(blocks)}개")
        if C.SAVE_HISTORY_ON_DRY:
            _persist()
        return 0

    slack.post(payload)
    print(f"\n[발송] 완료 — {total}건")

    # 7) 이력 저장 (발송 성공 후에만)
    _persist()

    if total < len(C.CATEGORIES) * 3:
        slack.send_alert(f"수집 부족 — 총 {total}건만 발송되었습니다.")
    return 0


def main():
    try:
        return run()
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        if not C.DRY_RUN and C.SLACK_WEBHOOK_URL:
            slack.send_alert(f"실행 실패 — {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
