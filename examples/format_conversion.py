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

    # 2. Get plain string format
    print("\n2. Getting plain string format:")
    print("-" * 40)
    plain_string = lyrics.to_plain_string()
    if plain_string:
        print(f"Plain string contains {len(plain_string)} characters")
        print(plain_string[:100] + "...")  # Show first 100 chars
    else:
        print("No plain string content available")

    # 3. Get LRC string format
    print("\n3. Getting LRC string format:")
    print("-" * 40)
    lrc_string = lyrics.to_lrc_string()
    print(f"LRC string contains {len(lrc_string)} characters")
    print("Sample LRC content:")
    lrc_lines = lrc_string.split("\n")[:8]  # Show first 8 lines
    for line in lrc_lines:
        print(f"  {line}")
    print("  ...")

    # 4. Save to plain text file
    print("\n4. Saving to plain text file:")
    print("-" * 40)
    plain_file = "output/circles.txt"
    lyrics.to_plain_file(plain_file)
    print(f"Plain lyrics saved to: {plain_file}")

    # 5. Save to LRC file
    print("\n5. Saving to LRC file:")
    print("-" * 40)
    lrc_file = "output/circles.lrc"
    lyrics.to_lrc_file(lrc_file)
    print(f"LRC lyrics saved to: {lrc_file}")

    # 6. Save to JSON file
    print("\n6. Saving to JSON file:")
    print("-" * 40)
    json_file = "output/circles.json"
    lyrics.to_json_file(json_file)
    print(f"JSON lyrics saved to: {json_file}")

    # 7. Load from LRC string
    print("\n7. Loading from LRC string:")
    print("-" * 40)
    # Create a simple LRC string
    sample_lrc = """[ti:Sample Song]
[ar:Sample Artist]
[al:Sample Album]
[length:180]

[00:00.00]This is a sample line
[00:05.00]Another sample line
[00:10.00]End of sample"""

    loaded_lrc = Lyrics.from_lrc_string(sample_lrc)
    print(
        f"Loaded from LRC string: {loaded_lrc.track_name} by {loaded_lrc.artist_name}"
    )
    for timestamp, line in sorted(loaded_lrc.lyrics.items())[:3]:
        print(f"  [{timestamp}] {line}")

    # 8. Load from LRC file
    print("\n8. Loading from LRC file:")
    print("-" * 40)
    # Load from the saved LRC
    loaded_from_file = Lyrics.from_lrc_file(lrc_file)
    print(
        f"Loaded from LRC file: {loaded_from_file.track_name} by {loaded_from_file.artist_name}"
    )
    print(f"Contains {len(loaded_from_file.lyrics)} lyric lines")

    # 9. Load from JSON file
    print("\n9. Loading from JSON file:")
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

    # 10. Custom empty line character
    print("\n10. Using custom empty line character:")
    print("-" * 40)
    custom_lyrics = get_lyrics("Circles", "Post Malone", none_char="***")
    if custom_lyrics:
        sample = {}
        for timestamp, line in sorted(custom_lyrics.lyrics.items())[:5]:
            sample[timestamp] = line
        print(f"Sample with custom empty line character ('***'): {sample}")


if __name__ == "__main__":
    main()
