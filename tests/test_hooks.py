from clipforge.hooks import DEFAULT_GAME_TAGS, format_post_text, generate_hooks
from clipforge.hype import Moment


def _moment(category="clutch", keywords=("clip it", "insane")):
    return Moment(start=92.0, end=102.0, peak=100.0, score=87.0, messages=31,
                  keywords=list(keywords), category=category,
                  samples=["OMG CLIP IT"])


def test_three_distinct_titles():
    hooks = generate_hooks(_moment())
    assert len(hooks["titles"]) == 3
    assert len(set(hooks["titles"])) == 3


def test_default_hashtags_are_gta_set():
    hooks = generate_hooks(_moment())
    for tag in DEFAULT_GAME_TAGS:
        assert tag in hooks["hashtags"]
    assert "#GTAVI" in hooks["hashtags"]


def test_custom_game_and_tags():
    hooks = generate_hooks(_moment(), game="Valorant",
                           game_tags=["#Valorant", "#FPS"])
    assert hooks["hashtags"][:2] == ["#Valorant", "#FPS"]
    assert "#GTAVI" not in hooks["hashtags"]
    assert any("Valorant" in t for t in hooks["titles"])


def test_caption_mentions_top_keyword():
    hooks = generate_hooks(_moment())
    assert "CLIP IT" in hooks["caption"]


def test_category_changes_titles():
    funny = generate_hooks(_moment(category="funny", keywords=("lol",)))
    clutch = generate_hooks(_moment(category="clutch"))
    assert funny["titles"] != clutch["titles"]
    assert "#FunnyMoments" in funny["hashtags"]


def test_post_text_contains_all_parts():
    m = _moment()
    text = format_post_text(m, generate_hooks(m))
    assert "TITLE OPTIONS" in text
    assert "CAPTION:" in text
    assert "HASHTAGS:" in text
    assert "#GTAVI" in text
