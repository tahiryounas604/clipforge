"""Shared chat-log fixtures: a quiet stream and a spiky one."""

from clipforge.chatlog import Message


def quiet_messages(duration=300, every=2.0):
    """Calm chat: one plain message every couple of seconds."""
    texts = ["nice", "hello everyone", "good game", "that was close",
             "hello", "good play", "nice one", "wp"]
    out = []
    t = 0.0
    i = 0
    while t < duration:
        out.append(Message(t=t, author=f"user{i % 7}", text=texts[i % len(texts)]))
        t += every
        i += 1
    return out


def spiky_messages():
    """Quiet chat with one eruption around t=100-106."""
    msgs = quiet_messages(duration=300, every=2.0)
    burst_texts = [
        "OMG OMG OMG", "CLIP IT", "NO WAY!!!", "W W W W", "INSANE",
        "POGGERS", "WHAT JUST HAPPENED", "GG GG GG", "LETS GOOO",
        "CLIP IT NOW", "WOW!!!", "THAT WAS CRAZY", "POG", "OMG",
        "NO WAY NO WAY", "W", "GG", "INSANE CLUTCH", "LMAO WHAT",
        "CLIP IT!!!", "WOOOO", "FIRE", "GOAT", "OMG!!!", "W W W",
        "LETS GO", "POG POG", "CRAZY", "NO WAY", "CLIP THAT",
    ]
    for i, text in enumerate(burst_texts):
        msgs.append(Message(t=100.0 + i * 0.2, author=f"fan{i}", text=text))
    return sorted(msgs, key=lambda m: m.t)
