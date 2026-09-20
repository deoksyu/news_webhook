"""피드 레지스트리.

PRD §7 — 2026-09-20 실제 HTTP 호출로 검증된 엔드포인트만 등록.
weight: 소스 신뢰도(0~1). 점수 공식의 source_weight.
slot:   사업(biz) 카테고리에서만 사용하는 하위 슬롯.
"""

GN = "https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"


def _gn(query):
    from urllib.parse import quote
    return GN.format(q=quote(query))


SOURCES = [
    # ---------------- AI (FR-1) ----------------
    dict(name="TechCrunch AI", cat="ai", weight=1.00,
         url="https://techcrunch.com/category/artificial-intelligence/feed/"),
    dict(name="The Verge AI", cat="ai", weight=0.95,
         url="https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    dict(name="MIT Tech Review", cat="ai", weight=1.00,
         url="https://www.technologyreview.com/topic/artificial-intelligence/feed"),
    dict(name="Ars Technica", cat="ai", weight=0.90,
         url="https://feeds.arstechnica.com/arstechnica/technology-lab"),
    dict(name="Google AI Blog", cat="ai", weight=0.85,
         url="https://blog.google/technology/ai/rss/"),
    dict(name="OpenAI News", cat="ai", weight=0.85,
         url="https://openai.com/news/rss.xml"),
    dict(name="Hugging Face", cat="ai", weight=0.70,
         url="https://huggingface.co/blog/feed.xml"),
    dict(name="전자신문", cat="ai", weight=0.90,
         url="https://rss.etnews.com/Section901.xml"),
    dict(name="Google News", cat="ai", weight=0.70, url=_gn("인공지능 when:1d")),
    dict(name="Google News", cat="ai", weight=0.70, url=_gn("AI 반도체 OR 생성형AI when:1d")),
    dict(name="VentureBeat AI", cat="ai", weight=0.75,
         url="https://venturebeat.com/category/ai/feed/"),

    # ---------------- 사업 (FR-2) ----------------
    dict(name="Platum", cat="biz", slot="kr_startup", weight=1.00,
         url="https://platum.kr/feed"),
    dict(name="벤처스퀘어", cat="biz", slot="kr_startup", weight=0.95,
         url="https://www.venturesquare.net/feed/"),
    dict(name="바이라인네트워크", cat="biz", slot="kr_startup", weight=0.90,
         url="https://byline.network/feed/"),
    dict(name="아웃스탠딩", cat="biz", slot="kr_startup", weight=0.90,
         url="https://outstanding.kr/feed"),
    dict(name="Google News", cat="biz", slot="kr_startup", weight=0.70,
         url=_gn("스타트업 투자 유치 when:3d")),

    dict(name="TechCrunch Startups", cat="biz", slot="global_startup", weight=1.00,
         url="https://techcrunch.com/category/startups/feed/"),
    dict(name="TechCrunch Venture", cat="biz", slot="global_startup", weight=0.95,
         url="https://techcrunch.com/category/venture/feed/"),
    dict(name="Y Combinator", cat="biz", slot="global_startup", weight=0.85,
         url="https://www.ycombinator.com/blog/rss"),
    dict(name="Product Hunt", cat="biz", slot="global_startup", weight=0.60,
         url="https://www.producthunt.com/feed"),

    dict(name="Google News", cat="biz", slot="local_biz", weight=0.70,
         url=_gn("소상공인 창업 when:7d")),
    dict(name="Google News", cat="biz", slot="local_biz", weight=0.70,
         url=_gn("자영업 성공 사례 when:7d")),
    dict(name="Google News", cat="biz", slot="local_biz", weight=0.70,
         url=_gn("공간 대여 창업 OR 카페 창업 트렌드 when:7d")),

    dict(name="Hacker News", cat="biz", slot="trend", weight=0.65,
         url="https://hnrss.org/frontpage?points=150"),
    dict(name="r/Entrepreneur", cat="biz", slot="trend", weight=0.42,
         url="https://www.reddit.com/r/Entrepreneur/top/.rss?t=day"),
    dict(name="Google News", cat="biz", slot="trend", weight=0.70,
         url=_gn("창업 트렌드 OR 신사업 아이템 when:7d")),

    # ---------------- 국내 시사/정치 (FR-3) ----------------
    dict(name="연합뉴스", cat="kr", weight=1.00,
         url="https://www.yna.co.kr/rss/politics.xml"),
    dict(name="연합뉴스", cat="kr", weight=0.95,
         url="https://www.yna.co.kr/rss/economy.xml"),
    dict(name="한겨레", cat="kr", weight=0.90, url="https://www.hani.co.kr/rss/"),
    dict(name="경향신문", cat="kr", weight=0.90,
         url="https://www.khan.co.kr/rss/rssdata/total_news.xml"),
    dict(name="조선일보", cat="kr", weight=0.90,
         url="https://www.chosun.com/arc/outboundfeeds/rss/category/politics/?outputType=xml"),
    dict(name="SBS", cat="kr", weight=0.85,
         url="https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=01"),
    dict(name="한국경제", cat="kr", weight=0.85,
         url="https://www.hankyung.com/feed/economy"),
    dict(name="매일경제", cat="kr", weight=0.85,
         url="https://www.mk.co.kr/rss/30000001/"),
    dict(name="Google News", cat="kr", weight=0.70,
         url="https://news.google.com/rss/headlines/section/topic/NATION?hl=ko&gl=KR&ceid=KR:ko"),

    # ---------------- 세계 시사/정치 (FR-4) ----------------
    dict(name="BBC World", cat="world", weight=1.00,
         url="https://feeds.bbci.co.uk/news/world/rss.xml"),
    dict(name="The Guardian", cat="world", weight=0.95,
         url="https://www.theguardian.com/world/rss"),
    dict(name="Al Jazeera", cat="world", weight=0.90,
         url="https://www.aljazeera.com/xml/rss/all.xml"),
    dict(name="NPR", cat="world", weight=0.85,
         url="https://feeds.npr.org/1004/rss.xml"),
    dict(name="연합뉴스", cat="world", weight=0.90,
         url="https://www.yna.co.kr/rss/international.xml"),
    dict(name="Google News", cat="world", weight=0.70,
         url="https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en"),
]


# 광고·행사홍보·공지성 글 제외 패턴 (제목 소문자 기준 부분일치)
PROMO_PATTERNS = [
    "exhibit at", "disrupt 2026", "disrupt 2027", "last chance", "final hours",
    "final 24 hours", "tickets", "ticket prices", "save $", "register now",
    "apply now", "deadline to", "sponsored", "webinar", "join us at",
    "早期", "early bird", "don't miss", "book your", "sale ends",
    "is coming to", "meet us at", "now open for", "call for speakers",
    "구독하기", "이벤트 참여", "사전등록", "참가 신청", "모집 공고", "채용공고",
    "[부고]", "[인사]", "[동정]", "인사·동정", "[포토]", "[화보]",
    "오늘의 운세", "오늘의 날씨", "주요 일정", "[표]", "[게시판]",
]

# 카테고리별 키워드 사전 (keyword_match 점수용)
KEYWORDS = {
    "ai": ["ai", "인공지능", "llm", "gpt", "claude", "gemini", "openai", "anthropic",
           "머신러닝", "딥러닝", "생성형", "chatgpt", "model", "모델", "반도체", "gpu",
           "로봇", "자율주행", "에이전트", "agent"],
    "biz": ["창업", "스타트업", "투자", "유치", "시리즈", "매출", "성공", "아이템",
            "사업", "폐업", "상권", "소상공인", "자영업", "브랜드", "인수", "m&a",
            "startup", "funding", "raises", "founder", "revenue", "launch", "acquire",
            "seed", "series a", "ipo"],
    "kr": ["대통령", "국회", "정부", "여당", "야당", "국민의힘", "더불어민주당", "장관",
           "총리", "예산", "법안", "개헌", "외교", "북한", "검찰", "법원", "경제",
           "물가", "부동산", "금리", "노동", "선거"],
    "world": ["election", "president", "government", "war", "ukraine", "russia", "china",
              "israel", "gaza", "trump", "eu", "nato", "un ", "summit", "sanction",
              "trade", "tariff", "minister", "parliament", "protest", "military",
              "미국", "중국", "러시아", "우크라", "이스라엘", "유엔", "정상회담"],
}
