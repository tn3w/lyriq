#!/usr/bin/env python3
"""
Example for working with synchronized lyrics in Lyriq.

This example demonstrates how to work with the synchronized lyrics format.
"""

import time
import sys
from lyriq import get_lyrics


def main() -> None:
    """
    Working with synchronized lyrics example for Lyriq library.

    This example demonstrates how to work with the synchronized lyrics format.
    """

    # Get lyrics for a song with synchronized lyrics
    lyrics = get_lyrics("Circles", "Post Malone")

    if not lyrics:
        print("No lyrics found.")
        sys.exit(1)

    # Check if we have synchronized lyrics
    if not lyrics.synced_lyrics:
        print("No synchronized lyrics available for this song.")
        sys.exit(1)

    print(
        f"Found synchronized lyrics for '{lyrics.track_name}' by {lyrics.artist_name}"
    )

    # Get timestamps and lyrics sorted by time
    timed_lyrics = []
    for timestamp, line in lyrics.lyrics.items():
        if ":" in timestamp:
            minutes, seconds = timestamp.split(":")
            total_seconds = float(minutes) * 60 + float(seconds)
            timed_lyrics.append((total_seconds, line))

    timed_lyrics.sort()  # Sort by timestamp

    # Option 1: Display all synchronized lyrics with timestamps
    print("\nOption 1: All synchronized lyrics:")
    print("-" * 40)
    for time_sec, line in timed_lyrics:
        minutes = int(time_sec // 60)
        seconds = time_sec % 60
        print(f"[{minutes:02d}:{seconds:05.2f}] {line}")

    # Option 2: Simulate playback (limited to first 5 lines, with 1-second intervals)
    print("\nOption 2: Simulated playback (first 5 lines with 1-second intervals):")
    print("-" * 40)
    print("Starting playback...")

    last_time = 0
    for i, (time_sec, line) in enumerate(timed_lyrics):
        if i >= 5:  # Limit to first 5 lines
            break

        # Calculate time difference for simulation
        if i > 0:
            wait_time = min(1.0, time_sec - last_time)  # Cap at 1 second for demo
            time.sleep(wait_time)

        minutes = int(time_sec // 60)
        seconds = time_sec % 60
        print(f"[{minutes:02d}:{seconds:05.2f}] {line}")
        last_time = time_sec

    print("... (playback stopped)")


if __name__ == "__main__":
    main()
