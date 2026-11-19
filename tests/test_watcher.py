import itertools

from clipforge.chatlog import Message
from clipforge.watcher import MomentAlerter, watch_file


def _burst(start=100.0, n=15):
    texts = ["OMG", "CLIP IT", "NO WAY!!!", "W W W", "INSANE",
             "POG", "GG GG", "LETS GOOO", "WOW!!!", "CRAZY",
             "OMG OMG", "POGGERS", "CLIP THAT", "FIRE", "W"]
    return [Message(t=start + i * 0.3, author=f"fan{i}", text=texts[i % len(texts)])
            for i in range(n)]


def test_alerter_fires_on_burst():
    alerter = MomentAlerter(window=10.0, min_messages=8,
                            energy_threshold=25.0, cooldown=45.0)
    alerts = [a for a in (alerter.feed(m) for m in _burst()) if a]
    assert len(alerts) == 1
    assert alerts[0]["messages_in_window"] >= 8


def test_alerter_quiet_on_calm_chat():
    alerter = MomentAlerter()
    calm = [Message(t=float(i * 5), author="a", text="nice stream")
            for i in range(30)]
    assert all(alerter.feed(m) is None for m in calm)


def test_alerter_cooldown_suppresses_second_burst():
    alerter = MomentAlerter(window=10.0, min_messages=8,
                            energy_threshold=25.0, cooldown=120.0)
    first = [a for a in (alerter.feed(m) for m in _burst(100.0)) if a]
    second = [a for a in (alerter.feed(m) for m in _burst(130.0)) if a]
    assert len(first) == 1
    assert second == []


def test_watch_file_detects_appended_lines(tmp_path):
    log = tmp_path / "live.txt"
    log.write_text("[0:01] a: hello\n", encoding="utf-8")
    burst_lines = "".join(
        f"[1:{40 + i // 60:02d}] fan{i}: {text}\n"
        for i, text in enumerate(
            ["OMG", "CLIP IT", "NO WAY!!!", "W W W", "INSANE", "POG",
             "GG GG", "LETS GOOO", "WOW!!!", "CRAZY", "OMG OMG",
             "POGGERS", "CLIP THAT", "FIRE", "W"])
    )
    state = {"appended": False, "ticks": 0}
    base = itertools.count(0.0, 0.1)

    def fake_clock():
        return next(base)

    def fake_sleeper(_seconds):
        state["ticks"] += 1
        if not state["appended"]:
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(burst_lines)
            state["appended"] = True

    seen = []
    alerts = watch_file(str(log), duration=1.0, poll_interval=0.1,
                        on_alert=seen.append, clock=fake_clock,
                        sleeper=fake_sleeper)
    assert len(alerts) == 1
    assert seen == alerts
