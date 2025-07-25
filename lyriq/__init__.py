"""
Lyriq - A Python library for fetching and managing song lyrics.

This package provides an easy way to retrieve synchronized and plain lyrics
from the LRCLib API with built-in caching support.

Basic usage:
    >>> from lyriq import get_lyrics
    >>> lyrics = get_lyrics("Circles", "Post Malone")
    >>> print(lyrics.plain_lyrics)
"""

__version__ = "1.4.0"
__author__ = "TN3W"
__license__ = "Apache-2.0"
__email__ = "tn3w@protonmail.com"
__url__ = "https://github.com/tn3w/lyriq"

from .lyriq import (
    Lyrics,
    DatabaseDump,
    LyriqError,
    get_lyrics,
    get_lyrics_by_id,
    search_lyrics,
    to_plain_lyrics,
    request_challenge,
    verify_nonce,
    generate_publish_token,
    publish_lyrics,
    get_database_dumps,
    get_latest_database_dump,
    download_database_dump,
)

__all__ = [
    "Lyrics",
    "DatabaseDump",
    "LyriqError",
    "get_lyrics",
    "get_lyrics_by_id",
    "search_lyrics",
    "to_plain_lyrics",
    "request_challenge",
    "verify_nonce",
    "generate_publish_token",
    "publish_lyrics",
    "get_database_dumps",
    "get_latest_database_dump",
    "download_database_dump",
]
