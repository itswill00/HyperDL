# Resolver registry - lazy indirection, logic stays in core.py
from engine.core import (
    resolve_tiktok, resolve_instagram, resolve_facebook, resolve_pinterest,
    resolve_reddit, resolve_twitter, resolve_bluesky, resolve_threads,
    resolve_streamable, resolve_bilibili, resolve_ytdlp, resolve_youtube,
    resolve_youtube_post, fetch_tikwm, is_progressive_instagram_format,
)

RESOLVERS = {
    "tiktok": resolve_tiktok,
    "instagram": resolve_instagram,
    "facebook": resolve_facebook,
    "pinterest": resolve_pinterest,
    "reddit": resolve_reddit,
    "twitter": resolve_twitter,
    "bluesky": resolve_bluesky,
    "threads": resolve_threads,
    "streamable": resolve_streamable,
    "bilibili": resolve_bilibili,
    "youtube": resolve_youtube,
    "ytdlp": resolve_ytdlp,
}

__all__ = ["RESOLVERS"]
