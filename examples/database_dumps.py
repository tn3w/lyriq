#!/usr/bin/env python3
"""
Example demonstrating how to work with LRCLib database dumps.

This example shows how to:
1. Get the list of available database dumps
2. Get the latest database dump
3. Download a database dump with progress tracking
"""

from lyriq import get_database_dumps, get_latest_database_dump, download_database_dump


def progress_callback(downloaded: int, total: int):
    """Progress callback for download tracking."""
    if total > 0:
        percent = (downloaded / total) * 100
        print(
            f"\rDownload progress: {percent:.1f}% ({downloaded:,} / {total:,} bytes)",
            end="",
        )
    else:
        print(f"\rDownloaded: {downloaded:,} bytes", end="")


def main():
    """
    Download LRCLib Database Dumps
    """
    print("LRCLib Database Dumps Example")
    print("=" * 40)

    # Get all available database dumps
    print("\n1. Getting available database dumps...")
    dumps = get_database_dumps()

    if not dumps:
        print("No database dumps found or error occurred.")
        return

    print(f"Found {len(dumps)} database dump(s):")
    for i, dump in enumerate(dumps, 1):
        size_mb = dump.size / (1024 * 1024)
        print(f"  {i}. {dump.filename}")
        print(f"     Size: {size_mb:.1f} MB")
        print(f"     Uploaded: {dump.uploaded}")
        print(f"     Storage Class: {dump.storage_class}")
        print()

    # Get the latest database dump
    print("2. Getting latest database dump...")
    latest_dump = get_latest_database_dump()

    if not latest_dump:
        print("No latest dump found.")
        return

    print(f"Latest dump: {latest_dump.filename}")
    print(f"Size: {latest_dump.size / (1024 * 1024):.1f} MB")
    print(f"Uploaded: {latest_dump.uploaded}")

    # Ask user if they want to download
    response = (
        input("\nDo you want to download the latest dump? (y/N): ").strip().lower()
    )

    if response == "y":
        print(f"\n3. Downloading {latest_dump.filename}...")
        download_path = download_database_dump(
            latest_dump, progress_callback=progress_callback
        )

        if download_path:
            print("\nDownload completed successfully!")
            print(f"File saved to: {download_path}")
        else:
            print("\nDownload failed.")
    else:
        print("Download skipped.")


if __name__ == "__main__":
    main()
