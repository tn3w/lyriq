#!/usr/bin/env python3
"""
Basic usage example for Lyriq library.

This example demonstrates how to fetch lyrics for a song and display basic information.
"""

from typing import Optional
from lyriq import Lyrics, get_lyrics


def main() -> None:
    """
    Basic usage example for Lyriq library.

    This example demonstrates how to fetch lyrics for a song and display basic information.
    """
    # 1. Fetch lyrics using song name and artist name
    lyrics = get_lyrics("Circles", "Post Malone")
    display_lyrics(lyrics)

    # 2. Fetch including album name
    lyrics = get_lyrics("Circles", "Post Malone", "Hollywood's Bleeding")
    display_lyrics(lyrics)

    # 3. Fetch including duration
    lyrics = get_lyrics("Circles", "Post Malone", duration=215)
    display_lyrics(lyrics)


def display_lyrics(lyrics: Optional[Lyrics]) -> None:
    """
    Display lyrics information.
    """
    if not lyrics:
        print("No lyrics found")
        return

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
    print("\nSynchronized Lyrics Sample (first 5 lines):")
    print("-" * 40)
    for i, (timestamp, line) in enumerate(sorted(lyrics.lyrics.items())):
        if i >= 5:
            break
        print(f"[{timestamp}] {line}")

    print("...")
    print("-" * 40)


if __name__ == "__main__":
    main()
