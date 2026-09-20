"""Slack Block Kit 빌드 · 전송 — PRD §9."""
import time
from datetime import datetime, timedelta, timezone

import requests

from . import config as C

KST = timezone(timedelta(hours=9))
WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]

SECTION_TEXT_LIMIT = 2900  # Slack 한도 3000자, 여유 100자


def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def trunc(s: str, n: int = 80) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def rel_time(age_h: float) -> str:
    if age_h < 1:
        return f"{max(1, int(age_h * 60))}분 전"
    if age_h < 24:
        return f"{int(age_h)}시간 전"
    return f"{int(age_h // 24)}일 전"


def _item_line(idx: int, art) -> str:
    badge = "🔁 " if art.get("followup") else ""
    title = esc(trunc(art["title"]))
    meta = f'{esc(art["source"])} · {rel_time(art["age_h"])}'
    return f'`{idx}.` {badge}<{art["url"]}|{title}>\n      _{meta}_'


def build_blocks(selected_by_cat, meta):
    now = datetime.now(KST)
    header = f"📰 데일리 브리핑 · {now.month}월 {now.day}일 ({WEEKDAY_KO[now.weekday()]})"

    blocks = [
        {"type": "header",
         "text": {"type": "plain_text", "text": header, "emoji": True}},
    ]

    for cat in C.CATEGORIES:
        items = selected_by_cat.get(cat, [])
        blocks.append({"type": "divider"})
        label = C.CATEGORY_LABEL[cat]
        if len(items) < 3:
            label += "   ⚠️ 수집 부족"
        blocks.append({"type": "section",
                       "text": {"type": "mrkdwn", "text": f"*{label}*"}})

        if not items:
            blocks.append({"type": "section",
                           "text": {"type": "mrkdwn", "text": "_오늘은 조건에 맞는 새 기사가 없습니다._"}})
            continue

        chunk, buf = [], ""
        for i, art in enumerate(items, 1):
            line = _item_line(i, art)
            if len(buf) + len(line) + 2 > SECTION_TEXT_LIMIT:
                chunk.append(buf)
                buf = line
            else:
                buf = f"{buf}\n\n{line}" if buf else line
        if buf:
            chunk.append(buf)
        for c in chunk:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": c}})

    ctx = (
        f'수집 소스 {meta["sources_ok"]}개 · 후보 {meta["candidates"]}건 · '
        f'중복 제외 {meta["blocked"]}건 · {meta["total"]}건 선별 · '
        f'{now.strftime("%Y-%m-%d %H:%M")} KST'
    )
    if meta.get("cold_start"):
        ctx = "⚠️ 발송 이력 없음 — 중복 필터 미적용\n" + ctx
    if meta.get("log_only"):
        ctx = "🧪 DEDUP_LOG_ONLY 관찰 모드 (차단 없이 로그만)\n" + ctx

    blocks.append({"type": "divider"})
    blocks.append({"type": "context",
                   "elements": [{"type": "mrkdwn", "text": ctx}]})
    return header, blocks


def post(payload, webhook=None):
    url = webhook or C.SLACK_WEBHOOK_URL
    if not url:
        raise RuntimeError("SLACK_WEBHOOK_URL 이 설정되지 않았습니다.")

    delay = 2
    last = None
    for attempt in range(1, 4):
        try:
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code == 200:
                return True
            last = f"HTTP {r.status_code}: {r.text[:200]}"
            if 400 <= r.status_code < 500:
                break  # 설정 오류 — 재시도 무의미
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {e}"
        if attempt < 3:
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"슬랙 전송 실패: {last}")


def send_alert(text, webhook=None):
    try:
        post({"text": f"⚠️ daily-brief-bot: {text}", "unfurl_links": False}, webhook)
    except Exception as e:  # noqa: BLE001
        print(f"[slack] 경고 전송 실패: {e}")
