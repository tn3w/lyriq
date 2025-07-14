#!/usr/bin/env python
"""
Example usage of the Lyriq library.

This script demonstrates how to retrieve song lyrics using the Lyriq library.
"""

from typing import Optional

from lyriq import Lyrics, get_lyrics


def display_lyrics(lyrics: Lyrics) -> None:
    """Display both plain and synchronized lyrics."""
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


def main() -> None:
    """Run the example code."""
    # Get lyrics for a popular song
    print("Fetching lyrics for 'Circles' by Post Malone...")
    lyrics: Optional[Lyrics] = get_lyrics("test", "test")

    if lyrics:
        display_lyrics(lyrics)
    else:
        print("No lyrics found for 'Circles' by Post Malone")


if __name__ == "__main__":
    main()
