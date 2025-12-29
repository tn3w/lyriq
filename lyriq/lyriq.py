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
from typing import Dict, List, Optional, Union, Tuple
from urllib.error import HTTPError
import hashlib
from datetime import datetime

from . import __version__, __url__

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "https://lrclib.net/api"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
LYRICS_CACHE_PATH = os.path.join(CACHE_DIR, "lyrics.json")
SEARCH_CACHE_PATH = os.path.join(CACHE_DIR, "search.json")
DB_DUMPS_CACHE_PATH = os.path.join(CACHE_DIR, "db_dumps.json")
DB_DUMPS_URL = "https://lrclib-db-dumps.bu3nnyut4y9jfkdg.workers.dev"


class _Cache:
    """
    Internal class for caching data to avoid redundant API calls.

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
                with open(self.cache_file_path, "r", encoding="utf-8") as file_stream:
                    self.cache = json.load(file_stream)
            except Exception as e:
                logger.error("Error loading cache: %s", e)
                self.cache = {}
        else:
            self.cache = {}

    def get(self, key: str) -> Optional[Union[Dict, List[str]]]:
        """
        Get a value from the cache.

        Args:
            key: The cache key to lookup.

        Returns:
            The cached value if found, None otherwise.
        """
        with self._lock:
            return self.cache.get(key)

    def set(self, key: str, value: Union[Dict, List[str]]) -> None:
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

    def update(self, data: Dict) -> None:
        """
        Add only new keys from data to the cache and write to disk asynchronously.
        Existing keys in the cache will not be updated.
        """
        with self._lock:
            for key, value in data.items():
                if key not in self.cache:
                    self.cache[key] = value
            cache_copy = self.cache.copy()

        threading.Thread(
            target=self._write_cache, args=(cache_copy,), daemon=False
        ).start()

    def _write_cache(self, cache_data: Union[Dict, List[str]]) -> None:
        """
        Write the cache to disk.

        Args:
            cache_data: The cache data to write.
        """
        try:
            with open(self.cache_file_path, "w", encoding="utf-8") as file_stream:
                json.dump(cache_data, file_stream)
            logger.debug("Cache written to %s", self.cache_file_path)
        except Exception as e:
            logger.error("Error writing cache: %s", e)


class _LyricsCache(_Cache):
    """
    Internal class for caching lyrics data to avoid redundant API calls.

    The cache is stored in a JSON file and accessed with thread-safety.
    """

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

    def get_bulk_by_lyrics_id(self, lyrics_ids: List[str]) -> List[Dict]:
        """
        Get a list of values from the cache by the id field.
        """
        with self._lock:
            lyrics = []
            for value in self.cache.values():
                if value.get("id") in lyrics_ids:
                    lyrics.append(value)
            return lyrics


lyrics_cache = _LyricsCache(LYRICS_CACHE_PATH)
search_cache = _Cache(SEARCH_CACHE_PATH)
db_dumps_cache = _Cache(DB_DUMPS_CACHE_PATH)


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
class DatabaseDump:
    """
    Database dump information from the LRCLib database dumps API.

    Contains metadata about available database dump files.
    """

    storage_class: str
    uploaded: datetime
    checksums: Dict
    http_etag: str
    etag: str
    size: int
    version: str
    key: str

    @classmethod
    def from_dict(cls, data: Dict) -> "DatabaseDump":
        """
        Create a DatabaseDump instance from a dictionary.

        Args:
            data: The raw database dump data dictionary.

        Returns:
            A new DatabaseDump instance.
        """
        return cls(
            storage_class=data.get("storageClass", ""),
            uploaded=datetime.fromisoformat(
                data.get("uploaded", "").replace("Z", "+00:00")
            ),
            checksums=data.get("checksums", {}),
            http_etag=data.get("httpEtag", ""),
            etag=data.get("etag", ""),
            size=data.get("size", 0),
            version=data.get("version", ""),
            key=data.get("key", ""),
        )

    @property
    def filename(self) -> str:
        """Get the filename from the key."""
        return self.key.split("/")[-1] if "/" in self.key else self.key

    @property
    def download_url(self) -> str:
        """Get the download URL for this dump."""
        return f"https://db-dumps.lrclib.net/{self.filename}"


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

    def to_plain_string(self, none_char: Optional[str] = None) -> Optional[str]:
        """
        Convert the Lyrics instance to a plain string.

        Args:
            none_char: Character to represent empty lines. If not specified, uses the current.

        Returns:
            Plain string or None.
        """
        if self.synced_lyrics:
            lyrics = self.lyrics
            if none_char is not None:
                lyrics = _process_lyrics(lyrics, none_char=none_char)

            result = ""
            for timestamp, line in lyrics.items():
                result += f"{timestamp} {line}\n"
            return result

        if self.plain_lyrics:
            return f"{self.plain_lyrics}\n"

    def to_plain_file(self, file_path: str, none_char: Optional[str] = None) -> None:
        """
        Write the lyrics of the Lyrics instance to a text file.

        Args:
            file_path: The path to the file to write.
            none_char: Character to represent empty lines. If not specified, uses the current.
        """
        plain_string = self.to_plain_string(none_char)
        if not plain_string:
            raise EmptyLyricsError("Cannot convert empty lyrics to plain text file")

        with open(file_path, "w", encoding="utf-8") as file_stream:
            file_stream.write(plain_string)

    def to_lrc_string(self) -> str:
        """
        Convert the Lyrics instance to a LRC string.

        Args:
            none_char: Character to represent empty lines. If not specified, uses the current.

        Returns:
            LRC string.
        """
        result = ""

        lrc_info = {
            "ti": self.track_name,
            "ar": self.artist_name,
            "al": self.album_name,
            "by": self.artist_name,
            "length": self.duration,
            "x-name": self.name,
            "x-id": self.id,
            "x-instrumental": self.instrumental,
        }
        for key, value in lrc_info.items():
            if not value:
                continue
            result += f"[{key}:{str(value)}]\n"
        result += "\n"

        if self.synced_lyrics:
            result += self.synced_lyrics
        elif self.plain_lyrics:
            result += self.plain_lyrics
        return result

    def to_lrc_file(self, file_path: str) -> None:
        """
        Write the Lyircs instance to a LRC file.

        Args:
            file_path: The path to the LRC file to write.
        """
        with open(file_path, "w", encoding="utf-8") as file_stream:
            file_stream.write(self.to_lrc_string())

    @classmethod
    def from_lrc_string(cls, lrc_string: str, none_char: str = "♪") -> "Lyrics":
        """
        Init a Lyrics instance from a LRC string.

        Args:
            lrc_string: The LRC string.
            none_char: Character to use for empty lines.

        Returns:
            A new Lyrics instance.
        """
        data = {
            "syncedLyrics": "",
            "plainLyrics": "",
            "id": "",
            "name": "",
            "trackName": "",
            "artistName": "",
            "albumName": "",
            "duration": 0,
            "instrumental": False,
        }

        lines = lrc_string.split("\n")
        metadata_lines = []
        lyrics_lines = []

        metadata_section = True
        for line in lines:
            line = line.strip()
            if not line:
                metadata_section = False
                continue

            if (
                metadata_section
                and line.startswith("[")
                and ":" in line
                and line.endswith("]")
            ):
                metadata_lines.append(line)
            else:
                lyrics_lines.append(line)

        for line in metadata_lines:
            tag = line[1 : line.find(":")]
            value = line[line.find(":") + 1 : line.find("]")]

            if tag == "ti":
                data["trackName"] = value
                data["name"] = value
            elif tag == "ar":
                data["artistName"] = value
            elif tag == "al":
                data["albumName"] = value
            elif tag == "length":
                try:
                    data["duration"] = float(value)
                except ValueError:
                    pass
            elif tag == "x-name":
                data["name"] = value
            elif tag == "x-id":
                data["id"] = value
            elif tag == "x-instrumental":
                data["instrumental"] = value.lower() == "true"

        has_sync_format = all(
            line.startswith("[") and "]" in line and line.index("]") > 1
            for line in lyrics_lines
            if line.strip()
        )

        if has_sync_format:
            synced_lyrics = "\n".join(lyrics_lines)
            data["syncedLyrics"] = synced_lyrics
            data["plainLyrics"] = to_plain_lyrics(synced_lyrics, none_char=none_char)
        else:
            data["plainLyrics"] = "\n".join(lyrics_lines)

        return cls.from_dict(data, none_char=none_char)

    @classmethod
    def from_lrc_file(cls, file_path: str, none_char: str = "♪") -> "Lyrics":
        """
        Read a Lyrics instance from a LRC file.

        Args:
            file_path: The path to the LRC file to read.
            none_char: Character to use for empty lines.

        Returns:
            A new Lyrics instance.
        """
        with open(file_path, "r", encoding="utf-8") as file_stream:
            content = file_stream.read()

        return cls.from_lrc_string(content, none_char=none_char)

    def to_json_file(self, file_path: str) -> None:
        """
        Write the Lyrics instance to a JSON file.

        Args:
            file_path: The path to the JSON file to write.
        """
        with open(file_path, "w", encoding="utf-8") as file_stream:
            json.dump(self.to_dict(), file_stream)

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
        with open(file_path, "r", encoding="utf-8") as file_stream:
            data = json.load(file_stream)

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


def to_plain_lyrics(lyrics: Union[Lyrics, dict, str], none_char: str = "♪") -> str:
    """
    Convert a Lyrics instance or synced lyrics dictionary or string to plain text lyrics.

    Args:
        lyrics: The Lyrics instance or dictionary or string to convert.
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
    elif isinstance(lyrics, str):
        synced_lyrics_str = lyrics

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


class EmptyLyricsError(LyriqError):
    """
    Exception raised when trying to convert empty lyrics to a string.
    """

    def __init__(self, message: str = "Cannot convert empty lyrics to string"):
        """
        Initialize a new EmptyLyricsError instance.

        Args:
            message: The error message.
        """
        super().__init__(400, "EmptyLyricsError", message)


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
        headers={"User-Agent": f"Lyriq v{__version__} ({__url__})"},
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
    cached_data = lyrics_cache.get_by_lyrics_id(lyrics_id)
    if cached_data:
        return Lyrics.from_dict(cached_data, none_char=none_char)

    try:
        url = f"{API_URL}/get/{lyrics_id}"
        data = _json_get(url)

        cache_key = f"{data['artistName'].lower()}:{data['trackName'].lower()}"
        lyrics_cache.set(cache_key, data)
        return Lyrics.from_dict(data, none_char=none_char)
    except LyriqError as e:
        logger.error("Error getting lyrics for %s: %s", lyrics_id, e)
        return None


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
    cached_data = lyrics_cache.get(cache_key)
    if cached_data and isinstance(cached_data, dict):
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

        lyrics_cache.set(cache_key, data)
        return Lyrics.from_dict(data, none_char=none_char)
    except LyriqError as e:
        logger.error("Error getting lyrics for %s by %s: %s", song_name, artist_name, e)
        return None


def search_lyrics(
    q: Optional[str] = None,
    song_name: Optional[str] = None,
    artist_name: Optional[str] = None,
    album_name: Optional[str] = None,
    none_char: str = "♪",
) -> Optional[List[Lyrics]]:
    """
    Search for lyrics by query.

    Args:
        q: The query to search for.
        song_name: Optional song name for better matching.
        artist_name: Optional artist name for better matching.
        album_name: Optional album name for better matching.
        none_char: Character to use for empty lines.

    Returns:
        A list of Lyrics objects if found, None otherwise.
    """
    params = {}
    if q:
        cache_key = f"{_normalize_name(q)}"
        params["q"] = _normalize_name(q)
    elif song_name:
        params["track_name"] = _normalize_name(song_name)
        if artist_name:
            params["artist_name"] = _normalize_name(artist_name)
            cache_key = f"{_normalize_name(artist_name)}:{_normalize_name(song_name)}"
        else:
            cache_key = _normalize_name(song_name)

        if album_name:
            params["album_name"] = _normalize_name(album_name)
    else:
        raise ValueError("Either q or song_name must be provided")

    cached_data = search_cache.get(cache_key)
    if cached_data and isinstance(cached_data, list):
        return [
            Lyrics.from_dict(lyrics, none_char=none_char)
            for lyrics in lyrics_cache.get_bulk_by_lyrics_id(cached_data)
        ]

    url = f"{API_URL}/search?{urllib.parse.urlencode(params)}"

    try:
        data = _json_get(url)
        cache_data = {}

        for lyrics in data:
            lyrics_cache_key = (
                f"{_normalize_name(lyrics['artistName'])}:"
                f"{_normalize_name(lyrics['trackName'])}"
            )
            if lyrics_cache_key not in cache_data:
                cache_data[lyrics_cache_key] = lyrics
                lyrics_cache.set(lyrics_cache_key, lyrics)

        lyrics_cache.update(cache_data)

        search_cache.set(
            cache_key,
            [lyrics.get("id") for lyrics in cache_data.values() if lyrics.get("id")],
        )

        return [
            Lyrics.from_dict(lyrics, none_char=none_char)
            for lyrics in cache_data.values()
        ]
    except LyriqError as e:
        logger.error("Error searching for lyrics: %s", e)
        return None


def request_challenge() -> Tuple[str, str]:
    """
    Request a challenge from the API for generating a publish token.

    Returns:
        A tuple containing (prefix, target) for the proof-of-work challenge.

    Raises:
        LyriqError: If the API returns an error.
    """
    url = f"{API_URL}/request-challenge"
    headers = {
        "User-Agent": f"Lyriq v{__version__} ({__url__})",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(url, method="POST", headers=headers, data=b"")
    try:
        with urllib.request.urlopen(req) as response:
            data = response.read().decode("utf-8")
            challenge = json.loads(data)
            return challenge["prefix"], challenge["target"]
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


def verify_nonce(result_bytes: bytes, target_bytes: bytes) -> bool:
    """
    Verify if a nonce satisfies the target requirement.

    Args:
        result_bytes: The hashed result as bytes.
        target_bytes: The target as bytes.

    Returns:
        True if the nonce satisfies the target, False otherwise.
    """
    if len(result_bytes) != len(target_bytes):
        return False

    for r_byte, t_byte in zip(result_bytes, target_bytes):
        if r_byte > t_byte:
            return False
        if r_byte < t_byte:
            break

    return True


def generate_publish_token(prefix: str, target: str) -> str:
    """
    Generate a valid publish token by solving a proof-of-work challenge.
    Args:
        prefix: The prefix to use for the challenge.
        target: The target to use for the challenge. Must be a hex string.

    Returns:
        A valid publish token in the format {prefix}:{nonce}.

    Raises:
        LyriqError: If there is an error requesting the challenge.
    """
    target_bytes = bytes.fromhex(target)

    nonce = 0
    while True:
        input_string = f"{prefix}{nonce}"
        hashed = hashlib.sha256(input_string.encode()).digest()

        if verify_nonce(hashed, target_bytes):
            break

        nonce += 1

    return f"{prefix}:{nonce}"


def publish_lyrics(
    track_name: str,
    artist_name: str,
    album_name: str,
    duration: int,
    plain_lyrics: str = "",
    synced_lyrics: str = "",
) -> bool:
    """
    Publish lyrics to the API.

    Args:
        track_name: Name of the track.
        artist_name: Name of the artist.
        album_name: Name of the album.
        duration: Duration of the track in seconds.
        plain_lyrics: Plain text lyrics (optional).
        synced_lyrics: Synchronized lyrics (optional).

    Returns:
        True if the publish was successful, False otherwise.

    Raises:
        LyriqError: If there is an error publishing the lyrics.
    """
    url = f"{API_URL}/publish"

    prefix, target = request_challenge()
    publish_token = generate_publish_token(prefix, target)

    data = {
        "trackName": track_name,
        "artistName": artist_name,
        "albumName": album_name,
        "duration": duration,
        "plainLyrics": plain_lyrics,
        "syncedLyrics": synced_lyrics,
    }

    headers = {
        "User-Agent": f"Lyriq v{__version__} ({__url__})",
        "Content-Type": "application/json",
        "X-Publish-Token": publish_token,
    }

    try:
        data_bytes = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url, method="POST", headers=headers, data=data_bytes
        )

        with urllib.request.urlopen(req) as response:
            if response.status == 201:
                logger.info(
                    "Successfully published lyrics for %s by %s",
                    track_name,
                    artist_name,
                )
                return True
            else:
                logger.error(
                    "Failed to publish lyrics for %s by %s: %s",
                    track_name,
                    artist_name,
                    response.status,
                )
                return False
    except HTTPError as e:
        error_data = e.read().decode("utf-8")
        try:
            error_json = json.loads(error_data)
            logger.error(
                "Error publishing lyrics for %s by %s: %s",
                track_name,
                artist_name,
                error_json.get("message", "Unknown error"),
            )
            raise LyriqError(
                error_json.get("statusCode", e.code),
                error_json.get("name", "Unknown error"),
                error_json.get("message", "Unknown error"),
            ) from e
        except json.JSONDecodeError as exc:
            raise exc from e


def get_database_dumps() -> Optional[List[DatabaseDump]]:
    """
    Get the list of available database dumps from the LRCLib database dumps API.

    This function caches the results to avoid redundant API calls.

    Returns:
        A list of DatabaseDump objects if successful, None otherwise.

    Raises:
        LyriqError: If there is an error fetching the database dumps.
    """
    cache_key = "database_dumps"
    cached_data = db_dumps_cache.get(cache_key)

    if cached_data and isinstance(cached_data, dict):
        cache_time = cached_data.get("timestamp", 0)
        current_time = datetime.now().timestamp()
        if current_time - cache_time < 3600:
            objects = cached_data.get("objects", [])
            return [DatabaseDump.from_dict(obj) for obj in objects]

    try:
        data = _json_get(DB_DUMPS_URL)

        cache_data = {
            "timestamp": datetime.now().timestamp(),
            "objects": data.get("objects", []),
            "truncated": data.get("truncated", False),
            "delimitedPrefixes": data.get("delimitedPrefixes", []),
        }
        db_dumps_cache.set(cache_key, cache_data)

        objects = data.get("objects", [])
        return [DatabaseDump.from_dict(obj) for obj in objects]

    except LyriqError as e:
        logger.error("Error getting database dumps: %s", e)
        return None
    except Exception as e:
        logger.error("Error getting database dumps: %s", e)
        return None


def get_latest_database_dump() -> Optional[DatabaseDump]:
    """
    Get the latest database dump from the LRCLib database dumps API.

    Returns:
        The latest DatabaseDump object if found, None otherwise.
    """
    dumps = get_database_dumps()
    if not dumps:
        return None

    dumps.sort(key=lambda x: x.uploaded, reverse=True)
    return dumps[0]


def download_database_dump(
    dump: DatabaseDump,
    download_path: Optional[str] = None,
    progress_callback: Optional[callable] = None,
) -> Optional[str]:
    """
    Download a database dump file.

    Args:
        dump: The DatabaseDump object to download.
        download_path: Optional path to save the file. If not provided, saves to cache directory.
        progress_callback: Optional callback function to track download progress.
                          Called with (bytes_downloaded, total_bytes).

    Returns:
        The path to the downloaded file if successful, None otherwise.

    Raises:
        LyriqError: If there is an error downloading the file.
    """
    if not download_path:
        download_path = os.path.join(CACHE_DIR, dump.filename)

    os.makedirs(os.path.dirname(download_path), exist_ok=True)

    try:
        req = urllib.request.Request(
            dump.download_url,
            headers={"User-Agent": f"Lyriq v{__version__} ({__url__})"},
        )

        with urllib.request.urlopen(req) as response:
            total_size = int(response.headers.get("Content-Length") or 0)
            downloaded = 0

            with open(download_path, "wb") as f:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break

                    f.write(chunk)
                    downloaded += len(chunk)

                    if progress_callback:
                        progress_callback(downloaded, total_size)

        logger.info("Successfully downloaded database dump to %s", download_path)
        return download_path

    except HTTPError as e:
        error_data = e.read().decode("utf-8")
        try:
            error_json = json.loads(error_data)
            raise LyriqError(
                error_json.get("statusCode", e.code),
                error_json.get("name", "Unknown error"),
                error_json.get("message", "Unknown error"),
            ) from e
        except json.JSONDecodeError:
            logger.error("Error downloading database dump: HTTP %s", e.code)
            return None
    except Exception as e:
        logger.error("Error downloading database dump: %s", e)
        return None
