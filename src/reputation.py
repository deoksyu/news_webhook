"""매체 신뢰도 보정.

Google News 검색 결과에는 지역지·보도자료 전문 매체가 다수 섞인다.
피드 자체의 weight만으로는 이걸 거를 수 없으므로,
**기사의 실제 발행 매체**를 보고 점수를 보정한다.
"""

TIER1 = {
    # 국내 종합·통신
    "연합뉴스", "연합뉴스TV", "뉴시스", "뉴스1", "조선일보", "중앙일보", "동아일보",
    "한겨레", "경향신문", "한국일보", "서울신문", "국민일보", "세계일보", "문화일보",
    "KBS", "KBS 뉴스", "MBC", "MBC 뉴스", "SBS", "SBS 뉴스", "JTBC", "YTN",
    "채널A", "MBN", "TV조선", "노컷뉴스", "오마이뉴스", "프레시안", "시사IN", "한겨레21",
    # 국내 경제·산업
    "매일경제", "한국경제", "서울경제", "머니투데이", "이데일리", "아시아경제",
    "헤럴드경제", "파이낸셜뉴스", "조선비즈", "한경비즈니스", "머니S", "뉴스핌",
    "아주경제", "브릿지경제", "더벨", "인베스트조선",
    # 국내 IT·스타트업
    "전자신문", "디지털타임스", "ZDNet Korea", "지디넷코리아", "블로터", "테크M",
    "AI타임스", "바이라인네트워크", "플래텀", "Platum", "벤처스퀘어", "아웃스탠딩",
    "IT조선", "디지털데일리", "인공지능신문", "로봇신문",
    # 해외
    "Reuters", "Associated Press", "AP News", "BBC", "BBC News", "The Guardian",
    "Al Jazeera", "NPR", "The New York Times", "The Washington Post",
    "The Wall Street Journal", "Financial Times", "Bloomberg", "CNBC", "CNN",
    "Axios", "Politico", "The Economist", "Nikkei Asia", "South China Morning Post",
    "TechCrunch", "The Verge", "MIT Technology Review", "Ars Technica", "Wired",
    "VentureBeat", "Engadget", "The Information", "Semafor", "Rest of World",
    "Hacker News", "Y Combinator", "Product Hunt",
}

# Google News 결과에서 흔히 보이는 비뉴스·보도자료성 신호
LOW_SIGNALS = ("타임즈", "일보닷컴", "프레스", "PR", "뉴스와이어", "보도자료")

UNKNOWN_PENALTY = 0.45   # 처음 보는 매체
LOW_PENALTY = 0.30       # 보도자료성 매체


def source_multiplier(source_name: str, feed_name: str) -> float:
    """0~1 배수. 직접 구독 중인 피드는 감점하지 않는다."""
    if feed_name != "Google News":
        return 1.0

    name = (source_name or "").strip()
    if not name:
        return UNKNOWN_PENALTY

    if name in TIER1:
        return 1.0
    # "연합뉴스TV" 같은 변형 흡수
    for t in TIER1:
        if len(t) >= 3 and (name.startswith(t) or t in name):
            return 0.95

    for sig in LOW_SIGNALS:
        if sig in name:
            return LOW_PENALTY

    return UNKNOWN_PENALTY
