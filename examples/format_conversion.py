#!/usr/bin/env python3
"""
Example for format conversion and file operations with Lyriq.

This example demonstrates how to:
- Convert between different lyric formats
- Save lyrics to files
- Load lyrics from files
"""

import os
import sys
from lyriq import Lyrics, get_lyrics, to_plain_lyrics


def main() -> None:
    """
    Format conversion and file operations example for Lyriq library.

    This example demonstrates how to:
    - Convert between different lyric formats
    - Save lyrics to files
    - Load lyrics from files
    """
    # Get lyrics
    lyrics = get_lyrics("Circles", "Post Malone")

    if not lyrics:
        print("No lyrics found.")
        sys.exit(1)

    print(f"Found lyrics for '{lyrics.track_name}' by {lyrics.artist_name}")

    # 1. Convert to plain text
    print("\n1. Converting to plain text:")
    print("-" * 40)
    plain = to_plain_lyrics(lyrics)
    print(plain[:200] + "...")  # Show first 200 chars

    # Create a directory for our output files
    os.makedirs("output", exist_ok=True)

    # 2. Save to plain text file
    print("\n2. Saving to plain text file:")
    print("-" * 40)
    plain_file = "output/circles.txt"
    lyrics.to_plain_file(plain_file)
    print(f"Plain lyrics saved to: {plain_file}")

    # 3. Save to JSON file
    print("\n3. Saving to JSON file:")
    print("-" * 40)
    json_file = "output/circles.json"
    lyrics.to_json_file(json_file)
    print(f"JSON lyrics saved to: {json_file}")

    # 4. Load from JSON file
    print("\n4. Loading from JSON file:")
    print("-" * 40)
    # Create an empty lyrics object
    empty_lyrics = Lyrics(
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

    # Load from the saved JSON
    loaded_lyrics = empty_lyrics.from_json_file(json_file)
    print(
        f"Loaded from JSON: {loaded_lyrics.track_name} by {loaded_lyrics.artist_name}"
    )
    print(f"Has synchronized lyrics: {'Yes' if loaded_lyrics.synced_lyrics else 'No'}")
    print(f"Plain lyrics contains {len(loaded_lyrics.plain_lyrics)} characters")

    # 5. Custom empty line character
    print("\n5. Using custom empty line character:")
    print("-" * 40)
    custom_lyrics = get_lyrics("Circles", "Post Malone", none_char="***")
    if custom_lyrics:
        sample = {}
        for timestamp, line in sorted(custom_lyrics.lyrics.items())[:5]:
            sample[timestamp] = line
        print(f"Sample with custom empty line character ('***'): {sample}")


if __name__ == "__main__":
    main()
