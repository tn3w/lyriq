"""
Lyriq: A simple library for fetching and managing song lyrics.

This module provides functionality to retrieve synchronized and plain lyrics
from the LRCLib API with caching support.
"""

import json
import logging
import os
import threading
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Dict, Optional, Union
from urllib.error import HTTPError

from . import __version__

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "https://lrclib.net/api"
CACHE_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache.json")


class _LyricsCache:
    """
    Internal class for caching lyrics data to avoid redundant API calls.

    The cache is stored in a JSON file and accessed with thread-safety.
    """

    def __init__(self, cache_file_path: str):
        """
        Initialize the lyrics cache.

        Args:
            cache_file_path: Path to the JSON file used for caching.
        """
        self.cache_file_path = cache_file_path
        self._lock = threading.Lock()
        self._load_cache()

    def _load_cache(self) -> None:
        """Load the cache from the disk if it exists."""
        if os.path.exists(self.cache_file_path):
            try:
                with open(self.cache_file_path, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            except Exception as e:
                logger.error("Error loading cache: %s", e)
                self.cache = {}
        else:
            self.cache = {}

    def get(self, key: str) -> Optional[Dict]:
        """
        Get a value from the cache.

        Args:
            key: The cache key to lookup.

        Returns:
            The cached value if found, None otherwise.
        """
        with self._lock:
            return self.cache.get(key)

    def get_by_lyrics_id(self, lyrics_id: str) -> Optional[Dict]:
        """
        Get a value from the cache by the id field.

        Args:
            lyrics_id: The ID to lookup.

        Returns:
            The cached value if found, None otherwise.
        """
        with self._lock:
            for value in self.cache.values():
                if value.get("id") == lyrics_id:
                    return value
            return None

    def set(self, key: str, value: Dict) -> None:
        """
        Set a value in the cache and write to disk asynchronously.

        Args:
            key: The cache key.
            value: The value to store.
        """
        with self._lock:
            self.cache[key] = value
            cache_copy = self.cache.copy()

        threading.Thread(
            target=self._write_cache, args=(cache_copy,), daemon=False
        ).start()

    def _write_cache(self, cache_data: Dict) -> None:
        """
        Write the cache to disk.

        Args:
            cache_data: The cache data to write.
        """
        try:
            with open(self.cache_file_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f)
            logger.debug("Cache written to %s", self.cache_file_path)
        except Exception as e:
            logger.error("Error writing cache: %s", e)


cache = _LyricsCache(CACHE_FILE_PATH)


def _process_lyrics(data: Dict, none_char: str = "♪") -> Dict[str, str]:
    """
    Process lyrics data combining timestamp information and handling empty lines.

    Args:
        data: The raw lyrics data from the API.
        none_char: Character to use for empty lines.

    Returns:
        A dictionary mapping timestamps to lyrics lines.
    """
    result = {}

    if not data.get("syncedLyrics"):
        if data.get("plainLyrics"):
            plain_lines = data["plainLyrics"].split("\n")
            for idx, line in enumerate(plain_lines):
                trimmed = line.strip()
                idx_str = f"0{idx}" if idx < 10 else str(idx)
                result[f"{idx_str}.00"] = line if trimmed else none_char
        return result

    synced_lines = data["syncedLyrics"].split("\n")
    empty_sections = []

    for line in synced_lines:
        if not line.strip():
            continue

        timestamp_end = line.find("]")
        if timestamp_end == -1:
            continue

        timestamp = line[1:timestamp_end]
        content = line[timestamp_end + 1 :].strip()

        if not content:
            empty_sections.append(timestamp)
            result[timestamp] = none_char
        else:
            result[timestamp] = content

    if data.get("plainLyrics"):
        plain_sections = data["plainLyrics"].split("\n\n")

        if len(plain_sections) > 1 and empty_sections:
            for timestamp in empty_sections:
                result[timestamp] = none_char

    return result


@dataclass
class Lyrics:
    """
    Lyrics class containing lyrics data and metadata.

    This class stores both synchronized and plain lyrics along with
    track information like artist, album, and duration.
    """

    lyrics: Dict[str, str]
    synced_lyrics: str
    plain_lyrics: str
    id: str
    name: str
    track_name: str
    artist_name: str
    album_name: str
    duration: int
    instrumental: bool

    @classmethod
    def from_dict(cls, data: Dict, none_char: str = "♪") -> "Lyrics":
        """
        Create a Lyrics instance from a dictionary.

        Args:
            data: The raw lyrics data dictionary.
            none_char: Character to use for empty lines.

        Returns:
            A new Lyrics instance.
        """
        return cls(
            lyrics=_process_lyrics(data, none_char=none_char),
            synced_lyrics=data.get("syncedLyrics", ""),
            plain_lyrics=data.get("plainLyrics", ""),
            id=data.get("id", ""),
            name=data.get("name", ""),
            track_name=data.get("trackName", ""),
            artist_name=data.get("artistName", ""),
            album_name=data.get("albumName", ""),
            duration=data.get("duration", 0),
            instrumental=data.get("instrumental", False),
        )

    def to_dict(self) -> Dict:
        """
        Convert the Lyrics instance to a dictionary.

        Returns:
            Dictionary representation of the lyrics.
        """
        return {
            "lyrics": self.lyrics,
            "synced_lyrics": self.synced_lyrics,
            "plain_lyrics": self.plain_lyrics,
            "id": self.id,
            "name": self.name,
            "track_name": self.track_name,
            "artist_name": self.artist_name,
            "album_name": self.album_name,
            "duration": self.duration,
            "instrumental": self.instrumental,
        }

    def __bool__(self) -> bool:
        """
        Check if the Lyrics instance has lyrics.

        Returns:
            True if lyrics exist, False otherwise.
        """
        return bool(self.lyrics)

    def to_plain_file(self, file_path: str) -> None:
        """
        Write the Lyrics instance to a plain text file.

        Args:
            file_path: The path to the file to write.
        """
        with open(file_path, "a", encoding="utf-8") as f:
            if self.plain_lyrics and not self.synced_lyrics:
                f.write(f"{self.plain_lyrics}\n")
                return

            for timestamp, line in self.lyrics.items():
                f.write(f"{timestamp} {line}\n")

    def to_json_file(self, file_path: str) -> None:
        """
        Write the Lyrics instance to a JSON file.

        Args:
            file_path: The path to the JSON file to write.
        """
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f)

    @classmethod
    def from_json_file(cls, file_path: str, none_char: str = "♪") -> "Lyrics":
        """
        Read a Lyrics instance from a JSON file.

        Args:
            file_path: The path to the JSON file to read.
            none_char: Character to use for empty lines.

        Returns:
            A new Lyrics instance.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

            if "synced_lyrics" in data:
                api_data = {
                    "syncedLyrics": data.get("synced_lyrics", ""),
                    "plainLyrics": data.get("plain_lyrics", ""),
                    "id": data.get("id", ""),
                    "name": data.get("name", ""),
                    "trackName": data.get("track_name", ""),
                    "artistName": data.get("artist_name", ""),
                    "albumName": data.get("album_name", ""),
                    "duration": data.get("duration", 0),
                    "instrumental": data.get("instrumental", False),
                }
                return cls.from_dict(api_data, none_char=none_char)

            return cls.from_dict(data, none_char=none_char)


def to_plain_lyrics(lyrics: Union[Lyrics, dict], none_char: str = "♪") -> str:
    """
    Convert a Lyrics instance or synced lyrics dictionary to plain text lyrics.

    Args:
        lyrics: The Lyrics instance or dictionary to convert.
        none_char: Character to use for empty lines.

    Returns:
        Plain text lyrics.
    """
    synced_lyrics: Dict[str, str] = {}
    synced_lyrics_str = ""

    if isinstance(lyrics, Lyrics):
        if lyrics.plain_lyrics:
            return lyrics.plain_lyrics
        if lyrics.synced_lyrics:
            synced_lyrics_str = lyrics.synced_lyrics
    elif isinstance(lyrics, dict):
        if lyrics.get("plainLyrics"):
            return lyrics.get("plainLyrics") or ""
        if lyrics.get("syncedLyrics"):
            synced_lyrics_str = lyrics.get("syncedLyrics")
        else:
            synced_lyrics = lyrics

    result = ""
    if synced_lyrics:
        for line in synced_lyrics.values():
            if line.strip():
                result += f"{line}\n"
            else:
                result += f"{none_char}\n"

    if synced_lyrics_str:
        for line in synced_lyrics_str.split("\n"):
            if not line.strip():
                continue

            timestamp_end = line.find("]")
            if timestamp_end == -1:
                continue
            content = line[timestamp_end + 1 :].strip()

            if not content:
                result += f"{none_char}\n"
            else:
                result += f"{content}\n"

    return result


def _normalize_name(name: str) -> str:
    """
    Normalize a name for use in the API.

    Args:
        name: The name to normalize.

    Returns:
        Normalized name.
    """
    return name.lower().replace("·", "-")


class LyriqError(Exception):
    """
    Exception raised for errors in the Lyriq library.
    """

    def __init__(self, code: int, name: str, message: str):
        """
        Initialize a new LyriqError instance.

        Args:
            code: The error code.
            name: The error name.
            message: The error message.
        """
        self.code = code
        self.name = name
        self.message = message
        super().__init__(f"{code} {name}: {message}")


def _json_get(url: str) -> Dict:
    """
    Make a GET request to the given URL and return the JSON response.

    Args:
        url: The URL to request.

    Returns:
        Parsed JSON response as dictionary.

    Raises:
        LyriqError: If the API returns an error.
        Exception: For other errors.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": f"Lyriq v{__version__} (https://github.com/TN3W/lyriq)"},
    )
    try:
        with urllib.request.urlopen(req) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)
    except HTTPError as e:
        error_data = e.read().decode("utf-8")
        try:
            error_json = json.loads(error_data)
            raise LyriqError(
                error_json.get("statusCode", e.code),
                error_json.get("name", "Unknown error"),
                error_json.get("message", "Unknown error"),
            ) from e
        except json.JSONDecodeError as exc:
            raise exc from e


def get_lyrics_by_id(lyrics_id: str, none_char: str = "♪") -> Optional[Lyrics]:
    """
    Get lyrics for a song by ID.

    Args:
        lyrics_id: The ID to lookup.
        none_char: Character to use for empty lines.

    Returns:
        A Lyrics object if found, None otherwise.

    Raises:
        Exception: If there is an error fetching the lyrics.
    """
    cached_data = cache.get_by_lyrics_id(lyrics_id)
    if cached_data:
        return Lyrics.from_dict(cached_data, none_char=none_char)

    try:
        url = f"{API_URL}/get/{lyrics_id}"
        data = _json_get(url)

        cache_key = f"{data['artistName'].lower()}:{data['trackName'].lower()}"
        cache.set(cache_key, data)
        return Lyrics.from_dict(data, none_char=none_char)
    except LyriqError as e:
        logger.error("Error getting lyrics for %s: %s", lyrics_id, e)
        return None
    except Exception as e:
        logger.error("Error getting lyrics for %s: %s", lyrics_id, e)
        raise e


def get_lyrics(
    song_name: str,
    artist_name: str,
    album_name: Optional[str] = None,
    duration: Optional[int] = None,
    none_char: str = "♪",
) -> Optional[Lyrics]:
    """
    Get lyrics for a song by artist.

    Retrieves lyrics from either the local cache or the remote API.

    Args:
        song_name: Name of the song.
        artist_name: Name of the artist.
        album_name: Optional album name for better matching.
        duration: Optional duration of the song.
        none_char: Character to use for empty lines.

    Returns:
        A Lyrics object if found, None otherwise.

    Raises:
        Exception: If there is an error fetching the lyrics.
    """
    cache_key = f"{_normalize_name(artist_name)}:{_normalize_name(song_name)}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return Lyrics.from_dict(cached_data, none_char=none_char)

    params = {
        "track_name": _normalize_name(song_name),
        "artist_name": _normalize_name(artist_name),
    }
    if album_name:
        params["album_name"] = _normalize_name(album_name)
    if duration:
        params["duration"] = str(duration)

    url = f"{API_URL}/get?{urllib.parse.urlencode(params)}"

    try:
        data = _json_get(url)

        cache.set(cache_key, data)
        return Lyrics.from_dict(data, none_char=none_char)
    except LyriqError as e:
        logger.error("Error getting lyrics for %s by %s: %s", song_name, artist_name, e)
        return None
    except Exception as e:
        logger.error("Error getting lyrics for %s by %s: %s", song_name, artist_name, e)
        raise e
