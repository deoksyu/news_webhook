"""URL 정규화 · 제목 정규화 · SimHash · 사건 키.

PRD §8.4.1 (수정판)
- Google News 리디렉션 URL은 서버에서 원문으로 해석할 수 없음(JS 인터스티셜).
  대신 RSS의 <guid>(= 안정적인 CBMi 기사 ID)를 L1 지문으로 사용한다.
"""
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# ---------------------------------------------------------------- URL

TRACKING_PARAMS_PREFIX = ("utm_", "at_", "pk_", "mc_", "_hs")
TRACKING_PARAMS = {
    "oc", "ref", "referrer", "fbclid", "gclid", "cmp", "CMP", "ito", "smid",
    "partner", "ncid", "sh", "source", "spm", "igshid", "mbid", "guccounter",
    "__twitter_impression", "s", "amp",
}


def normalize_url(url: str) -> str:
    """추적 파라미터·프래그먼트·AMP 경로를 제거한 정규 URL."""
    if not url:
        return ""
    try:
        sp = urlsplit(url.strip())
    except ValueError:
        return url.strip()

    scheme = (sp.scheme or "https").lower()
    host = (sp.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("amp."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]

    path = sp.path or "/"
    path = re.sub(r"/amp/?$", "", path)
    path = re.sub(r"^/amp/", "/", path)
    if len(path) > 1:
        path = path.rstrip("/")

    kept = [
        (k, v) for k, v in parse_qsl(sp.query, keep_blank_values=False)
        if k not in TRACKING_PARAMS and not k.lower().startswith(TRACKING_PARAMS_PREFIX)
    ]
    kept.sort()
    query = urlencode(kept)

    return urlunsplit((scheme, host, path, query, ""))


def url_identity(url: str, guid: str = "") -> str:
    """L1 지문 원본 문자열.

    Google News 링크는 매번 달라질 수 있는 리디렉션 URL이므로,
    안정적인 기사 ID(guid)를 식별자로 쓴다.
    """
    host = ""
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        pass
    if "news.google.com" in host:
        token = (guid or "").strip()
        if not token:
            m = re.search(r"/articles/([A-Za-z0-9_\-]+)", url)
            token = m.group(1) if m else url
        return "gnews:" + token.split("?")[0]
    return normalize_url(url)


def url_hash(url: str, guid: str = "") -> str:
    return hashlib.sha1(url_identity(url, guid).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 제목

# [속보] [단독] (종합) (종합3보) (2보) <신년기획> 【단독】 …
_TAG_RE = re.compile(r"[\[\(\<【][^\]\)\>】]{0,14}[\]\)\>】]")
_PUNCT_RE = re.compile(r"[\"'“”‘’·…\.,!?~\-–—:;/|\\\*\#\$\^&\+=_​]")
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]", flags=re.UNICODE
)
_SPACE_RE = re.compile(r"\s+")

# Google News 제목 접미: " - 매체명"
_GN_SUFFIX_RE = re.compile(r"\s+[-–—]\s+[^\-–—]{2,20}$")


def strip_source_suffix(title: str) -> tuple:
    """'제목 - 매체명' → ('제목', '매체명'). 못 찾으면 (원문, '')."""
    m = _GN_SUFFIX_RE.search(title or "")
    if not m:
        return (title or "").strip(), ""
    src = m.group(0).lstrip(" -–—").strip()
    return title[: m.start()].strip(), src


def clean_title(title: str, drop_source_suffix: bool = True) -> str:
    t = title or ""
    if drop_source_suffix:
        t, _ = strip_source_suffix(t)
    t = _TAG_RE.sub(" ", t)
    t = _EMOJI_RE.sub(" ", t)
    t = _PUNCT_RE.sub(" ", t)
    t = _SPACE_RE.sub(" ", t).strip().lower()
    return t


# ---------------------------------------------------------------- SimHash

_MASK64 = (1 << 64) - 1


def _hash64(s: str) -> int:
    return int.from_bytes(hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest(), "big")


def simhash(text: str, ngram: int = 3) -> int:
    """문자 n-gram 기반 64bit SimHash."""
    t = (text or "").replace(" ", "")
    if len(t) < ngram:
        t = (t + "___")[: max(ngram, 1)]
    grams = [t[i : i + ngram] for i in range(len(t) - ngram + 1)] or [t]

    weights = {}
    for g in grams:
        weights[g] = weights.get(g, 0) + 1

    v = [0] * 64
    for g, w in weights.items():
        h = _hash64(g)
        for i in range(64):
            if h & (1 << i):
                v[i] += w
            else:
                v[i] -= w
    out = 0
    for i in range(64):
        if v[i] > 0:
            out |= 1 << i
    return out & _MASK64


def hamming(a: int, b: int) -> int:
    return bin((a ^ b) & _MASK64).count("1")


# ---------------------------------------------------------------- 사건 키

STOPWORDS = {
    # 한국어
    "대한", "관련", "위해", "통해", "밝혀", "밝혔", "전망", "가능", "예정", "결정", "지난",
    "올해", "내년", "작년", "오늘", "내일", "어제", "이번", "우리", "그는", "그녀", "하는",
    "한다", "했다", "된다", "있다", "없다", "이날", "당시", "최근", "가장", "다시", "모두",
    "정도", "경우", "상황", "이후", "이전", "현재", "기자", "특파원", "종합", "속보", "단독",
    "사진", "영상", "인터뷰", "칼럼", "사설", "오피니언", "뉴스", "보도", "기사", "라며",
    "면서", "으로", "에서", "에게", "부터", "까지", "보다", "처럼", "만큼", "또한", "그리고",
    # 영어
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "had", "are",
    "was", "were", "will", "would", "could", "should", "says", "said", "after", "amid",
    "over", "into", "about", "more", "than", "what", "when", "where", "which", "who",
    "how", "why", "new", "its", "his", "her", "their", "our", "you", "they", "but",
    "not", "can", "may", "now", "one", "two", "out", "off", "all", "some", "been",
}

_TOKEN_RE = re.compile(r"[가-힣]{2,8}|[A-Za-z][A-Za-z0-9']{2,}|[0-9]{4,}")
_JOSA_RE = re.compile(r"(은|는|이|가|을|를|에|의|와|과|도|만|로|으로|에서|에게|부터|까지|라며|라고|이라|하며|한다|했다|이다)$")


def _strip_josa(tok: str) -> str:
    if len(tok) >= 3:
        stripped = _JOSA_RE.sub("", tok)
        if len(stripped) >= 2:
            return stripped
    return tok


def extract_tokens(title: str, drop_source_suffix: bool = True) -> list:
    t = clean_title(title, drop_source_suffix)
    toks = []
    for raw in _TOKEN_RE.findall(t):
        tok = _strip_josa(raw)
        if tok in STOPWORDS or len(tok) < 2:
            continue
        toks.append(tok)
    return toks


def event_key(title: str, n_tokens: int = 4, drop_source_suffix: bool = True) -> str:
    """제목 핵심어 n개를 정렬·결합한 사건 식별자."""
    toks = extract_tokens(title, drop_source_suffix)
    if not toks:
        return hashlib.sha1(clean_title(title).encode("utf-8")).hexdigest()

    seen, uniq = set(), []
    for t in toks:
        if t not in seen:
            seen.add(t)
            uniq.append(t)

    # 긴 토큰일수록 고유명사일 확률이 높다 → 길이 내림차순, 동률은 등장 순서
    ranked = sorted(uniq, key=lambda x: (-len(x), uniq.index(x)))[:n_tokens]
    key = "|".join(sorted(ranked))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def title_bigrams(title: str) -> set:
    t = clean_title(title).replace(" ", "")
    return {t[i : i + 2] for i in range(len(t) - 1)} or {t}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------- 일반어

# 사건을 특정하지 못하는 서술어·일반명사.
# "targeted + ballistic" 처럼 일반어끼리만 겹치는 경우를 같은 사건으로 오판하지 않기 위함.
GENERIC_TOKENS = {
    # 영어 — 행위·규모·일반 주체
    "targeted", "target", "targets", "attack", "attacks", "attacked", "strike",
    "strikes", "struck", "killed", "kills", "dead", "death", "deaths", "injured",
    "hundreds", "thousands", "millions", "dozens", "ballistic", "missile",
    "missiles", "drone", "drones", "capital", "forces", "military", "army",
    "troops", "war", "conflict", "report", "reports", "reported", "claims",
    "claimed", "warns", "warned", "urges", "calls", "called", "backs", "accused",
    "talks", "meeting", "summit", "deal", "group", "state", "states", "country",
    "countries", "government", "minister", "ministers", "president", "official",
    "officials", "leader", "leaders", "plans", "plan", "police", "people",
    "city", "world", "news", "latest", "live", "updates", "first", "second",
    "year", "years", "day", "days", "week", "weeks", "month", "months",
    "million", "billion", "percent", "market", "company", "companies",
    # 한국어 — 서술·일반 주체
    "논란", "공개", "발표", "검토", "추진", "반발", "비판", "지적", "강조", "촉구",
    "요구", "주장", "우려", "전망", "계획", "방침", "입장", "회의", "회담", "협의",
    "정부", "대통령", "장관", "의원", "국회", "위원회", "당국", "관계자",
    "사건", "사고", "조사", "수사", "혐의", "경찰", "검찰", "법원", "재판",
    "시민", "지역", "전국", "규모", "기업", "시장", "사업", "지원", "확대",
    "강화", "도입", "출시", "개최", "진행", "모집", "운영", "체결", "선정",
    "참여", "제공", "가능", "필요", "문제", "상황", "상태", "결과", "효과",
    "억원", "만원", "천억", "달러", "수준", "이상", "이하", "최대", "최소",
}


def is_generic(token: str) -> bool:
    return token in GENERIC_TOKENS


def entity_overlap(a: set, b: set, min_n: int = 2) -> int:
    """공통 토큰 수. 단, 고유성 있는 토큰이 최소 1개 포함될 때만 인정한다.

    조건 미충족 시 0을 반환한다.
    """
    shared = a & b
    if len(shared) < min_n:
        return 0
    if not any(not is_generic(t) for t in shared):
        return 0
    return len(shared)
