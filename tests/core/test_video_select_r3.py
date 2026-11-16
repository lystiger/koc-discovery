"""Review r3 of v2 item 4: word comparison is symmetric for unaccented brief products."""
from koc.config import load_config
from koc.video_select import select_videos

from tests.core.test_video_select import BRIEF, _ids, _v


def test_unaccented_brief_product_matches_accented_title_and_beats_shampoo():
    brief = {"product": "sua tam", "product_type": "Khác"}
    picked = select_videos([_v("shampoo", "Dầu gội hương hoa", 999), _v("body", "Sữa tắm hương hoa", 1)], brief, load_config())
    assert _ids(picked) == ["body", "shampoo"]
    assert picked[0][1]["on_topic"] is True and picked[1][1]["on_topic"] is False


def test_two_accented_words_still_compare_exactly():
    cfg = load_config()
    assert select_videos([_v("n", "kem dưỡng chống lão hóa, nâng cơ", 1)], BRIEF, cfg)[0][1]["on_topic"] is False
    assert select_videos([_v("n", "chống nâng", 1)], BRIEF, cfg)[0][1]["on_topic"] is False
    assert select_videos([_v("a", "kem chong nang cho da dầu", 1)], BRIEF, cfg)[0][1]["on_topic"] is True
