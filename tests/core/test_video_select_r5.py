"""Review r5 of v2 item 4: hashtags follow the same accent rule as words."""
import pytest

from koc.config import load_config
from koc.video_select import select_videos

from tests.core.test_video_select import _ids, _v

BRIEF = {"product": "kem chống nắng", "product_type": "Chống nắng"}


@pytest.mark.parametrize("title", ["Mới về #chồngnàng", "Mới về #chốngnâng", "Hot #rửamát"])
def test_lookalike_accented_hashtags_are_off_topic(title):
    brief = {"product": "sữa rửa mặt", "product_type": "Làm sạch"} if "rửa" in title else BRIEF
    assert select_videos([_v("a", title, 1)], brief, load_config())[0][1]["on_topic"] is False


@pytest.mark.parametrize("title", ["Mới về #kemchongnang", "Mới về #kemchốngnắng", "#KemChốngNắng đây"])
def test_matching_hashtags_are_on_topic(title):
    assert select_videos([_v("a", title, 1)], BRIEF, load_config())[0][1]["on_topic"] is True


def test_three_on_topic_hashtag_videos_beat_unrelated_hashtag_video_with_high_revenue():
    videos = [_v("x", "Hot #chồngnàng #xuhuong", 999), _v("a", "Review #kemchongnang", 3), _v("b", "Mới #kemchốngnắng", 2), _v("c", "Da dầu #chongnang", 1)]
    picked = select_videos(videos, BRIEF, load_config(), n=3)
    assert sorted(_ids(picked)) == ["a", "b", "c"] and all(i["on_topic"] for _, i in picked)


def test_loose_fallback_brief_term_still_folds_hashtags():
    brief = {"product": "sua tam", "product_type": "Khác"}
    assert select_videos([_v("a", "Hot #sữatắm", 1)], brief, load_config())[0][1]["on_topic"] is True
