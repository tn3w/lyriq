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
from lyriq import Lyrics, get_lyrics

lyrics: Optional[Lyrics] = get_lyrics("Circles", "Post Malone")
if not lyrics:
    print("No lyrics found for 'Circles' by Post Malone")
    sys.exit(0)

print(f"ID: {lyrics.id}")
print(f"Name: {lyrics.name}")
print(f"Track: {lyrics.track_name}")
print(f"Artist: {lyrics.artist_name}")
print(f"Album: {lyrics.album_name}")
print(f"Duration: {lyrics.duration} seconds")
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

## Command Line Interface

The library comes with a command-line interface for quick access to lyrics with synchronized lyrics playback:

```bash
# Basic usage
lyriq "Circles" "Post Malone"

# With album name (optional)
lyriq "Circles" "Post Malone" "Hollywood's Bleeding"

# With duration (optional)
lyriq "Circles" "Post Malone" --duration 210

# Custom character for empty lines
lyriq "Circles" "Post Malone" --none-char "*"

# Display no track information
lyriq "Circles" "Post Malone" --no-info

# Display only plain lyrics
lyriq "Circles" "Post Malone" --plain

# Save lyrics to file and exit
lyriq "Circles" "Post Malone" --file Circles-Post-Malone.txt

# Save lyrics to JSON file and exit
lyriq "Circles" "Post Malone" --file Circles-Post-Malone.json --file-format json

# Load lyrics from file
lyriq --load Circles-Post-Malone.json

# Fetch lyrics by ID
lyriq --id 449
```

### CLI Features

- Display song metadata with colored highlighting of differences
- Synchronized lyrics playback (if available)
- Interactive controls:
    - Press `SPACE` (or custom character): Play/Pause
    - Press `←` / `→` arrows: Rewind/Fast-forward by 5 seconds
    - Press `r`: Toggle repeat
    - Press `q`: Quit

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

#### `to_plain_lyrics(lyrics, none_char="♪")`

Converts a `Lyrics` object or lyrics dictionary to plain text.

- **Parameters**:
    - `lyrics`: A `Lyrics` object or dictionary containing lyrics data
    - `none_char`: Character to use for empty lines
- **Returns**: Plain text lyrics as a string

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

##### `to_plain_file(file_path)`

Write the lyrics to a plain text file.

- **Parameters**:
    - `file_path`: Path to the output file

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

## Examples

### Fetching and Displaying Lyrics

```python
import sys
from lyriq import Lyrics, get_lyrics

lyrics: Optional[Lyrics] = get_lyrics("Circles", "Post Malone")
if not lyrics:
    print("No lyrics found for 'Circles' by Post Malone")
    sys.exit(0)

print(f"ID: {lyrics.id}")
print(f"Name: {lyrics.name}")
print(f"Track: {lyrics.track_name}")
print(f"Artist: {lyrics.artist_name}")
print(f"Album: {lyrics.album_name}")
print(f"Duration: {lyrics.duration} seconds")
print(f"Instrumental: {lyrics.instrumental}")
print("\nPlain Lyrics:")
print("-" * 40)
print(lyrics.plain_lyrics)
print("\nSynchronized Lyrics (timestamp: lyric):")
print("-" * 40)

for timestamp, line in sorted(lyrics.lyrics.items()):
    print(f"[{timestamp}] {line}")

print("-" * 40)
```

### Working with Synchronized Lyrics

```python
import time
from lyriq import get_lyrics

# Get lyrics for a song with synchronized lyrics
lyrics = get_lyrics("Circles", "Post Malone")

if lyrics and lyrics.synced_lyrics:
    # Sort timestamps for playback
    timed_lyrics = [(float(ts.split(":")[0]) * 60 + float(ts.split(":")[1]), line)
                    for ts, line in lyrics.lyrics.items()]
    timed_lyrics.sort()

    # Simple playback simulation
    start_time = time.time()
    current_idx = 0

    print("Press Ctrl+C to stop playback\n")

    try:
        while current_idx < len(timed_lyrics):
            elapsed = time.time() - start_time

            # Display lyrics at the current timestamp
            if current_idx < len(timed_lyrics) and elapsed >= timed_lyrics[current_idx][0]:
                print(f"[{elapsed:.2f}] {timed_lyrics[current_idx][1]}")
                current_idx += 1

            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nPlayback stopped")
```

### Converting Between Formats

```python
from lyriq import Lyrics, get_lyrics, to_plain_lyrics

# Get lyrics
lyrics = get_lyrics("Circles", "Post Malone")

if lyrics:
    # Convert to plain text
    plain = to_plain_lyrics(lyrics)
    print(plain)

    # Save to files
    lyrics.to_plain_file("circles.txt")
    lyrics.to_json_file("circles.json")

    empty_lyrics = Lyrics(
        lyrics={}, synced_lyrics="", plain_lyrics="",
        id="", name="", track_name="", artist_name="",
        album_name="", duration=0, instrumental=False
    )

    loaded = empty_lyrics.from_json_file("circles.json")
    print(f"Loaded: {loaded.track_name} by {loaded.artist_name}")
```

## Development

### Project Structure

```
lyriq/
├── .github/
│   ├── workflows/
│   │   ├── python-tests.yml
│   │   └── python-publish.yml
├── environment.yml      # Environment file
├── lyriq/
│   ├── __init__.py      # Package exports
│   ├── __main__.py      # CLI entry point
│   ├── lyriq.py         # Core functionality
│   ├── cli.py           # Command line interface
│   └── cache.json       # Auto-generated cache file
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

To reduce API calls and improve performance, Lyriq caches all retrieved lyrics in a JSON file located at:

```
<package_location>/cache.json
```

The cache is thread-safe and automatically writes to disk when new lyrics are added.

### Synchronized Lyrics Format

Synchronized lyrics are stored in LRC format with timestamps in the format `[MM:SS.ms]`. The CLI tool interprets these timestamps to display the lyrics at the right moment during playback.

## License

Apache 2.0 License - See LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
