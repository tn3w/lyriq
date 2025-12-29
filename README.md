# Lyriq

A lightweight Python library designed to effortlessly fetch and display song lyrics, with support for synchronized lyrics and an accompanying CLI tool.

[![PyPI version](https://img.shields.io/pypi/v/lyriq.svg)](https://pypi.org/project/lyriq/)
[![Python Versions](https://img.shields.io/pypi/pyversions/lyriq.svg)](https://pypi.org/project/lyriq/)
[![License](https://img.shields.io/github/license/tn3w/lyriq.svg)](https://github.com/tn3w/lyriq/blob/main/LICENSE)

## Features

- Fetch lyrics from the LRCLib API
- Support for both plain and synchronized lyrics
- Built-in caching to reduce API calls
- CLI tool with synchronized lyrics playback
- Support for saving/loading lyrics in JSON and plain text formats
- Colorful terminal output with synchronized highlighting
- Database dump management with download functionality
- Progress tracking for large file downloads

## Installation

### From PyPI

```bash
pip install lyriq
```

### Development Installation

```bash
git clone https://github.com/tn3w/lyriq.git
cd lyriq
pip install -e ".[dev]"
```

## Usage

### Basic Usage

```python
import sys
from lyriq import get_lyrics

lyrics = get_lyrics("Circles", "Post Malone")
if not lyrics:
    print("No lyrics found for 'Circles' by Post Malone")
    sys.exit(0)

print(f"ID: {lyrics.id}")
print(f"Name: {lyrics.name}")
print(f"Track: {lyrics.track_name}")
print(f"Artist: {lyrics.artist_name}")
print(f"Album: {lyrics.album_name}")
print(f"Duration: {lyrics.duration} seconds")
print(f"Instrumental: {'Yes' if lyrics.synced_lyrics else 'No'}")
print("\nPlain Lyrics:")
print("-" * 40)
print(lyrics.plain_lyrics)
print("\nSynchronized Lyrics (timestamp: lyric):")
print("-" * 40)

for timestamp, line in sorted(lyrics.lyrics.items()):
    print(f"[{timestamp}] {line}")

print("-" * 40)
```

### Fetch by ID

```python
from lyriq import get_lyrics_by_id

# Fetch lyrics by ID
lyrics = get_lyrics_by_id("449")  # ID for "Circles" by Post Malone

if lyrics:
    print(f"Found: {lyrics.track_name} by {lyrics.artist_name}")
```

### Convert to Plain Text

```python
from lyriq import to_plain_lyrics, get_lyrics

lyrics = get_lyrics("Circles", "Post Malone")
plain_text = to_plain_lyrics(lyrics)
print(plain_text)
```

### Search for Lyrics

```python
from lyriq import search_lyrics

# Search by general query
results = search_lyrics(q="Circles Post Malone")

# Or search by song and artist name
results = search_lyrics(song_name="Circles", artist_name="Post Malone")

if results:
    print(f"Found {len(results)} results:")
    for i, lyrics in enumerate(results[:3]):  # Display first 3 results
        print(f"{i+1}. {lyrics.track_name} by {lyrics.artist_name} ({lyrics.album_name})")
else:
    print("No results found")
```

### Save and Load Lyrics

```python
from lyriq import get_lyrics

# Fetch and save lyrics
lyrics = get_lyrics("Circles", "Post Malone")

# Save to plain text file
lyrics.to_plain_file("circles.txt")

# Save to JSON file
lyrics.to_json_file("circles.json")

# Load from JSON file
loaded_lyrics = lyrics.from_json_file("circles.json")
```

### Database Dumps

```python
from lyriq import get_database_dumps, get_latest_database_dump, download_database_dump

# Get all available database dumps
dumps = get_database_dumps()
if dumps:
    print(f"Found {len(dumps)} database dumps:")
    for i, dump in enumerate(dumps, 1):
        size_mb = dump.size / (1024 * 1024)
        print(f"{i}. {dump.filename} ({size_mb:.1f} MB)")

# Get the latest database dump
latest_dump = get_latest_database_dump()
if latest_dump:
    print(f"Latest dump: {latest_dump.filename}")
    print(f"Size: {latest_dump.size / (1024 * 1024):.1f} MB")
    print(f"Uploaded: {latest_dump.uploaded}")

# Download a database dump with progress tracking
def progress_callback(downloaded, total):
    if total > 0:
        percent = (downloaded / total) * 100
        print(f"Progress: {percent:.1f}%")

if latest_dump:
    file_path = download_database_dump(
        latest_dump, 
        download_path="./my_dump.sqlite3.gz",
        progress_callback=progress_callback
    )
    if file_path:
        print(f"Downloaded to: {file_path}")
```

## Command Line Interface

The library comes with a command-line interface for quick access to lyrics with synchronized lyrics playback:
```
usage: lyriq [-h] [-v] [--id ID] [--duration [DURATION]] [--search [SEARCH]]
             [--search-index SEARCH_INDEX] [--none-char NONE_CHAR] [--no-info]
             [--plain [{plain,lrc,json}]] [--file FILE] [--file-format {plain,lrc,json}]
             [--load LOAD] [--dumps] [--dumps-index DUMPS_INDEX]
             [--publish] [--sync [SYNC]] [--audio AUDIO]
             [song_name] [artist_name] [album_name]

Fetch and display song lyrics

positional arguments:
  song_name             Name of the song (optional)
  artist_name           Name of the artist (optional)
  album_name            Name of the album (optional)

options:
  -h, --help            show this help message and exit
  -v, --version         show version message and exit
  --id ID               ID of the song
  --duration [DURATION]
                        Duration of the song (optional)
  --search [SEARCH]     Search for lyrics by song name and artist name. Optionally provide a search query.
  --search-index SEARCH_INDEX
                        Select search result at specified index directly (1-based)
  --none-char NONE_CHAR
                        Character to use for empty lines
  --no-info             Do not display track information
  --plain [{plain,lrc,json}]
                        Display only plain lyrics (default), or specify 'lrc' or 'json' for other formats
  --file FILE           File to save lyrics to and exit
  --file-format {plain,lrc,json}
                        Format to save lyrics to
  --load LOAD           Load lyrics from file
  --dumps               List and download database dumps
  --dumps-index DUMPS_INDEX
                        Select database dump at specified index directly (1-based)
  --publish             Publish lyrics to the database. Requires --load with song_name and artist_name
  --sync [SYNC]         Sync plain lyrics (from --load) to create LRC. Optionally specify output file (default: <input>.lrc)
  --audio AUDIO         Audio file to play during sync (requires pygame)
```

### Usage Examples

```bash
# Basic usage
lyriq "Circles" "Post Malone"

# With album name (optional)
lyriq "Circles" "Post Malone" "Hollywood's Bleeding"

# With duration (optional)
lyriq "Circles" "Post Malone" --duration 210

# Fetch lyrics by ID
lyriq --id 449

# Custom character for empty lines
lyriq "Circles" "Post Malone" --none-char "*"

# Display no track information
lyriq "Circles" "Post Malone" --no-info

# Display only plain lyrics
lyriq "Circles" "Post Malone" --plain

# Display plain lyrics in other formats
lyriq "Circles" "Post Malone" --plain lrc
lyriq "Circles" "Post Malone" --plain json

# Save lyrics to file and exit
lyriq "Circles" "Post Malone" --file Circles-Post-Malone.txt

# Save lyrics to JSON file and exit
lyriq "Circles" "Post Malone" --file Circles-Post-Malone.json --file-format json

# Save lyrics to LRC file and exit
lyriq "Circles" "Post Malone" --file Circles-Post-Malone.json --file-format lrc

# Load lyrics from file
lyriq --load Circles-Post-Malone.json
lyriq --load Circles-Post-Malone.lrc

# Publish lyrics to the database (requires song_name, artist_name, album_name, and --load)
lyriq "Song Name" "Artist Name" "Album Name" --load lyrics.lrc --publish --duration 180

# Sync plain lyrics to create LRC file (manual timing)
lyriq --load lyrics.txt --sync

# Sync lyrics with audio playback (requires pygame)
lyriq --load lyrics.txt --sync --audio song.mp3

# Sync with custom output file
lyriq --load lyrics.txt --sync synced.lrc --audio song.mp3

# Search for lyrics using song name and artist name fields with interactive UI
lyriq "Circles" "Post Malone" --search

# Search with general query
lyriq --search "Circles Post Malone"

# Search and select result at specific index
lyriq --search "Circles Post Malone" --search-index 1

# List and download database dumps with interactive UI
lyriq --dumps

# Download database dump at specific index directly
lyriq --dumps --dumps-index 1
```

### CLI Features

- Display song metadata with colored highlighting of differences
- Synchronized lyrics playback (if available)
- Interactive controls:
    - Press `SPACE` (or custom character): Play/Pause
    - Press `←` / `→` arrows: Rewind/Fast-forward by 5 seconds
    - Press `r`: Toggle repeat
    - Press `q`: Quit
- Interactive search UI:
    - Navigate results with `↑` / `↓` arrow keys
    - Select with `Enter` or number keys `1-9`
    - Pagination with 4 results per page
    - Shows synchronized lyrics availability with color indicators
- Lyrics sync tool:
    - Create LRC files from plain text lyrics
    - Optional audio playback with pygame (install separately)
    - Press `SPACE` to mark timestamps for each line
    - Press `Q` to quit and save progress
    - Works without audio for manual timing

## API Reference

### Main Functions

#### `get_lyrics(song_name, artist_name, album_name=None, duration=None, none_char="♪")`

Fetches lyrics for a song by artist name and song name.

- **Parameters**:
    - `song_name`: Name of the song
    - `artist_name`: Name of the artist
    - `album_name`: (Optional) Album name to improve search accuracy
    - `duration`: (Optional) Duration of the song in seconds
    - `none_char`: Character to use for empty lines in synchronized lyrics
- **Returns**: A `Lyrics` object if found, `None` otherwise

#### `get_lyrics_by_id(lyrics_id, none_char="♪")`

Fetches lyrics for a song by its LRCLib ID.

- **Parameters**:
    - `lyrics_id`: The LRCLib ID of the song
    - `none_char`: Character to use for empty lines in synchronized lyrics
- **Returns**: A `Lyrics` object if found, `None` otherwise

#### `search_lyrics(q=None, song_name=None, artist_name=None, album_name=None, none_char="♪")`

Searches for lyrics by query or song/artist information.

- **Parameters**:
    - `q`: General search query string
    - `song_name`: Optional song name for searching
    - `artist_name`: Optional artist name for searching
    - `album_name`: Optional album name for better matching
    - `none_char`: Character to use for empty lines in synchronized lyrics
- **Returns**: A list of `Lyrics` objects if found, `None` otherwise

#### `to_plain_lyrics(lyrics, none_char="♪")`

Converts a `Lyrics` object or lyrics dictionary to plain text.

- **Parameters**:
    - `lyrics`: A `Lyrics` object or dictionary containing lyrics data
    - `none_char`: Character to use for empty lines
- **Returns**: Plain text lyrics as a string

#### `request_challenge()`

Requests a cryptographic challenge from the API for generating a publish token.

- **Returns**: A tuple containing `(prefix, target)` for the proof-of-work challenge
- **Raises**: `LyriqError` if the API returns an error

#### `verify_nonce(result_bytes, target_bytes)`

Verifies if a nonce satisfies the target requirement for the proof-of-work challenge.

- **Parameters**:
    - `result_bytes`: The hashed result as bytes
    - `target_bytes`: The target as bytes
- **Returns**: `True` if the nonce satisfies the target, `False` otherwise

#### `generate_publish_token(prefix, target)`

Generates a valid publish token by solving a proof-of-work challenge.

- **Parameters**:
    - `prefix`: The prefix string provided by the challenge
    - `target`: The target string in hexadecimal format provided by the challenge
- **Returns**: A valid publish token in the format `{prefix}:{nonce}`
- **Raises**: `LyriqError` if there is an error with the token generation

#### `publish_lyrics(track_name, artist_name, album_name, duration, plain_lyrics="", synced_lyrics="")`

Publishes lyrics to the LRCLIB API.

- **Parameters**:
    - `track_name`: Name of the track
    - `artist_name`: Name of the artist
    - `album_name`: Name of the album
    - `duration`: Duration of the track in seconds
    - `plain_lyrics`: Plain text lyrics (optional)
    - `synced_lyrics`: Synchronized lyrics (optional)
- **Returns**: `True` if the publish was successful, `False` otherwise
- **Raises**: `LyriqError` if there is an error publishing the lyrics

#### `get_database_dumps()`

Fetches the list of available database dumps from the LRCLib database dumps API.

- **Returns**: A list of `DatabaseDump` objects if successful, `None` otherwise
- **Raises**: `LyriqError` if there is an error fetching the database dumps

#### `get_latest_database_dump()`

Gets the latest database dump from the LRCLib database dumps API.

- **Returns**: The latest `DatabaseDump` object if found, `None` otherwise

#### `download_database_dump(dump, download_path=None, progress_callback=None)`

Downloads a database dump file.

- **Parameters**:
    - `dump`: The `DatabaseDump` object to download
    - `download_path`: Optional path to save the file. If not provided, saves to cache directory
    - `progress_callback`: Optional callback function to track download progress. Called with `(bytes_downloaded, total_bytes)`
- **Returns**: The path to the downloaded file if successful, `None` otherwise
- **Raises**: `LyriqError` if there is an error downloading the file

### Lyrics Class

#### Properties

- `lyrics`: Dictionary mapping timestamps to lyric lines
- `synced_lyrics`: Raw synchronized lyrics string
- `plain_lyrics`: Plain lyrics string
- `id`: LRCLib ID of the song
- `name`: Name of the song
- `track_name`: Name of the track
- `artist_name`: Name of the artist
- `album_name`: Name of the album
- `duration`: Duration of the song in seconds
- `instrumental`: Whether the song is instrumental (True/False)

#### Methods

##### `from_dict(data, none_char="♪")`

Create a `Lyrics` instance from a dictionary.

- **Parameters**:
    - `data`: Raw lyrics data dictionary from the API
    - `none_char`: Character to use for empty lines
- **Returns**: A new `Lyrics` instance

##### `to_dict()`

Convert the `Lyrics` instance to a dictionary.

- **Returns**: Dictionary representation of the lyrics

##### `to_plain_string(none_char=None)`

Convert the lyrics to a plain string representation.

- **Parameters**:
    - `none_char`: Character to use for empty lines (optional)
- **Returns**: Plain string representation of lyrics or None if empty
- **Raises**: `EmptyLyricsError` if lyrics are empty

##### `to_plain_file(file_path, none_char=None)`

Write the lyrics to a plain text file.

- **Parameters**:
    - `file_path`: Path to the output file
    - `none_char`: Character to use for empty lines (optional)
- **Raises**: `EmptyLyricsError` if lyrics are empty

##### `to_lrc_string()`

Convert the lyrics to LRC format string.

- **Returns**: LRC format string with metadata and timestamps

##### `to_lrc_file(file_path)`

Write the lyrics to a LRC file.

- **Parameters**:
    - `file_path`: Path to the output file

##### `from_lrc_string(lrc_string, none_char="♪")`

Create a `Lyrics` instance from a LRC format string.

- **Parameters**:
    - `lrc_string`: LRC format string with metadata and timestamps
    - `none_char`: Character to use for empty lines
- **Returns**: A new `Lyrics` instance

##### `from_lrc_file(file_path, none_char="♪")`

Read lyrics from a LRC file.

- **Parameters**:
    - `file_path`: Path to the LRC file
    - `none_char`: Character to use for empty lines
- **Returns**: A new `Lyrics` instance

##### `to_json_file(file_path)`

Write the lyrics to a JSON file.

- **Parameters**:
    - `file_path`: Path to the output file

##### `from_json_file(file_path, none_char="♪")`

Read lyrics from a JSON file.

- **Parameters**:
    - `file_path`: Path to the JSON file
    - `none_char`: Character to use for empty lines
- **Returns**: A new `Lyrics` instance

### DatabaseDump Class

#### Properties

- `storage_class`: Storage class of the dump file (e.g., "Standard")
- `uploaded`: Upload datetime as a `datetime` object
- `checksums`: Dictionary of checksums for the file
- `http_etag`: HTTP ETag header value
- `etag`: ETag value
- `size`: Size of the dump file in bytes
- `version`: Version identifier of the dump
- `key`: Key/filename of the dump file
- `filename`: Extracted filename from the key (property)
- `download_url`: Full download URL for the dump (property)

#### Methods

##### `from_dict(data)`

Create a `DatabaseDump` instance from a dictionary.

- **Parameters**:
    - `data`: Raw database dump data dictionary from the API
- **Returns**: A new `DatabaseDump` instance

## Examples

See the examples directory for practical usage examples:

- `examples/basic_usage.py` - Basic usage of the library
- `examples/fetch_by_id.py` - Fetching lyrics by ID
- `examples/search_lyrics.py` - Searching for lyrics
- `examples/synced_lyrics.py` - Working with synchronized lyrics
- `examples/format_conversion.py` - Converting between formats
- `examples/publishing_lyrics.py` - Publishing lyrics to the API
- `examples/database_dumps.py` - Working with database dumps

## Development

### Project Structure

```
lyriq/
├── .github/
│   ├── workflows/
│   │   ├── python-tests.yml
│   │   └── python-publish.yml
├── environment.yml      # Environment file
├── examples/            # Example files demonstrating usage
│   ├── basic_usage.py
│   ├── fetch_by_id.py
│   ├── search_lyrics.py
│   ├── synced_lyrics.py
│   ├── format_conversion.py
│   └── publishing_lyrics.py
├── lyriq/
│   ├── __init__.py      # Package exports
│   ├── __main__.py      # CLI entry point
│   ├── lyriq.py         # Core functionality
│   ├── cli.py           # Command line interface
│   └── cache/           # Auto-generated cache directory
│       ├── lyrics.json  # Lyrics cache
│       └── search.json  # Search cache
├── tests/
│   ├── __init__.py
│   └── test_lyriq.py    # Test suite
├── pyproject.toml       # Project configuration
├── setup.py             # Setup script
├── main.py              # Example usage
├── README.md            # This file
├── LICENSE              # License file
└── .gitignore           # Git ignore file
```

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run the test suite
pytest

# Run with coverage report
pytest --cov=lyriq --cov-report=term-missing
```

### Adding Features

1. Make changes to the core functionality in `lyriq.py`
2. Add appropriate tests in `test_lyriq.py`
3. Update documentation in docstrings and README.md
4. Run tests to ensure everything works

## Technical Details

### API

Lyriq uses the LRCLib API (https://lrclib.net/api) to fetch lyrics data. The API provides both synchronized and plain lyrics.

### Caching

To reduce API calls and improve performance, Lyriq caches all retrieved lyrics in JSON files located in the cache directory:

```
<package_location>/cache/
```

The cache is thread-safe and automatically writes to disk when new lyrics are added.

### Synchronized Lyrics Format

Synchronized lyrics are stored in LRC format with timestamps in the format `[MM:SS.ms]`. The CLI tool interprets these timestamps to display the lyrics at the right moment during playback.

## License

Copyright 2025 TN3W

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
