"""Hook, title, caption and hashtag generation.

Template-based on purpose. ClipForge does **not** use an AI model
and makes no virality promises: these are starting-point drafts
built from what chat actually said (the dominant reaction category
and top keywords), for the creator to edit before posting.
"""

from __future__ import annotations

from .hype import Moment

DEFAULT_GAME_TAGS = ["#GTAVI", "#GTA6", "#GTA", "#Gaming", "#Shorts"]

_CATEGORY_TAGS = {
    "funny": ["#FunnyMoments", "#Fail"],
    "clutch": ["#Clutch", "#ProGamer"],
    "chaos": ["#Chaos", "#NoWay"],
    "hype": ["#Hype", "#ViralClip"],
}

# Three title templates per category; {kw} is the top chat keyword
# (upper-cased, as chat shouted it), {game} the game name.
_TITLES = {
    "funny": [
        "This {game} fail made chat lose it 😂",
        "Chat could NOT stop laughing at this…",
        "The dumbest {game} moment of the stream 💀",
    ],
    "clutch": [
        "The {game} clutch that broke chat 🔥",
        "Chat went INSANE over this play",
        "Nobody believed this clutch was possible",
    ],
    "chaos": [
        "Pure {game} chaos — chat exploded",
        "Nobody saw this coming 😳",
        "The moment everything went wrong (and right)",
    ],
    "hype": [
        "Chat EXPLODED at this {game} moment",
        "The clip everyone in chat demanded",
        "This is why you watch the stream live",
    ],
}

_CAPTIONS = {
    "funny": "Chat was crying laughing at this one 😂 Full stream moment, clipped by request.",
    "clutch": "The play that had the whole chat on its feet. GG.",
    "chaos": "Absolute chaos. Chat did not recover for a full minute.",
    "hype": "Chat demanded this clip — here it is. The energy was unreal.",
}


def generate_hooks(moment: Moment, game: str = "GTA VI",
                   game_tags: list[str] | None = None) -> dict:
    """Build title options, a caption and hashtags for *moment*.

    Returns ``{"titles": [3 distinct strings], "caption": str,
    "hashtags": [..]}``. Pure function of the moment's category and
    keywords — same moment in, same hooks out.
    """
    category = moment.category if moment.category in _TITLES else "hype"
    kw = (moment.keywords[0].upper() if moment.keywords else "WOW")
    titles = []
    for template in _TITLES[category]:
        title = template.format(game=game, kw=kw)
        if title not in titles:
            titles.append(title)
    # Guarantee three distinct options even for custom categories.
    fallback = [
        f"Chat lost it over this {game} moment",
        "The moment the whole stream felt",
        f"As seen live — the {game} clip chat asked for",
    ]
    for extra in fallback:
        if len(titles) >= 3:
            break
        if extra not in titles:
            titles.append(extra)
    tags = list(game_tags) if game_tags is not None else list(DEFAULT_GAME_TAGS)
    for tag in _CATEGORY_TAGS.get(category, []):
        if tag not in tags:
            tags.append(tag)
    caption = _CAPTIONS[category]
    if moment.keywords:
        caption += f" (chat: \"{kw}!\")"
    return {"titles": titles[:3], "caption": caption, "hashtags": tags}


def format_post_text(moment: Moment, hooks: dict) -> str:
    """The post.txt body for one clip: titles, caption, hashtags."""
    lines = ["TITLE OPTIONS (pick one, edit freely):"]
    for i, title in enumerate(hooks["titles"], 1):
        lines.append(f"{i}. {title}")
    lines += [
        "",
        "CAPTION:",
        hooks["caption"],
        "",
        "HASHTAGS:",
        " ".join(hooks["hashtags"]),
        "",
        f"(Moment: {moment.start:.0f}s–{moment.end:.0f}s into the stream, "
        f"chat-hype score {moment.score:.0f}/100, category: {moment.category}.)",
    ]
    return "\n".join(lines) + "\n"
