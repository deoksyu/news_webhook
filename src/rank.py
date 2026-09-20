"""점수화 · 당일 중복 제거 · 매체 쏠림 방지 — PRD §8.1~§8.3."""
from . import config as C
from .collect import keyword_score
from .fingerprint import title_bigrams, jaccard, extract_tokens, entity_overlap
from .reputation import source_multiplier

W_FRESH, W_SOURCE, W_KW = 0.30, 0.45, 0.25

JACCARD_THRESHOLD = 0.55
EVENT_TOKEN_OVERLAP = 2      # 핵심어 2개 이상 겹치면 같은 사건으로 간주
ETOKEN_TOPN = 6
COMMON_DF_RATIO = 0.06       # 후보의 6% 이상에 등장하는 토큰은 변별력 없음


def base_score(art):
    max_age = C.MAX_AGE_HOURS[art["category"]]
    freshness = max(0.0, 1.0 - art["age_h"] / max_age)
    weight = art["weight"] * source_multiplier(art["source"], art["feed"])
    art["_eff_weight"] = weight
    return W_FRESH * freshness + W_SOURCE * weight + W_KW * keyword_score(art)


# ------------------------------------------------------------------ 사건 토큰

def _build_token_stats(pool):
    df = {}
    for a in pool:
        for t in set(a["_tokens"]):
            df[t] = df.get(t, 0) + 1
    return df


def _event_tokens(art, df, n_docs):
    """변별력 있는 핵심어 상위 N개."""
    limit = max(3, int(n_docs * COMMON_DF_RATIO))
    toks = [t for t in art["_tokens"] if df.get(t, 0) <= limit]
    if not toks:
        toks = art["_tokens"]
    seen, uniq = set(), []
    for t in toks:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    ranked = sorted(uniq, key=lambda x: (-len(x), uniq.index(x)))[:ETOKEN_TOPN]
    return set(ranked)


def annotate_tokens(articles):
    """카테고리별 문서빈도를 기준으로 변별력 있는 핵심어 집합(_etok)을 붙인다.

    수집 직후 한 번만 호출한다. 이전 날 중복 판정(dedup)과
    당일 중복 제거(rank) 양쪽이 같은 토큰 집합을 공유해야 한다.
    """
    by_cat = {}
    for a in articles:
        a["_tokens"] = extract_tokens(a["title"], drop_source_suffix=False)
        by_cat.setdefault(a["category"], []).append(a)
    for cat, pool in by_cat.items():
        df = _build_token_stats(pool)
        n_docs = max(1, len(pool))
        for a in pool:
            a["_etok"] = _event_tokens(a, df, n_docs)
    return articles


def dedup_intra(articles):
    """같은 실행 안에서 같은 기사·같은 사건을 합친다 (PRD §8.2).

    3단계: ① 제목 bigram Jaccard  ② 사건 키 완전일치  ③ 핵심어 2개 이상 중복
    ③이 '같은 사건, 다른 매체, 다른 제목'을 잡는다.
    """
    articles = sorted(articles, key=lambda a: -a["_score"])
    kept = []
    for art in articles:
        grams = title_bigrams(art["title"])
        dup = False
        for k in kept:
            if jaccard(grams, k["_grams"]) >= JACCARD_THRESHOLD:
                dup = True
                break
            if art["event_key"] == k["event_key"]:
                dup = True
                break
            if entity_overlap(art["_etok"], k["_etok"], EVENT_TOKEN_OVERLAP):
                dup = True
                break
        if not dup:
            art["_grams"] = grams
            kept.append(art)
    return kept


# ------------------------------------------------------------------ 선별

def _pick(pool, n, seen_events, seen_etok, media_count):
    out = []
    for art in pool:
        if len(out) >= n:
            break
        if art["event_key"] in seen_events:
            continue
        if any(entity_overlap(art["_etok"], e, EVENT_TOKEN_OVERLAP) for e in seen_etok):
            continue
        src = art["source"]
        if media_count.get(src, 0) >= C.MEDIA_CAP:
            continue
        out.append(art)
        seen_events.add(art["event_key"])
        seen_etok.append(art["_etok"])
        media_count[src] = media_count.get(src, 0) + 1
    return out


def select(articles, category, n, taken_events, taken_etok):
    """카테고리별 상위 n건 선별. taken_* 은 읽기 전용(카테고리 간 중복 방지용)."""
    pool = [a for a in articles if a["category"] == category]
    if not pool:
        return []
    for a in pool:
        a["_score"] = base_score(a)
        a.setdefault("_etok", set())
    pool = dedup_intra(pool)

    seen_events = set(taken_events)
    seen_etok = list(taken_etok)
    media_count = {}

    if category == "biz":
        picked, chosen = [], set()
        for slot, quota in C.BIZ_SLOTS:
            sub = [a for a in pool if a.get("slot") == slot and id(a) not in chosen]
            got = _pick(sub, quota, seen_events, seen_etok, media_count)
            picked += got
            chosen |= {id(a) for a in got}
        if len(picked) < n:
            rest = [a for a in pool if id(a) not in chosen]
            picked += _pick(rest, n - len(picked), seen_events, seen_etok, media_count)
        return picked[:n]

    return _pick(pool, n, seen_events, seen_etok, media_count)
