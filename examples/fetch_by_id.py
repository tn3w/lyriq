#!/usr/bin/env python3
"""
Example for fetching lyrics by ID with Lyriq.

This example demonstrates how to retrieve lyrics using the LRCLib ID.
"""

from typing import Optional
from lyriq import Lyrics, get_lyrics_by_id


def main() -> None:
    """
    Fetch lyrics by ID example for Lyriq library.

    This example demonstrates how to retrieve lyrics using the LRCLib ID.
    """
    # Fetch lyrics by ID (ID 449 is "Circles" by Post Malone)
    # You can get IDs from search results or from previous lookups
    lyrics_id = "449"
    print(f"Fetching lyrics with ID: {lyrics_id}")

    lyrics = get_lyrics_by_id(lyrics_id)
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
