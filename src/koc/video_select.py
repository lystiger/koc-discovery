"""S3 video selection: rank a creator's candidate videos by how well they match the brief's product.

Keyword match only (no embeddings): the video title plus the attached product name, when the API gives one, is
compared with the brief product and the terms of its product type in config/video_topics.yaml as whole phrases.
Accented text keeps its diacritics; text typed without accents is folded (lowercase, d-stroke -> d).
Score = number of distinct terms found. Ties break by revenue.
"""
import re
import unicodedata


def fold_text(text) -> str:
    """Lowercase, strip combining marks, map the Vietnamese d-stroke to d."""
    decomposed = unicodedata.normalize("NFD", str(text or "").lower())
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.replace("đ", "d")


def _words(text) -> list[str]:
    """Letter runs and digit runs of NFC-lowercased text (diacritics kept): 'SPF50' -> ['spf', '50']."""
    return re.findall(r"[^\W\d_]+|\d+", unicodedata.normalize("NFC", str(text or "").lower()))


def _tokens(text) -> list[str]:
    return _words(fold_text(text))


class _Term(str):
    """A topic term; loose=True lets its unaccented words fold-match accented title words (fallback brief product only)."""
    loose = False


def _is_accented(text) -> bool:
    nfc = unicodedata.normalize("NFC", str(text or "").lower())
    return fold_text(nfc) != nfc


def topic_terms(brief: dict, config: dict) -> list[str]:
    """Configured terms of the product type first (canonical, accented), then the brief product when it adds something.

    The brief product is added when it is accented, or when the type has no configured terms; only in that fallback
    may an unaccented brief term fold-match accented titles. A configured spelling wins over the same folded phrase.
    """
    topics = config.get("video_topics") or {}
    product_type = brief.get("product_type")
    if product_type not in topics:  # no type given (older runs): the type whose name is inside the product name
        product_type = next((name for name in topics if fold_text(name) in fold_text(brief.get("product"))), None)
    configured = list(topics.get(product_type) or [])
    product = brief.get("product")
    candidates = [(term, False) for term in configured]
    if product and (_is_accented(product) or not configured):
        candidates.append((product, not configured))
    seen, terms = set(), []
    for term, loose in candidates:
        key = " ".join(_tokens(term))
        if key and key not in seen:
            seen.add(key)
            item = _Term(str(term))
            item.loose = loose
            terms.append(item)
    return terms


def _word_matches(title_word: str, term_word: str, loose: bool = False) -> bool:
    """Identical words, or equal once folded when the TITLE word has no diacritics.

    Two accented words compare exactly ('nâng' is not 'nắng'). With loose=True an unaccented term word also
    fold-matches an accented title word (unaccented brief product with no configured terms).
    """
    if title_word == term_word:
        return True
    title_plain, term_plain = fold_text(title_word), fold_text(term_word)
    return title_plain == term_plain and (title_plain == title_word or (loose and term_plain == term_word))


def _phrase_in(words: list[str], phrase: list[str], loose: bool = False) -> bool:
    n = len(phrase)
    return bool(phrase) and any(all(_word_matches(words[i + j], phrase[j], loose) for j in range(n)) for i in range(len(words) - n + 1))


def _matches(term: str, text: str) -> bool:
    """Whole term as a contiguous phrase between word boundaries, judged word by word.

    A title word matches a term word when it is identical (diacritics kept: 'nâng' is not 'nắng') or when the
    title word has no diacritics and equals the term word folded ('chong' is 'chống'). Loose terms also fold-match
    accented title words. Multi-word terms also match
    a hashtag that glues them together: unaccented (#kemchongnang) folded, accented (#kemchốngnắng) exactly.
    """
    if _phrase_in(_words(text), _words(term), getattr(term, "loose", False)):
        return True
    if len(_words(term)) < 2:
        return False
    loose = getattr(term, "loose", False)
    exact, folded = "".join(_words(term)), "".join(_tokens(term))
    for tag in re.findall(r"#(\w+)", unicodedata.normalize("NFC", str(text or "").lower())):
        if folded in tag.replace(" ", "") and fold_text(tag) == tag:  # hashtag typed without accents
            return True
        if loose and folded in fold_text(tag):
            return True
        if exact in tag:  # accented hashtag: same rule as words, it must carry the term's own accents
            return True
    return False


def score_video(video: dict, terms: list[str]) -> dict:
    text = f"{video.get('video_title') or ''} {video.get('product_name') or ''}"
    matched = [term for term in terms if _matches(term, text)]
    return {"on_topic": bool(matched), "score": len(matched), "matched_terms": matched}


def select_videos(videos: list[dict], brief: dict, config: dict, n: int = 3) -> list[tuple[dict, dict]]:
    """Top n [(video, {"on_topic","score","matched_terms"})]: on-topic by score then revenue, then off-topic by revenue."""
    terms = topic_terms(brief, config)
    scored = [(video, score_video(video, terms)) for video in videos]
    scored.sort(key=lambda item: (-item[1]["score"], -float(item[0].get("revenue") or 0)))
    return scored[:n]
