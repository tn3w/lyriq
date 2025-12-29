"""
Lyriq: A library for fetching and managing song lyrics.

Provides functionality to retrieve synchronized and plain lyrics from the LRCLib API
with caching support.
"""

import hashlib
import json
import logging
import os
import threading
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple, Union
from urllib.error import HTTPError

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


class LyriqError(Exception):
    """Exception raised for errors in the Lyriq library."""

    def __init__(self, code: int, name: str, message: str):
        self.code = code
        self.name = name
        self.message = message
        super().__init__(f"{code} {name}: {message}")


class EmptyLyricsError(LyriqError):
    """Exception raised when trying to convert empty lyrics to a string."""

    def __init__(self, message: str = "Cannot convert empty lyrics to string"):
        super().__init__(400, "EmptyLyricsError", message)


class _Cache:
    """Thread-safe cache stored in a JSON file."""

    def __init__(self, cache_file_path: str):
        self.cache_file_path = cache_file_path
        self._lock = threading.Lock()
        self._load_cache()

    def _load_cache(self) -> None:
        """Load the cache from disk if it exists."""
        if not os.path.exists(self.cache_file_path):
            self.cache = {}
            return
        try:
            with open(self.cache_file_path, "r", encoding="utf-8") as file:
                self.cache = json.load(file)
        except Exception as error:
            logger.error("Error loading cache: %s", error)
            self.cache = {}

    def get(self, key: str) -> Optional[Union[Dict, List[str]]]:
        """Get a value from the cache."""
        with self._lock:
            return self.cache.get(key)

    def set(self, key: str, value: Union[Dict, List[str]]) -> None:
        """Set a value in the cache and write to disk asynchronously."""
        with self._lock:
            self.cache[key] = value
            cache_copy = self.cache.copy()
        threading.Thread(
            target=self._write_cache, args=(cache_copy,), daemon=False
        ).start()

    def update(self, data: Dict) -> None:
        """Add only new keys from data to the cache."""
        with self._lock:
            for key, value in data.items():
                if key not in self.cache:
                    self.cache[key] = value
            cache_copy = self.cache.copy()
        threading.Thread(
            target=self._write_cache, args=(cache_copy,), daemon=False
        ).start()

    def _write_cache(self, cache_data: Union[Dict, List[str]]) -> None:
        """Write the cache to disk."""
        try:
            with open(self.cache_file_path, "w", encoding="utf-8") as file:
                json.dump(cache_data, file)
        except Exception as error:
            logger.error("Error writing cache: %s", error)


class _LyricsCache(_Cache):
    """Cache specifically for lyrics data with ID-based lookups."""

    def get_by_lyrics_id(self, lyrics_id: str) -> Optional[Dict]:
        """Get a value from the cache by the id field."""
        with self._lock:
            for value in self.cache.values():
                if value.get("id") == lyrics_id:
                    return value
            return None

    def get_bulk_by_lyrics_id(self, lyrics_ids: List[str]) -> List[Dict]:
        """Get a list of values from the cache by the id field."""
        with self._lock:
            return [v for v in self.cache.values() if v.get("id") in lyrics_ids]


lyrics_cache = _LyricsCache(LYRICS_CACHE_PATH)
search_cache = _Cache(SEARCH_CACHE_PATH)
db_dumps_cache = _Cache(DB_DUMPS_CACHE_PATH)


def _normalize_name(name: str) -> str:
    """Normalize a name for use in the API."""
    return name.lower().replace("·", "-")


def _json_get(url: str) -> Dict:
    """Make a GET request and return the JSON response."""
    req = urllib.request.Request(
        url, headers={"User-Agent": f"Lyriq v{__version__} ({__url__})"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        error_data = error.read().decode("utf-8")
        try:
            error_json = json.loads(error_data)
            raise LyriqError(
                error_json.get("statusCode", error.code),
                error_json.get("name", "Unknown error"),
                error_json.get("message", "Unknown error"),
            ) from error
        except json.JSONDecodeError as exc:
            raise exc from error


def _process_lyrics(data: Dict, none_char: str = "♪") -> Dict[str, str]:
    """Process lyrics data combining timestamp information and handling empty lines."""
    result = {}

    if not data.get("syncedLyrics"):
        if data.get("plainLyrics"):
            for idx, line in enumerate(data["plainLyrics"].split("\n")):
                idx_str = f"0{idx}" if idx < 10 else str(idx)
                result[f"{idx_str}.00"] = line.strip() if line.strip() else none_char
        return result

    for line in data["syncedLyrics"].split("\n"):
        if not line.strip():
            continue
        timestamp_end = line.find("]")
        if timestamp_end == -1:
            continue
        timestamp = line[1:timestamp_end]
        content = line[timestamp_end + 1 :].strip()
        result[timestamp] = content if content else none_char

    return result


def to_plain_lyrics(lyrics: Union["Lyrics", dict, str], none_char: str = "♪") -> str:
    """Convert lyrics to plain text."""
    if isinstance(lyrics, Lyrics):
        if lyrics.plain_lyrics:
            return lyrics.plain_lyrics
        synced_str = lyrics.synced_lyrics
    elif isinstance(lyrics, dict):
        if lyrics.get("plainLyrics"):
            return lyrics.get("plainLyrics") or ""
        synced_str = lyrics.get("syncedLyrics", "")
        if not synced_str:
            return "\n".join(
                line if line.strip() else none_char for line in lyrics.values()
            )
    else:
        synced_str = lyrics

    result = ""
    for line in synced_str.split("\n"):
        if not line.strip():
            continue
        timestamp_end = line.find("]")
        if timestamp_end == -1:
            continue
        content = line[timestamp_end + 1 :].strip()
        result += f"{content if content else none_char}\n"
    return result


@dataclass
class DatabaseDump:
    """Database dump information from the LRCLib database dumps API."""

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
        """Create a DatabaseDump instance from a dictionary."""
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
    """Lyrics class containing lyrics data and metadata."""

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
        """Create a Lyrics instance from a dictionary."""
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
        """Convert the Lyrics instance to a dictionary."""
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
        """Check if the Lyrics instance has lyrics."""
        return bool(self.lyrics)

    def to_plain_string(self, none_char: Optional[str] = None) -> Optional[str]:
        """Convert the Lyrics instance to a plain string."""
        if self.synced_lyrics:
            lyrics = self.lyrics
            if none_char is not None:
                lyrics = _process_lyrics(
                    {"syncedLyrics": self.synced_lyrics}, none_char
                )
            return "".join(f"{ts} {line}\n" for ts, line in lyrics.items())
        if self.plain_lyrics:
            return f"{self.plain_lyrics}\n"
        return None

    def to_plain_file(self, file_path: str, none_char: Optional[str] = None) -> None:
        """Write the lyrics to a text file."""
        plain_string = self.to_plain_string(none_char)
        if not plain_string:
            raise EmptyLyricsError("Cannot convert empty lyrics to plain text file")
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(plain_string)

    def to_lrc_string(self) -> str:
        """Convert the Lyrics instance to a LRC string."""
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
        result = "".join(
            f"[{key}:{value}]\n" for key, value in lrc_info.items() if value
        )
        result += "\n"
        result += self.synced_lyrics if self.synced_lyrics else self.plain_lyrics
        return result

    def to_lrc_file(self, file_path: str) -> None:
        """Write the Lyrics instance to a LRC file."""
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(self.to_lrc_string())

    def to_json_file(self, file_path: str) -> None:
        """Write the Lyrics instance to a JSON file."""
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file)

    @classmethod
    def from_lrc_string(cls, lrc_string: str, none_char: str = "♪") -> "Lyrics":
        """Init a Lyrics instance from a LRC string."""
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

        metadata_lines = []
        lyrics_lines = []
        metadata_section = True

        for line in lrc_string.split("\n"):
            line = line.strip()
            if not line:
                metadata_section = False
                continue
            is_metadata = (
                metadata_section
                and line.startswith("[")
                and ":" in line
                and line.endswith("]")
            )
            if is_metadata:
                metadata_lines.append(line)
            else:
                lyrics_lines.append(line)

        data = _parse_lrc_metadata(data, metadata_lines)
        data = _parse_lrc_lyrics(data, lyrics_lines, none_char)
        return cls.from_dict(data, none_char=none_char)

    @classmethod
    def from_lrc_file(cls, file_path: str, none_char: str = "♪") -> "Lyrics":
        """Read a Lyrics instance from a LRC file."""
        with open(file_path, "r", encoding="utf-8") as file:
            return cls.from_lrc_string(file.read(), none_char=none_char)

    @classmethod
    def from_json_file(cls, file_path: str, none_char: str = "♪") -> "Lyrics":
        """Read a Lyrics instance from a JSON file."""
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

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


def _parse_lrc_metadata(data: Dict, metadata_lines: List[str]) -> Dict:
    """Parse LRC metadata lines into data dictionary."""
    tag_map = {
        "ti": "trackName",
        "ar": "artistName",
        "al": "albumName",
        "x-name": "name",
        "x-id": "id",
    }

    for line in metadata_lines:
        tag = line[1 : line.find(":")]
        value = line[line.find(":") + 1 : line.find("]")]

        if tag in tag_map:
            data[tag_map[tag]] = value
            if tag == "ti":
                data["name"] = value
        elif tag == "length":
            try:
                data["duration"] = float(value)
            except ValueError:
                pass
        elif tag == "x-instrumental":
            data["instrumental"] = value.lower() == "true"

    return data


def _parse_lrc_lyrics(data: Dict, lyrics_lines: List[str], none_char: str) -> Dict:
    """Parse LRC lyrics lines into data dictionary."""
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

    return data


def get_lyrics_by_id(lyrics_id: str, none_char: str = "♪") -> Optional[Lyrics]:
    """Get lyrics for a song by ID."""
    cached_data = lyrics_cache.get_by_lyrics_id(lyrics_id)
    if cached_data:
        return Lyrics.from_dict(cached_data, none_char=none_char)

    try:
        url = f"{API_URL}/get/{lyrics_id}"
        data = _json_get(url)
        cache_key = f"{data['artistName'].lower()}:{data['trackName'].lower()}"
        lyrics_cache.set(cache_key, data)
        return Lyrics.from_dict(data, none_char=none_char)
    except LyriqError as error:
        logger.error("Error getting lyrics for %s: %s", lyrics_id, error)
        return None


def get_lyrics(
    song_name: str,
    artist_name: str,
    album_name: Optional[str] = None,
    duration: Optional[int] = None,
    none_char: str = "♪",
) -> Optional[Lyrics]:
    """Get lyrics for a song by artist."""
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
    except LyriqError as error:
        logger.error(
            "Error getting lyrics for %s by %s: %s", song_name, artist_name, error
        )
        return None


def search_lyrics(
    q: Optional[str] = None,
    song_name: Optional[str] = None,
    artist_name: Optional[str] = None,
    album_name: Optional[str] = None,
    none_char: str = "♪",
) -> Optional[List[Lyrics]]:
    """Search for lyrics by query."""
    params = {}
    cache_key = _build_search_cache_key(q, song_name, artist_name, params)

    if album_name:
        params["album_name"] = _normalize_name(album_name)

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
            [l.get("id") for l in cache_data.values() if l.get("id")],
        )

        return [Lyrics.from_dict(l, none_char=none_char) for l in cache_data.values()]
    except LyriqError as error:
        logger.error("Error searching for lyrics: %s", error)
        return None


def _build_search_cache_key(
    q: Optional[str],
    song_name: Optional[str],
    artist_name: Optional[str],
    params: Dict,
) -> str:
    """Build cache key and populate params for search."""
    if q:
        params["q"] = _normalize_name(q)
        return _normalize_name(q)

    if not song_name:
        raise ValueError("Either q or song_name must be provided")

    params["track_name"] = _normalize_name(song_name)
    if artist_name:
        params["artist_name"] = _normalize_name(artist_name)
        return f"{_normalize_name(artist_name)}:{_normalize_name(song_name)}"
    return _normalize_name(song_name)


def request_challenge() -> Tuple[str, str]:
    """Request a challenge from the API for generating a publish token."""
    url = f"{API_URL}/request-challenge"
    headers = {
        "User-Agent": f"Lyriq v{__version__} ({__url__})",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(url, method="POST", headers=headers, data=b"")
    try:
        with urllib.request.urlopen(req) as response:
            challenge = json.loads(response.read().decode("utf-8"))
            return challenge["prefix"], challenge["target"]
    except HTTPError as error:
        error_data = error.read().decode("utf-8")
        try:
            error_json = json.loads(error_data)
            raise LyriqError(
                error_json.get("statusCode", error.code),
                error_json.get("name", "Unknown error"),
                error_json.get("message", "Unknown error"),
            ) from error
        except json.JSONDecodeError as exc:
            raise exc from error


def verify_nonce(result_bytes: bytes, target_bytes: bytes) -> bool:
    """Verify if a nonce satisfies the target requirement."""
    if len(result_bytes) != len(target_bytes):
        return False
    for r_byte, t_byte in zip(result_bytes, target_bytes):
        if r_byte > t_byte:
            return False
        if r_byte < t_byte:
            break
    return True


def generate_publish_token(prefix: str, target: str) -> str:
    """Generate a valid publish token by solving a proof-of-work challenge."""
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
    """Publish lyrics to the API."""
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
                logger.info("Published lyrics for %s by %s", track_name, artist_name)
                return True
            logger.error("Failed to publish lyrics: %s", response.status)
            return False
    except HTTPError as error:
        error_data = error.read().decode("utf-8")
        try:
            error_json = json.loads(error_data)
            logger.error("Error publishing lyrics: %s", error_json.get("message"))
            raise LyriqError(
                error_json.get("statusCode", error.code),
                error_json.get("name", "Unknown error"),
                error_json.get("message", "Unknown error"),
            ) from error
        except json.JSONDecodeError as exc:
            raise exc from error


def get_database_dumps() -> Optional[List[DatabaseDump]]:
    """Get the list of available database dumps from the LRCLib database dumps API."""
    cache_key = "database_dumps"
    cached_data = db_dumps_cache.get(cache_key)

    if cached_data and isinstance(cached_data, dict):
        cache_time = cached_data.get("timestamp", 0)
        if datetime.now().timestamp() - cache_time < 3600:
            return [
                DatabaseDump.from_dict(obj) for obj in cached_data.get("objects", [])
            ]

    try:
        data = _json_get(DB_DUMPS_URL)
        cache_data = {
            "timestamp": datetime.now().timestamp(),
            "objects": data.get("objects", []),
            "truncated": data.get("truncated", False),
            "delimitedPrefixes": data.get("delimitedPrefixes", []),
        }
        db_dumps_cache.set(cache_key, cache_data)
        return [DatabaseDump.from_dict(obj) for obj in data.get("objects", [])]
    except (LyriqError, Exception) as error:
        logger.error("Error getting database dumps: %s", error)
        return None


def get_latest_database_dump() -> Optional[DatabaseDump]:
    """Get the latest database dump from the LRCLib database dumps API."""
    dumps = get_database_dumps()
    if not dumps:
        return None
    dumps.sort(key=lambda x: x.uploaded, reverse=True)
    return dumps[0]


def download_database_dump(
    dump: DatabaseDump,
    download_path: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Optional[str]:
    """Download a database dump file."""
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

            with open(download_path, "wb") as file:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    file.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)

        logger.info("Downloaded database dump to %s", download_path)
        return download_path

    except HTTPError as error:
        error_data = error.read().decode("utf-8")
        try:
            error_json = json.loads(error_data)
            raise LyriqError(
                error_json.get("statusCode", error.code),
                error_json.get("name", "Unknown error"),
                error_json.get("message", "Unknown error"),
            ) from error
        except json.JSONDecodeError:
            logger.error("Error downloading database dump: HTTP %s", error.code)
            return None
    except Exception as error:
        logger.error("Error downloading database dump: %s", error)
        return None
