"""
Tests for the lyriq module.

These tests cover the functionality of the lyriq module, including:
- Lyrics class
- LyricsCache functionality
- get_lyrics function
- Helper functions
"""

import json
import os
import tempfile
import time
import urllib.error
import urllib.request
import email.message
from unittest import mock

import pytest

from lyriq import Lyrics, LyriqError, get_lyrics
from lyriq.lyriq import (
    API_URL,
    _LyricsCache,
    _json_get,
    _normalize_name,
    _process_lyrics,
    get_lyrics_by_id,
    search_lyrics,
    to_plain_lyrics,
    request_challenge,
    verify_nonce,
    generate_publish_token,
    publish_lyrics,
)


@pytest.fixture
def sample_lyrics_data():
    """
    Sample lyrics data for testing.

    Returns:
        Dictionary containing sample lyrics data.
    """
    return {
        "syncedLyrics": "[00:00.00]Test Lyrics\n[00:05.00]Second Line\n[00:10.00]",
        "plainLyrics": "Test Lyrics\nSecond Line\n\nThird Section",
        "id": "test123",
        "name": "Test Song",
        "trackName": "Test Track",
        "artistName": "Test Artist",
        "albumName": "Test Album",
        "duration": 180,
        "instrumental": False,
    }


@pytest.fixture
def sample_lyrics_object(sample_lyrics_data):
    """
    Create a sample Lyrics object for testing.

    Args:
        sample_lyrics_data: The sample lyrics data from the fixture.

    Returns:
        A Lyrics object created from the sample data.
    """
    return Lyrics.from_dict(sample_lyrics_data)


@pytest.fixture
def temp_cache_file():
    """
    Create a temporary cache file for testing.

    Yields:
        Path to the temporary file.
    """
    with tempfile.NamedTemporaryFile(delete=False) as f:
        yield f.name
    if os.path.exists(f.name):
        os.unlink(f.name)


@pytest.fixture
def temp_output_file():
    """
    Create a temporary output file for testing.

    Yields:
        Path to the temporary file.
    """
    with tempfile.NamedTemporaryFile(delete=False) as f:
        temp_file = f.name

    yield temp_file
    if os.path.exists(temp_file):
        os.unlink(temp_file)


class TestLyricsClass:
    """Tests for the Lyrics class."""

    def test_from_dict(self, sample_lyrics_data):
        """Test creating a Lyrics object from a dictionary."""
        lyrics = Lyrics.from_dict(sample_lyrics_data)

        assert lyrics.id == "test123"
        assert lyrics.track_name == "Test Track"
        assert lyrics.artist_name == "Test Artist"
        assert lyrics.album_name == "Test Album"
        assert lyrics.duration == 180
        assert lyrics.synced_lyrics == sample_lyrics_data["syncedLyrics"]
        assert lyrics.plain_lyrics == sample_lyrics_data["plainLyrics"]

    def test_to_dict(self, sample_lyrics_object):
        """Test converting a Lyrics object to a dictionary."""
        lyrics_dict = sample_lyrics_object.to_dict()

        assert lyrics_dict["id"] == "test123"
        assert lyrics_dict["track_name"] == "Test Track"
        assert lyrics_dict["artist_name"] == "Test Artist"
        assert lyrics_dict["album_name"] == "Test Album"
        assert lyrics_dict["duration"] == 180
        assert "lyrics" in lyrics_dict
        assert "synced_lyrics" in lyrics_dict
        assert "plain_lyrics" in lyrics_dict

    def test_bool_method(self, sample_lyrics_object):
        """Test the __bool__ method of Lyrics."""
        assert bool(sample_lyrics_object) is True

        empty_lyrics = Lyrics(
            lyrics={},
            synced_lyrics="",
            plain_lyrics="",
            id="empty",
            name="Empty",
            track_name="Empty",
            artist_name="Empty",
            album_name="Empty",
            duration=0,
            instrumental=False,
        )
        assert bool(empty_lyrics) is False

    def test_to_plain_file(self, sample_lyrics_object, temp_output_file):
        """Test writing lyrics to a plain text file."""
        sample_lyrics_object.to_plain_file(temp_output_file)

        assert os.path.exists(temp_output_file)
        with open(temp_output_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "Test Lyrics" in content
            assert "Second Line" in content

    def test_to_plain_file_with_synced_lyrics(self, temp_output_file):
        """Test writing synced lyrics to a plain text file."""
        lyrics = Lyrics(
            lyrics={"00:00.00": "First Line", "00:05.00": "Second Line"},
            synced_lyrics="",
            plain_lyrics="",
            id="test",
            name="Test",
            track_name="Test Track",
            artist_name="Test Artist",
            album_name="Test Album",
            duration=180,
            instrumental=False,
        )

        lyrics.to_plain_file(temp_output_file)

        assert os.path.exists(temp_output_file)
        with open(temp_output_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "00:00.00 First Line" in content
            assert "00:05.00 Second Line" in content

    def test_to_json_file(self, sample_lyrics_object, temp_output_file):
        """Test writing lyrics to a JSON file."""
        sample_lyrics_object.to_json_file(temp_output_file)

        assert os.path.exists(temp_output_file)
        with open(temp_output_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["id"] == "test123"
            assert data["track_name"] == "Test Track"
            assert data["artist_name"] == "Test Artist"

    def test_from_json_file(self, sample_lyrics_object, temp_output_file):
        """Test reading lyrics from a JSON file."""
        sample_lyrics_object.to_json_file(temp_output_file)

        lyrics = Lyrics(
            lyrics={},
            synced_lyrics="",
            plain_lyrics="",
            id="",
            name="",
            track_name="",
            artist_name="",
            album_name="",
            duration=0,
            instrumental=False,
        )

        loaded_lyrics = lyrics.from_json_file(temp_output_file)

        assert loaded_lyrics.id == sample_lyrics_object.id
        assert loaded_lyrics.track_name == sample_lyrics_object.track_name
        assert loaded_lyrics.artist_name == sample_lyrics_object.artist_name
        assert "00:00.00" in loaded_lyrics.lyrics


class TestProcessLyrics:
    """Tests for the _process_lyrics function."""

    def test_process_synced_lyrics(self, sample_lyrics_data):
        """Test processing synchronized lyrics."""
        result = _process_lyrics(sample_lyrics_data)

        assert "00:00.00" in result
        assert result["00:00.00"] == "Test Lyrics"
        assert "00:05.00" in result
        assert result["00:05.00"] == "Second Line"
        assert "00:10.00" in result
        assert result["00:10.00"] == "♪"

    def test_process_plain_lyrics_only(self):
        """Test processing plain lyrics when no synced lyrics are available."""
        data = {
            "syncedLyrics": "",
            "plainLyrics": "Line 1\nLine 2\nLine 3",
            "id": "test",
        }

        result = _process_lyrics(data)

        assert "00.00" in result
        assert "01.00" in result
        assert "02.00" in result
        assert result["00.00"] == "Line 1"
        assert result["01.00"] == "Line 2"
        assert result["02.00"] == "Line 3"

    def test_process_empty_lyrics(self):
        """Test processing empty lyrics."""
        data = {"syncedLyrics": "", "plainLyrics": "", "id": "test"}

        result = _process_lyrics(data)

        assert not result

    def test_custom_none_char(self, sample_lyrics_data):
        """Test using a custom character for empty lines."""
        result = _process_lyrics(sample_lyrics_data, none_char="***")

        assert result["00:10.00"] == "***"


class TestNormalizeName:
    """Tests for the _normalize_name function."""

    def test_normalize_name(self):
        """Test normalizing artist and song names."""
        assert _normalize_name("Test·Name") == "test-name"
        assert _normalize_name("Normal Name") == "normal name"
        assert _normalize_name("") == ""


class TestJsonGet:
    """Tests for the _json_get function."""

    @mock.patch("urllib.request.urlopen")
    def test_json_get(self, mock_urlopen):
        """Test the JSON GET function."""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps({"key": "value"}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = _json_get("https://example.com/api")

        assert result == {"key": "value"}
        mock_urlopen.assert_called_once()

        args, _ = mock_urlopen.call_args
        request = args[0]
        assert "Lyriq v" in request.get_header("User-agent")
        assert "github.com/TN3W/lyriq" in request.get_header("User-agent")


class TestLyricsCache:
    """Tests for the _LyricsCache class."""

    def test_cache_init(self, temp_cache_file):
        """Test initializing the cache."""
        cache = _LyricsCache(temp_cache_file)
        assert cache.cache == {}

    def test_cache_with_existing_file(self, temp_cache_file):
        """Test loading cache from an existing file."""
        cache_data = {"test_key": {"id": "123", "name": "Test"}}
        with open(temp_cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f)

        cache = _LyricsCache(temp_cache_file)

        assert cache.cache == cache_data
        assert cache.get("test_key") == {"id": "123", "name": "Test"}

    def test_set_and_get(self, temp_cache_file):
        """Test setting and getting cache values."""
        cache = _LyricsCache(temp_cache_file)
        cache.set("test_key", {"id": "123"})

        assert cache.get("test_key") == {"id": "123"}
        assert cache.get("non_existent") is None

    def test_cache_write(self, temp_cache_file):
        """Test that cache writes to disk."""
        cache = _LyricsCache(temp_cache_file)
        cache.set("test_key", {"id": "123"})

        time.sleep(0.1)

        assert os.path.exists(temp_cache_file)

        with open(temp_cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert "test_key" in data
            assert data["test_key"] == {"id": "123"}

    def test_get_by_id(self, temp_cache_file):
        """Test getting a cache entry by ID."""
        cache = _LyricsCache(temp_cache_file)

        cache.set("test_key", {"id": "123", "name": "Test"})
        cache.set("another_key", {"id": "456", "name": "Another"})

        result = cache.get_by_lyrics_id("123")
        assert result == {"id": "123", "name": "Test"}

        assert cache.get_by_lyrics_id("non_existent") is None


class TestGetLyrics:
    """Tests for the get_lyrics function."""

    def test_get_lyrics_success(self):
        """Test successful lyrics retrieval."""
        with (
            mock.patch("lyriq.lyriq.lyrics_cache") as mock_cache,
            mock.patch("lyriq.lyriq._json_get") as mock_json_get,
        ):

            mock_cache.get.return_value = None
            sample_data = {
                "syncedLyrics": "[00:00.00]Test",
                "plainLyrics": "Test",
                "id": "test123",
                "name": "Test Song",
                "trackName": "Test Track",
                "artistName": "Test Artist",
                "albumName": "Test Album",
                "duration": 180,
                "instrumental": False,
            }
            mock_json_get.return_value = sample_data

            lyrics = get_lyrics("Test Track", "Test Artist")

            assert lyrics is not None
            assert lyrics.track_name == "Test Track"
            assert lyrics.artist_name == "Test Artist"

            mock_json_get.assert_called_once()
            called_url = mock_json_get.call_args[0][0]
            assert API_URL in called_url
            assert "track_name=test+track" in called_url
            assert "artist_name=test+artist" in called_url

    @mock.patch("lyriq.lyriq._json_get")
    def test_get_lyrics_with_album(self, mock_json_get, sample_lyrics_data):
        """Test lyrics retrieval with album name."""
        mock_json_get.return_value = sample_lyrics_data

        with mock.patch("lyriq.lyriq.lyrics_cache") as mock_cache:
            mock_cache.get.return_value = None
            get_lyrics("Test Track", "Test Artist", album_name="Test Album")

            mock_json_get.assert_called_once()
            called_url = mock_json_get.call_args[0][0]
            assert "album_name=test+album" in called_url

    @mock.patch("lyriq.lyriq._json_get")
    def test_get_lyrics_failure(self, mock_json_get):
        """Test handling of API failure."""
        mock_json_get.side_effect = Exception("API error")

        with mock.patch("lyriq.lyriq.lyrics_cache") as mock_cache:
            mock_cache.get.return_value = None
            with pytest.raises(Exception) as excinfo:
                get_lyrics("Test Track", "Test Artist")

            assert "API error" in str(excinfo.value)


class TestGetLyricsById:
    """Tests for the get_lyrics_by_id function."""

    def test_get_lyrics_by_id_from_cache(self):
        """Test retrieving lyrics by ID from cache."""
        with mock.patch("lyriq.lyriq.lyrics_cache") as mock_cache:
            sample_data = {
                "syncedLyrics": "[00:00.00]Test",
                "plainLyrics": "Test",
                "id": "test123",
                "name": "Test Song",
                "trackName": "Test Track",
                "artistName": "Test Artist",
                "albumName": "Test Album",
                "duration": 180,
                "instrumental": False,
            }

            mock_cache.get_by_lyrics_id.return_value = sample_data

            lyrics = get_lyrics_by_id("test123")

            assert lyrics is not None
            assert lyrics.id == "test123"
            assert lyrics.track_name == "Test Track"
            mock_cache.get_by_lyrics_id.assert_called_once_with("test123")

    def test_get_lyrics_by_id_from_api(self):
        """Test retrieving lyrics by ID from API."""
        with (
            mock.patch("lyriq.lyriq.lyrics_cache") as mock_cache,
            mock.patch("lyriq.lyriq._json_get") as mock_json_get,
        ):
            sample_data = {
                "syncedLyrics": "[00:00.00]Test",
                "plainLyrics": "Test",
                "id": "test123",
                "name": "Test Song",
                "trackName": "Test Track",
                "artistName": "Test Artist",
                "albumName": "Test Album",
                "duration": 180,
                "instrumental": False,
            }

            mock_cache.get_by_lyrics_id.return_value = None
            mock_json_get.return_value = sample_data

            lyrics = get_lyrics_by_id("test123")

            assert lyrics is not None
            assert lyrics.id == "test123"
            assert lyrics.track_name == "Test Track"
            mock_json_get.assert_called_once()
            called_url = mock_json_get.call_args[0][0]
            assert f"{API_URL}/get/test123" in called_url

    def test_get_lyrics_by_id_failure(self):
        """Test handling of API failure when retrieving lyrics by ID."""
        with (
            mock.patch("lyriq.lyriq.lyrics_cache") as mock_cache,
            mock.patch("lyriq.lyriq._json_get") as mock_json_get,
        ):
            mock_cache.get_by_lyrics_id.return_value = None
            mock_json_get.side_effect = Exception("API error")

            with pytest.raises(Exception) as excinfo:
                get_lyrics_by_id("test123")

            assert "API error" in str(excinfo.value)


class TestSearchLyrics:
    """Tests for the search_lyrics function."""

    def test_search_lyrics_by_query(self):
        """Test searching lyrics by general query."""
        with (
            mock.patch("lyriq.lyriq.search_cache") as mock_search_cache,
            mock.patch("lyriq.lyriq._json_get") as mock_json_get,
            mock.patch("lyriq.lyriq.lyrics_cache") as mock_lyrics_cache,
            mock.patch("builtins.open", mock.mock_open()),
        ):
            mock_search_cache.get.return_value = None
            sample_results = [
                {
                    "id": "test123",
                    "name": "Test Song",
                    "trackName": "Test Track",
                    "artistName": "Test Artist",
                    "albumName": "Test Album",
                    "syncedLyrics": "[00:00.00]Test Lyrics",
                    "plainLyrics": "Test Lyrics",
                    "duration": 180,
                    "instrumental": False,
                },
                {
                    "id": "test456",
                    "name": "Another Song",
                    "trackName": "Another Track",
                    "artistName": "Another Artist",
                    "albumName": "Another Album",
                    "syncedLyrics": "[00:00.00]Another Test Lyrics",
                    "plainLyrics": "Another Test Lyrics",
                    "duration": 200,
                    "instrumental": False,
                },
            ]
            mock_json_get.return_value = sample_results
            mock_lyrics_cache.get_bulk_by_lyrics_id.return_value = []

            results = search_lyrics(q="test query")

            assert results is not None
            assert len(results) == 2
            assert results[0].id == "test123"
            assert results[0].track_name == "Test Track"
            assert results[1].id == "test456"
            assert results[1].track_name == "Another Track"

            mock_json_get.assert_called_once()
            called_url = mock_json_get.call_args[0][0]
            assert f"{API_URL}/search" in called_url
            assert "q=test+query" in called_url

    def test_search_lyrics_by_song_artist(self):
        """Test searching lyrics by song and artist name."""
        with (
            mock.patch("lyriq.lyriq.search_cache") as mock_search_cache,
            mock.patch("lyriq.lyriq._json_get") as mock_json_get,
            mock.patch("lyriq.lyriq.lyrics_cache") as mock_lyrics_cache,
            mock.patch("builtins.open", mock.mock_open()),
        ):
            mock_search_cache.get.return_value = None
            sample_results = [
                {
                    "id": "test123",
                    "name": "Test Song",
                    "trackName": "Test Track",
                    "artistName": "Test Artist",
                    "albumName": "Test Album",
                    "syncedLyrics": "[00:00.00]Test Lyrics",
                    "plainLyrics": "Test Lyrics",
                    "duration": 180,
                    "instrumental": False,
                }
            ]
            mock_json_get.return_value = sample_results
            mock_lyrics_cache.get_bulk_by_lyrics_id.return_value = []

            results = search_lyrics(song_name="Test Track", artist_name="Test Artist")

            assert results is not None
            assert len(results) == 1
            assert results[0].id == "test123"
            assert results[0].track_name == "Test Track"
            assert results[0].artist_name == "Test Artist"

            mock_json_get.assert_called_once()
            called_url = mock_json_get.call_args[0][0]
            assert f"{API_URL}/search" in called_url
            assert "track_name=test+track" in called_url
            assert "artist_name=test+artist" in called_url

    def test_search_lyrics_from_cache(self):
        """Test retrieving search results from cache."""
        with (
            mock.patch("lyriq.lyriq.search_cache") as mock_search_cache,
            mock.patch("lyriq.lyriq.lyrics_cache") as mock_lyrics_cache,
            mock.patch("lyriq.lyriq._json_get") as mock_json_get,
        ):
            cached_ids = ["test123", "test456"]
            mock_search_cache.get.return_value = cached_ids

            cached_lyrics = [
                {
                    "id": "test123",
                    "name": "Test Song",
                    "trackName": "Test Track",
                    "artistName": "Test Artist",
                    "albumName": "Test Album",
                    "syncedLyrics": "[00:00.00]Test Lyrics",
                    "plainLyrics": "Test Lyrics",
                    "duration": 180,
                    "instrumental": False,
                },
                {
                    "id": "test456",
                    "name": "Another Song",
                    "trackName": "Another Track",
                    "artistName": "Another Artist",
                    "albumName": "Another Album",
                    "syncedLyrics": "[00:00.00]Another Lyrics",
                    "plainLyrics": "Another Lyrics",
                    "duration": 200,
                    "instrumental": False,
                },
            ]
            mock_lyrics_cache.get_bulk_by_lyrics_id.return_value = cached_lyrics

            results = search_lyrics(q="test query")

            assert results is not None
            assert len(results) == 2
            assert results[0].id == "test123"
            assert results[1].id == "test456"

            mock_json_get.assert_not_called()
            mock_lyrics_cache.get_bulk_by_lyrics_id.assert_called_once_with(cached_ids)

    def test_search_lyrics_with_album(self):
        """Test searching lyrics with album name."""
        with (
            mock.patch("lyriq.lyriq.search_cache") as mock_search_cache,
            mock.patch("lyriq.lyriq._json_get") as mock_json_get,
            mock.patch("lyriq.lyriq.lyrics_cache") as mock_lyrics_cache,
            mock.patch("builtins.open", mock.mock_open()),
        ):
            mock_search_cache.get.return_value = None
            sample_results = [
                {
                    "id": "test123",
                    "name": "Test Song",
                    "trackName": "Test Track",
                    "artistName": "Test Artist",
                    "albumName": "Test Album",
                    "syncedLyrics": "[00:00.00]Test Lyrics",
                    "plainLyrics": "Test Lyrics",
                    "duration": 180,
                    "instrumental": False,
                }
            ]
            mock_json_get.return_value = sample_results
            mock_lyrics_cache.get_bulk_by_lyrics_id.return_value = []

            results = search_lyrics(
                song_name="Test Track",
                artist_name="Test Artist",
                album_name="Test Album",
            )

            assert results is not None
            assert len(results) == 1
            assert results[0].album_name == "Test Album"

            mock_json_get.assert_called_once()
            called_url = mock_json_get.call_args[0][0]
            assert "album_name=test+album" in called_url

    def test_search_lyrics_invalid_params(self):
        """Test handling of invalid parameters."""
        with pytest.raises(ValueError) as excinfo:
            search_lyrics()

        assert "Either q or song_name must be provided" in str(excinfo.value)

    def test_search_lyrics_api_error(self):
        """Test handling of API error."""
        with (
            mock.patch("lyriq.lyriq.search_cache") as mock_search_cache,
            mock.patch("lyriq.lyriq._json_get") as mock_json_get,
        ):
            mock_search_cache.get.return_value = None
            mock_json_get.side_effect = LyriqError(404, "Not Found", "No results found")

            results = search_lyrics(q="test query")

            assert results is None
            mock_json_get.assert_called_once()


class TestToPlainLyrics:
    """Tests for the to_plain_lyrics function."""

    def test_to_plain_lyrics_from_lyrics_object_with_plain(self, sample_lyrics_object):
        """Test converting a Lyrics object with plain lyrics to plain text."""
        result = to_plain_lyrics(sample_lyrics_object)

        assert "Test Lyrics" in result
        assert "Second Line" in result
        assert "Third Section" in result

    def test_to_plain_lyrics_from_lyrics_object_with_synced(self):
        """Test converting a Lyrics object with synced lyrics to plain text."""
        lyrics = Lyrics(
            lyrics={},
            synced_lyrics="[00:00.00]First Line\n[00:05.00]Second Line\n[00:10.00]\n",
            plain_lyrics="",
            id="test",
            name="Test",
            track_name="Test Track",
            artist_name="Test Artist",
            album_name="Test Album",
            duration=180,
            instrumental=False,
        )

        result = to_plain_lyrics(lyrics)

        assert "First Line" in result
        assert "Second Line" in result
        assert "♪" in result

    def test_to_plain_lyrics_from_dict_with_plain(self):
        """Test converting a dictionary with plain lyrics to plain text."""
        data = {
            "plainLyrics": "Line 1\nLine 2\nLine 3",
        }

        result = to_plain_lyrics(data)

        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_to_plain_lyrics_from_dict_with_synced(self):
        """Test converting a dictionary with synced lyrics to plain text."""
        data = {"syncedLyrics": "[00:00.00]Line 1\n[00:05.00]Line 2\n[00:10.00]\n"}

        result = to_plain_lyrics(data)

        assert "Line 1" in result
        assert "Line 2" in result
        assert "♪" in result

    def test_to_plain_lyrics_from_synced_dict(self):
        """Test converting a synced lyrics dictionary to plain text."""
        data = {
            "00:00.00": "Line 1",
            "00:05.00": "Line 2",
            "00:10.00": "",
        }

        result = to_plain_lyrics(data)

        assert "Line 1" in result
        assert "Line 2" in result
        assert "♪" in result

    def test_to_plain_lyrics_custom_none_char(self):
        """Test using a custom character for empty lines."""
        lyrics = Lyrics(
            lyrics={},
            synced_lyrics="[00:00.00]First Line\n[00:05.00]Second Line\n[00:10.00]\n",
            plain_lyrics="",
            id="test",
            name="Test",
            track_name="Test Track",
            artist_name="Test Artist",
            album_name="Test Album",
            duration=180,
            instrumental=False,
        )

        result = to_plain_lyrics(lyrics, none_char="***")

        assert "First Line" in result
        assert "Second Line" in result
        assert "***" in result


class TestLyriqError:
    """Tests for the LyriqError class."""

    def test_lyriq_error_init(self):
        """Test initializing a LyriqError."""
        error = LyriqError(404, "Not Found", "The requested resource was not found")

        assert error.code == 404
        assert error.name == "Not Found"
        assert error.message == "The requested resource was not found"
        assert "404 Not Found: The requested resource was not found" in str(error)


class TestVerifyNonce:
    """Tests for the verify_nonce function."""

    def test_verify_nonce_true(self):
        """Test the verify_nonce function with valid nonce."""
        target_bytes = bytes.fromhex(
            "000000FF00000000000000000000000000000000000000000000000000000000"
        )
        result_bytes = bytes.fromhex(
            "000000AA00000000000000000000000000000000000000000000000000000000"
        )

        assert verify_nonce(result_bytes, target_bytes) is True

    def test_verify_nonce_false(self):
        """Test the verify_nonce function with invalid nonce."""
        target_bytes = bytes.fromhex(
            "000000AA00000000000000000000000000000000000000000000000000000000"
        )
        result_bytes = bytes.fromhex(
            "000000FF00000000000000000000000000000000000000000000000000000000"
        )

        assert verify_nonce(result_bytes, target_bytes) is False

    def test_verify_nonce_equal(self):
        """Test the verify_nonce function with equal values."""
        target_bytes = bytes.fromhex(
            "000000AA00000000000000000000000000000000000000000000000000000000"
        )
        result_bytes = bytes.fromhex(
            "000000AA00000000000000000000000000000000000000000000000000000000"
        )

        assert verify_nonce(result_bytes, target_bytes) is True

    def test_verify_nonce_different_lengths(self):
        """Test the verify_nonce function with different length inputs."""
        target_bytes = bytes.fromhex("000000AA00000000")
        result_bytes = bytes.fromhex("000000AA0000000000000000")

        assert verify_nonce(result_bytes, target_bytes) is False


class TestRequestChallenge:
    """Tests for the request_challenge function."""

    @mock.patch("urllib.request.urlopen")
    def test_request_challenge_success(self, mock_urlopen):
        """Test successful challenge request."""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "prefix": "TestPrefix123",
                "target": "000000FF00000000000000000000000000000000000000000000000000000000",
            }
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        prefix, target = request_challenge()

        assert prefix == "TestPrefix123"
        assert (
            target == "000000FF00000000000000000000000000000000000000000000000000000000"
        )
        mock_urlopen.assert_called_once()

    @mock.patch("urllib.request.urlopen")
    def test_request_challenge_error(self, mock_urlopen):
        """Test handling API error."""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "statusCode": 500,
                "name": "ServerError",
                "message": "Internal server error",
            }
        ).encode("utf-8")

        headers = email.message.Message()
        headers["Content-Type"] = "application/json"

        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://example.com", 500, "Server Error", headers, mock_response
        )

        with pytest.raises(LyriqError) as excinfo:
            request_challenge()

        assert excinfo.value.code == 500
        assert excinfo.value.name == "ServerError"
        assert "Internal server error" in excinfo.value.message


class TestGeneratePublishToken:
    """Tests for the generate_publish_token function."""

    @mock.patch("lyriq.lyriq.request_challenge")
    @mock.patch("lyriq.lyriq.verify_nonce")
    def test_generate_publish_token(self, mock_verify_nonce, mock_request_challenge):
        """Test generating a publish token."""
        mock_request_challenge.return_value = (
            "TestPrefix123",
            "000000FF00000000000000000000000000000000000000000000000000000000",
        )
        mock_verify_nonce.return_value = True

        token = generate_publish_token()

        assert token.startswith("TestPrefix123:")
        assert token.count(":") == 1
        mock_request_challenge.assert_called_once()
        mock_verify_nonce.assert_called_once()


class TestPublishLyrics:
    """Tests for the publish_lyrics function."""

    @mock.patch("lyriq.lyriq.generate_publish_token")
    @mock.patch("urllib.request.urlopen")
    def test_publish_lyrics_success(self, mock_urlopen, mock_generate_token):
        """Test successful lyrics publishing."""
        mock_generate_token.return_value = "TestPrefix123:456789"

        mock_response = mock.MagicMock()
        mock_response.status = 201
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = publish_lyrics(
            track_name="Test Track",
            artist_name="Test Artist",
            album_name="Test Album",
            duration=180,
            plain_lyrics="Test lyrics",
            synced_lyrics="[00:00.00]Test lyrics",
        )

        assert result is True
        mock_generate_token.assert_called_once()
        mock_urlopen.assert_called_once()

        args, _ = mock_urlopen.call_args
        request = args[0]
        assert "X-publish-token" in request.headers
        assert request.headers["X-publish-token"] == "TestPrefix123:456789"
        assert "Content-type" in request.headers
        assert request.headers["Content-type"] == "application/json"

        request_data = request.data.decode("utf-8")
        assert "trackName" in request_data
        assert "artistName" in request_data
        assert "albumName" in request_data
        assert "Test Track" in request_data
        assert "Test Artist" in request_data
        assert "Test Album" in request_data

    @mock.patch("lyriq.lyriq.generate_publish_token")
    @mock.patch("urllib.request.urlopen")
    def test_publish_lyrics_non_success_status(self, mock_urlopen, mock_generate_token):
        """Test handling of non-success status code."""
        mock_generate_token.return_value = "TestPrefix123:456789"

        mock_response = mock.MagicMock()
        mock_response.status = 400
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = publish_lyrics(
            track_name="Test Track",
            artist_name="Test Artist",
            album_name="Test Album",
            duration=180,
        )

        assert result is False

    @mock.patch("lyriq.lyriq.generate_publish_token")
    @mock.patch("urllib.request.urlopen")
    def test_publish_lyrics_http_error(self, mock_urlopen, mock_generate_token):
        """Test handling HTTP error."""
        mock_generate_token.return_value = "TestPrefix123:456789"

        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "statusCode": 400,
                "name": "IncorrectPublishTokenError",
                "message": "The provided publish token is incorrect",
            }
        ).encode("utf-8")

        headers = email.message.Message()
        headers["Content-Type"] = "application/json"

        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://example.com", 400, "Bad Request", headers, mock_response
        )

        with pytest.raises(LyriqError) as excinfo:
            publish_lyrics(
                track_name="Test Track",
                artist_name="Test Artist",
                album_name="Test Album",
                duration=180,
            )

        assert excinfo.value.code == 400
        assert excinfo.value.name == "IncorrectPublishTokenError"
        assert "incorrect" in excinfo.value.message


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
