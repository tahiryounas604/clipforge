from clipforge.hype import detect_moments, score_message
from tests.fixtures import quiet_messages, spiky_messages


def test_score_plain_message_is_zero():
    s = score_message("nice stream today")
    assert s.score == 0.0
    assert s.keywords == []


def test_score_keywords_and_category():
    s = score_message("OMG CLIP IT that was insane")
    assert "clip it" in s.keywords
    assert "omg" in s.keywords
    assert s.score >= 5.0
    assert s.category in ("hype", "clutch")


def test_score_caps_and_exclamations():
    loud = score_message("NO WAY!!!!")
    calm = score_message("no way")
    assert loud.score > calm.score


def test_score_repeated_char_burst():
    s = score_message("LOOOOOL")
    assert s.score > 0


def test_quiet_chat_produces_zero_moments():
    assert detect_moments(quiet_messages()) == []


def test_spiky_chat_finds_the_eruption():
    moments = detect_moments(spiky_messages())
    assert len(moments) == 1
    m = moments[0]
    assert 90.0 <= m.peak <= 120.0
    assert m.messages >= 20
    assert m.score > 40
    assert m.keywords  # hype keywords captured
    assert m.samples


def test_empty_chat_produces_zero_moments():
    assert detect_moments([]) == []


def test_threshold_is_configurable():
    msgs = spiky_messages()
    # An impossible spike factor must find nothing.
    assert detect_moments(msgs, spike_factor=10_000.0) == []
    # A very low bar still finds the eruption.
    assert detect_moments(msgs, spike_factor=1.0,
                          min_window_messages=5) != []


def test_moment_dict_round_trip_shape():
    m = detect_moments(spiky_messages())[0].to_dict()
    for key in ("start", "end", "peak", "score", "messages",
                "keywords", "category", "samples"):
        assert key in m
