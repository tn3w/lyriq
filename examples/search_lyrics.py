#!/usr/bin/env python3
"""
Example for searching lyrics with Lyriq.

This example demonstrates how to search for lyrics using different methods.
"""

from typing import List, Optional
from lyriq import Lyrics, search_lyrics


def main() -> None:
    """
    Searching lyrics with different methods example for Lyriq library.

    This example demonstrates how to search for lyrics using different methods.
    """
    print("Searching lyrics with different methods:\n")

    # Method 1: Search by general query
    print("Method 1: Search by general query")
    print("-" * 40)
    results = search_lyrics(q="Circles Post Malone")
    display_search_results(results)

    # Method 2: Search by song and artist name
    print("\nMethod 2: Search by song and artist name")
    print("-" * 40)
    results = search_lyrics(song_name="Circles", artist_name="Post Malone")
    display_search_results(results)

    # Method 3: Search with album name for better results
    print("\nMethod 3: Search with album name for better matching")
    print("-" * 40)
    results = search_lyrics(
        song_name="Circles",
        artist_name="Post Malone",
        album_name="Hollywood's Bleeding",
    )
    display_search_results(results)

    # Method 4: Search by song name only
    print("\nMethod 4: Search by song name only")
    print("-" * 40)
    results = search_lyrics(song_name="Circles")
    display_search_results(results, limit=3)  # Limit to 3 results


def display_search_results(results: Optional[List[Lyrics]], limit: int = 5) -> None:
    """
    Display search results with a limit.
    """
    if not results:
        print("No results found.")
        return

    # Display limited number of results
    for i, lyrics in enumerate(results):
        if i >= limit:
            print(f"... {len(results) - limit} more results ...")
            break

        print(f"{i+1}. {lyrics.track_name} by {lyrics.artist_name}")
        print(f"   Album: {lyrics.album_name}")
        print(f"   ID: {lyrics.id}")
        print(f"   Has synced lyrics: {'Yes' if lyrics.synced_lyrics else 'No'}")
        print(f"   Duration: {lyrics.duration} seconds")
        print()


if __name__ == "__main__":
    main()
