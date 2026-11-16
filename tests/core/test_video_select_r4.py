"""Review r4 of v2 item 4: configured terms are canonical; only a configless brief product may fold loosely."""
from koc.config import load_config
from koc.video_select import select_videos, topic_terms

from tests.core.test_video_select import _ids, _v


def test_unaccented_brief_is_dropped_when_the_type_has_configured_terms():
    cfg = load_config()
    brief = {"product": "chong nang", "product_type": "Chống nắng"}
    assert "chong nang" not in topic_terms(brief, cfg)
    picked = select_videos([_v("wife", "chồng - Nàng", 999), _v("sun", "Kem chống nắng cho da dầu", 1)], brief, cfg)
    assert _ids(picked) == ["sun", "wife"]
    assert [i["on_topic"] for _, i in picked] == [True, False]
    assert select_videos([_v("w", "rửa mát", 1)], {"product": "rua mat", "product_type": "Làm sạch"}, cfg)[0][1]["on_topic"] is False


def test_accented_brief_is_added_and_configured_spelling_wins_on_duplicates():
    cfg = load_config()
    terms = topic_terms({"product": "kem chống nắng", "product_type": "Chống nắng"}, cfg)
    assert terms.count("kem chống nắng") == 1 and not terms[0].loose
    assert "sữa chống nắng" in topic_terms({"product": "sữa chống nắng", "product_type": "Chống nắng"}, cfg)
    assert [str(t) for t in topic_terms({"product": "Kem Chong Nang", "product_type": "Chống nắng"}, cfg)].count("Kem Chong Nang") == 0


def test_type_without_configured_terms_lets_unaccented_brief_fold_loosely():
    cfg = load_config()
    brief = {"product": "sua tam", "product_type": "Khác"}
    assert topic_terms(brief, cfg)[0].loose is True
    picked = select_videos([_v("shampoo", "Dầu gội hương hoa", 999), _v("body", "Sữa tắm hương hoa", 1)], brief, cfg)
    assert _ids(picked) == ["body", "shampoo"]
    assert select_videos([_v("x", "Sữa tắm", 1)], {"product": "sua tam", "product_type": "không có loại"}, cfg)[0][1]["on_topic"] is True


def test_earlier_cases_still_hold():
    cfg = load_config()
    brief = {"product": "kem chống nắng", "product_type": "Chống nắng"}
    assert select_videos([_v("n", "kem dưỡng chống lão hóa, nâng cơ", 1)], brief, cfg)[0][1]["on_topic"] is False
    assert select_videos([_v("n", "chống nâng", 1)], brief, cfg)[0][1]["on_topic"] is False
    assert select_videos([_v("a", "kem chong nang cho da dầu", 1)], brief, cfg)[0][1]["on_topic"] is True
    assert select_videos([_v("a", "Mới về #kemchongnang", 1)], brief, cfg)[0][1]["on_topic"] is True
