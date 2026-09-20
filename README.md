# news_webhook — 슬랙 데일리 브리핑 봇

매일 오전 8시(KST), 슬랙으로 **AI / 사업 / 국내 시사 / 세계 시사** 각 5건씩 총 20건의
**실제 기사 링크**를 보내는 봇. 서버·DB·유료 API 없이 GitHub Actions만으로 돌아간다.

```
📰 데일리 브리핑 · 9월 21일 (월)
──────────────────────────────
🤖 AI 뉴스
 1. OpenAI, 신규 추론 모델 공개
       TechCrunch · 3시간 전
 ...
──────────────────────────────
수집 소스 32개 · 후보 924건 · 중복 제외 14건 · 20건 선별 · 08:00 KST
```

---

## 1. 설정 (5분)

### ① Slack Incoming Webhook
1. https://api.slack.com/apps → **Create New App** → From scratch
2. **Incoming Webhooks** 활성화 → **Add New Webhook to Workspace** → 채널 선택
3. 발급된 URL 복사

### ② GitHub Secret 등록
리포지토리 → **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|---|---|
| `SLACK_WEBHOOK_URL` | 위에서 복사한 URL |

> ⚠️ Webhook URL은 **절대 코드에 넣지 않는다.** URL을 아는 사람은 누구나 채널에 글을 쓸 수 있다.

### ③ 워크플로우 권한 확인
**Settings → Actions → General → Workflow permissions** 에서
`Read and write permissions` 선택. (발송 이력 커밋에 필요)

### ④ 동작 확인
**Actions → daily-brief → Run workflow** 로 수동 실행.
처음에는 `dry_run: true` 로 한 번 돌려 로그만 확인하는 것을 권장.

---

## 2. 로컬 실행

```bash
pip install -r requirements.txt

# 보내지 않고 결과만 확인
DRY_RUN=true python -m src.main

# 실제 발송
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
python -m src.main

# 테스트
python tests/test_dedup.py
```

---

## 3. 핵심 설계

### 3.1 할루시네이션 방지
**LLM을 쓰지 않는다.** 제목과 URL은 RSS 피드에서 파싱한 원본 문자열을 그대로 쓰고,
발송 직전 `guard.verify()` 가 "최종 발송물의 모든 제목·URL이 수집 원본 집합에 있는가"를
검사한다. 하나라도 어긋나면 예외를 던지고 발송하지 않는다.
링크는 HEAD 요청으로 생존을 확인하고, 죽은 링크는 다음 순위 후보로 교체한다.

### 3.2 이전 날 중복 방지 — 3중 지문

어제 보낸 기사가 오늘 또 나오는 걸 막는다. URL 해시만으로는 부족하다.
같은 사건을 **다른 매체가 다른 제목·다른 URL로** 다시 보도하기 때문이다.

| 레이어 | 지문 | 잡는 중복 | 시간창 |
|---|---|---|---|
| **L1** | 정규화 URL의 SHA-1 | 같은 기사 재등장 | 30일 (전역) |
| **L2** | 제목 64bit SimHash, 해밍거리 ≤ 6 | 제목이 거의 같은 기사 | 7~14일 |
| **L3** | 사건 키 + **핵심어 2개 이상 중복** | 같은 사건, 다른 매체, 다른 제목 | 2~7일 |

실제 차단 예시 (로그):
```
[world] BLOCKED L3_TOKENS[drones,hundreds,moscow]
        "Largest attack on Moscow sees Ukraine fire hundreds of drones"
      ~ "Moscow targeted with hundreds of drones…"(2026-09-20)
```

**일반어 필터** — 공통 토큰이 `targeted`, `ballistic` 처럼 사건을 특정하지 못하는
일반어뿐이면 중복으로 보지 않는다. 이게 없으면 "후티 반군의 사우디 공습"과
"모스크바 드론 공격"이 같은 사건으로 잘못 묶인다.

**후속 보도 예외** — 사건 키가 같아도 제목에 이전에 없던 진전 신호어
(`타결`, `구속`, `선고`, `통과`, `resigns`, `verdict` …)가 새로 등장하면 통과시키고
`🔁` 뱃지를 붙인다. 사건이 끝날 때까지 막으면 정작 결론을 놓친다.

### 3.3 이력 영속화
`state/history.json` 을 **리포지토리에 커밋**한다.
`actions/cache` 는 7일 미사용 시 삭제되고 같은 키 덮어쓰기가 안 돼서,
이력이 한 번 날아가면 중복 방지가 통째로 무력화된다.

덤으로 매일 커밋이 쌓이므로 "60일 무활동 시 스케줄 워크플로우 자동 비활성화" 정책에도 걸리지 않는다.

이력 파일이 없거나 깨져도 크래시하지 않는다. 콜드 스타트로 진행하고
슬랙 하단에 `⚠️ 발송 이력 없음` 을 표시한다.

### 3.4 매체 품질 보정
Google News 검색 결과에는 지역지·보도자료 전문 매체가 많이 섞인다.
`reputation.py` 가 **기사의 실제 발행 매체**를 보고 점수를 보정한다
(주요 매체 1.0, 처음 보는 매체 0.45, 보도자료성 0.30).
직접 구독 중인 피드는 감점하지 않는다.

---

## 4. 설정값

`src/config.py` 의 기본값은 모두 환경변수로 덮어쓸 수 있다.

| 변수 | 기본값 | 설명 |
|---|---|---|
| `SLACK_WEBHOOK_URL` | — | **필수** |
| `DRY_RUN` | `false` | 전송 없이 콘솔 출력 |
| `ITEMS_PER_CATEGORY` | `5` | 카테고리별 건수 |
| `MAX_AGE_HOURS_NEWS` | `24` | AI/시사 시간창 |
| `MAX_AGE_HOURS_BIZ` | `168` | 사업 시간창 (7일) |
| `MEDIA_CAP` | `2` | 카테고리별 동일 매체 최대 건수 |
| `DEDUP_ENABLED` | `true` | 이전 날 중복 방지 on/off |
| `DEDUP_LOG_ONLY` | `false` | 차단 없이 로그만 (관찰 모드) |
| `DEDUP_SIMHASH_DISTANCE` | `6` | L2 해밍거리 임계 |
| `DEDUP_TOKEN_OVERLAP` | `2` | L3 핵심어 중복 임계 |
| `HISTORY_RETENTION_DAYS` | `35` | 이력 보존 기간 |
| `CHECK_LINKS` | `true` | 링크 생존 확인 |

### 임계값 튜닝
첫 주는 `DEDUP_LOG_ONLY=true` 로 돌려 **차단하지 않고 로그만** 보는 것을 권장한다.
로그에 차단 사유와 매칭된 과거 제목이 함께 찍히므로 오탐을 눈으로 확인할 수 있다.

| 증상 | 조정 |
|---|---|
| 중요 뉴스가 누락됨 (과차단) | `DEDUP_SIMHASH_DISTANCE=4`, `DEDUP_TOKEN_OVERLAP=3` |
| 같은 사건이 또 옴 (과소차단) | `DEDUP_SIMHASH_DISTANCE=8`, `WINDOW_L3` 확대 |

---

## 5. 구조

```
src/
├── config.py       환경변수 · 상수
├── sources.py      피드 레지스트리 (41개) · 키워드 · 광고 제외 패턴
├── collect.py      병렬 수집 → Article 정규화
├── fingerprint.py  URL 정규화 · SimHash · 사건 토큰 · 일반어 사전
├── dedup.py        이전 날 중복 방지 + 이력 I/O
├── reputation.py   매체 신뢰도 보정
├── rank.py         점수화 · 당일 중복 제거 · 매체 쏠림 방지
├── guard.py        검증 게이트 · 링크 생존 확인
├── slack.py        Block Kit 빌드 · 재시도 전송
└── main.py         오케스트레이션
state/history.json  발송 이력 (자동 커밋)
tests/test_dedup.py 단위 테스트 31개
```

---

## 6. 소스 추가/제거

`src/sources.py` 의 `SOURCES` 리스트에 한 줄 추가하면 된다.

```python
dict(name="매체명", cat="kr", weight=0.9, url="https://example.com/rss"),
```

- `cat`: `ai` | `biz` | `kr` | `world`
- `weight`: 0~1 신뢰도
- `slot`: `biz` 전용 — `kr_startup` | `global_startup` | `local_biz` | `trend`

소스 하나가 죽어도 전체는 계속 돈다. 실패한 소스는 로그에 `✗` 로 표시된다.

알려진 이슈:
- 한국경제·NPR은 클라우드 IP에서 403이 나는 경우가 있다 (GitHub 러너에서는 대체로 정상)
- VentureBeat는 429(레이트리밋)가 잦다
- 중앙일보·KBS·Indie Hackers·TrendHunter는 피드가 죽었거나 차단되어 제외했다

---

## 7. 라이선스 / 이용 범위
공개 RSS 피드의 **제목 + 링크 + 출처**만 사용한다. 본문 크롤링·재배포는 하지 않는다.
