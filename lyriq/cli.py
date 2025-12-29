#!/usr/bin/env python
"""
CLI tool for the lyriq package.
This tool allows fetching and displaying lyrics with synchronized playback.
"""

import argparse
import json
import os
import sys
import threading
import time
from json import JSONDecodeError
from typing import Dict, List, Optional

from . import (
    Lyrics,
    DatabaseDump,
    __version__,
    get_lyrics,
    get_lyrics_by_id,
    search_lyrics,
    get_database_dumps,
    download_database_dump,
    publish_lyrics,
)

try:
    import tty
    import termios

    def unix_get_keypress() -> str:
        """
        Get a single keypress from the terminal.

        Returns:
            A string representing the pressed key.
        """
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    get_keypress = unix_get_keypress

except ImportError:
    import msvcrt

    def windows_get_keypress() -> str:
        """
        Get a single keypress from the terminal.

        Returns:
            A string representing the pressed key.
        """
        return msvcrt.getch().decode("utf-8")

    get_keypress = windows_get_keypress


class Colors:
    """
    ANSI color codes for the terminal.
    """

    RESET = "\033[0m" if sys.stdout.isatty() else ""
    BOLD = "\033[1m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


def clear_screen() -> None:
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def display_track_info(lyrics: Lyrics) -> None:
    """
    Display track information with highlighted differences.

    Args:
        lyrics: Lyrics object
    """
    print(f"\n{Colors.BOLD}Track Information:{Colors.RESET}")
    print(f"ID: {lyrics.id}")
    print(f"Name: {lyrics.name}")
    print(f"Track: {lyrics.track_name}")
    print(f"Artist: {lyrics.artist_name}")

    if lyrics.album_name:
        print(f"Album: {lyrics.album_name}")

    duration_min = int(lyrics.duration // 60)
    duration_sec = int(lyrics.duration % 60)
    print(f"Duration: {duration_min}:{duration_sec:02d}")
    print(f"Instrumental: {'Yes' if lyrics.instrumental else 'No'}")
    print()


def parse_timestamp(timestamp: str) -> float:
    """
    Parse a timestamp string to seconds.

    Args:
        timestamp: Timestamp string in format "MM:SS.ms" or "SS.ms"

    Returns:
        Seconds as float
    """
    if ":" in timestamp:
        mins, secs = timestamp.split(":")
        return float(mins) * 60 + float(secs)
    return float(timestamp)


def format_time(seconds: float) -> str:
    """
    Format seconds to MM:SS.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted time string
    """
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"


def display_lyrics(
    lyrics_dict: Dict[str, str], current_time: float, display_height: int = 5
) -> List[str]:
    """
    Display lyrics with the current line highlighted.

    Args:
        lyrics_dict: Dictionary of timestamps to lyrics lines
        current_time: Current playback time in seconds
        display_height: Number of lines to display

    Returns:
        List of displayed lines (for testing)
    """
    sorted_lyrics = [
        (parse_timestamp(ts), ts, text) for ts, text in lyrics_dict.items()
    ]
    sorted_lyrics.sort()

    current_idx = 0
    for i, (time_sec, _, _) in enumerate(sorted_lyrics):
        if time_sec > current_time:
            break
        current_idx = i

    half_height = display_height // 2
    start_idx = max(0, current_idx - half_height)
    end_idx = min(len(sorted_lyrics), start_idx + display_height)

    if end_idx == len(sorted_lyrics) and len(sorted_lyrics) > display_height:
        start_idx = len(sorted_lyrics) - display_height

    displayed_lines = []

    for i in range(start_idx, end_idx):
        time_sec, _, line = sorted_lyrics[i]

        if i == current_idx:
            formatted_line = (
                f"{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD}▶ {line}{Colors.RESET}"
            )
        else:
            formatted_line = f"{Colors.BRIGHT_CYAN}{line}{Colors.RESET}"

        print(formatted_line)
        displayed_lines.append(formatted_line)

    return displayed_lines


def play_synced_lyrics(
    lyrics: Lyrics, control_char: str = " ", no_info: bool = False
) -> None:
    """
    Play synchronized lyrics.

    Args:
        lyrics: Lyrics object with synchronized lyrics
        control_char: Character to press for advancing playback
        no_info: Whether to hide track information
    """
    if not lyrics.lyrics:
        print("No lyrics available for playback.")
        return

    timestamps = [(parse_timestamp(ts), ts, text) for ts, text in lyrics.lyrics.items()]
    timestamps.sort()

    playing = False
    current_time = 0.0
    start_time = None
    last_update = 0.0
    repeat = True

    event = threading.Event()

    def input_thread(event: threading.Event) -> None:
        nonlocal playing, current_time, start_time, repeat

        while not event.is_set():
            char = get_keypress()

            if char == "q":
                event.set()
            elif char == control_char:
                playing = not playing
                if playing:
                    start_time = time.time() - current_time
            elif char == "\x1b":
                next_char = get_keypress()
                if next_char == "[":
                    arrow = get_keypress()
                    if arrow == "D":
                        current_time = max(0, current_time - 1)
                        if playing:
                            start_time = time.time() - current_time
                    elif arrow == "C":
                        current_time += 1
                        if playing:
                            start_time = time.time() - current_time
            elif char == "r":
                repeat = not repeat

    input_thread_handle = threading.Thread(
        target=input_thread, args=(event,), daemon=True
    )
    input_thread_handle.start()

    try:
        while not event.is_set():
            if playing and start_time is not None:
                current_time = time.time() - start_time

            if time.time() - last_update > 0.5:
                clear_screen()
                if not no_info:
                    display_track_info(lyrics)
                print(
                    f"Press {Colors.YELLOW}'{'Space' if control_char == ' ' else control_char}'"
                    f"{Colors.RESET} to start/pause playback, {Colors.YELLOW}'r'{Colors.RESET}"
                    f" to toggle repeat, {Colors.YELLOW}'q'{Colors.RESET} to quit."
                )
                print(
                    f"Use {Colors.YELLOW}arrow keys ← →{Colors.RESET} to rewind/fast-forward 1s\n"
                )
                if current_time > lyrics.duration:
                    playing = repeat
                    start_time = None if not repeat else time.time()
                    current_time = 0.0
                print(
                    f"{Colors.BOLD}{'▶ PLAYING' if playing else '❚❚ PAUSED'}{Colors.RESET}"
                    f"{' REPEAT' if repeat else ''} {Colors.BRIGHT_BLACK}["
                    f"{format_time(current_time)}/{format_time(lyrics.duration)}]{Colors.RESET}"
                )
                display_lyrics(lyrics.lyrics, current_time)
                last_update = time.time()

            time.sleep(0.5)

    except KeyboardInterrupt:
        event.set()
    finally:
        clear_screen()


def display_plain_lyrics(lyrics: Dict[str, str]) -> None:
    """
    Display plain lyrics.

    Args:
        lyrics: Dictionary of timestamps to lyrics lines
    """
    sorted_lyrics = [(parse_timestamp(ts), text) for ts, text in lyrics.items()]
    sorted_lyrics.sort()

    for _, text in sorted_lyrics:
        print(f"{text}")


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def display_database_dumps(dumps: List[DatabaseDump]) -> Optional[DatabaseDump]:
    """
    Display database dumps in an interactive UI with arrow key navigation.

    Args:
        dumps: List of DatabaseDump objects

    Returns:
        Selected DatabaseDump object or None if canceled
    """
    if not dumps or len(dumps) == 0:
        print(f"{Colors.RED}No database dumps found.{Colors.RESET}")
        return None

    selected_idx = 0
    start_idx = 0
    page_size = 5
    max_idx = len(dumps) - 1

    while True:
        clear_screen()
        print(f"{Colors.BOLD}Available Database Dumps:{Colors.RESET}")
        print(
            f"Found {len(dumps)} dumps. Use {Colors.YELLOW}↑/↓{Colors.RESET}"
            f" arrows to navigate, {Colors.YELLOW}'Enter'{Colors.RESET} to download, "
            f"or {Colors.YELLOW}'1-9'{Colors.RESET} to choose directly."
        )
        print(f"Press {Colors.YELLOW}'q'{Colors.RESET} to quit.\n")

        if selected_idx >= start_idx + page_size:
            start_idx = min(selected_idx - page_size + 1, max_idx - page_size + 1)
        elif selected_idx < start_idx:
            start_idx = max(0, selected_idx)

        if start_idx > 0:
            print(f"{Colors.BRIGHT_BLACK}   ↑ more dumps above ↑{Colors.RESET}")

        end_idx = min(start_idx + page_size, len(dumps))

        for i in range(start_idx, end_idx):
            dump = dumps[i]

            size_str = format_file_size(dump.size)
            date_str = dump.uploaded.strftime("%Y-%m-%d %H:%M UTC")

            if i == selected_idx:
                selector = (
                    f"{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD}[{i+1}]{Colors.RESET} "
                )
            else:
                selector = f"{Colors.BRIGHT_CYAN}[{i+1}]{Colors.RESET} "

            print(f"{selector}{dump.filename}")
            print(f"     Size: {size_str} | Uploaded: {date_str}")
            if i < end_idx - 1:
                print()

        if end_idx < len(dumps):
            print(f"\n{Colors.BRIGHT_BLACK}   ↓ more dumps below ↓{Colors.RESET}")

        key = get_keypress()

        if key == "q":
            return None
        if key in ("\r", "\n"):
            return dumps[selected_idx]
        if key in "123456789":
            idx = int(key) - 1
            if 0 <= idx < len(dumps):
                return dumps[idx]
        if key == "\x1b":
            next_char = get_keypress()
            if next_char == "[":
                arrow = get_keypress()
                if arrow == "A":
                    selected_idx = max(0, selected_idx - 1)
                elif arrow == "B":
                    selected_idx = min(max_idx, selected_idx + 1)


def download_dump_with_progress(
    dump: DatabaseDump, download_path: Optional[str] = None
) -> bool:
    """
    Download a database dump with progress display.

    Args:
        dump: DatabaseDump object to download
        download_path: Optional custom download path

    Returns:
        True if download successful, False otherwise
    """
    print(f"\n{Colors.BOLD}Downloading {dump.filename}...{Colors.RESET}")
    print(f"Size: {format_file_size(dump.size)}")
    print(f"URL: {dump.download_url}")

    if download_path:
        print(f"Destination: {download_path}")
    else:
        print("Destination: Cache directory")

    print(f"\n{Colors.YELLOW}Press Ctrl+C to cancel download{Colors.RESET}\n")

    progress_bar_width = 50
    last_progress = 0

    def progress_callback(downloaded: int, total: int):
        nonlocal last_progress

        if total > 0:
            percent = (downloaded / total) * 100
            filled_width = int((downloaded / total) * progress_bar_width)
        else:
            percent = 0
            filled_width = 0

        if int(percent) > last_progress:
            status_bar = "█" * filled_width + "░" * (progress_bar_width - filled_width)
            downloaded_str = format_file_size(downloaded)
            total_str = format_file_size(total) if total > 0 else "Unknown"

            print(
                f"\r{Colors.GREEN}[{status_bar}]{Colors.RESET}"
                f" {percent:5.1f}% ({downloaded_str}/{total_str})",
                end="",
                flush=True,
            )
            last_progress = int(percent)

    try:
        result_path = download_database_dump(dump, download_path, progress_callback)

        if result_path:
            print(f"\n\n{Colors.GREEN}✓ Download completed successfully!{Colors.RESET}")
            print(f"File saved to: {result_path}")
            return True
        else:
            print(f"\n\n{Colors.RED}✗ Download failed.{Colors.RESET}")
            return False

    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Download canceled by user.{Colors.RESET}")
        return False
    except Exception as e:
        print(f"\n\n{Colors.RED}✗ Download failed: {e}{Colors.RESET}")
        return False


def handle_database_dumps(dumps_index: Optional[int] = None) -> int:
    """
    Handle the database dumps CLI functionality.

    Args:
        dumps_index: Optional index to select dump directly (1-based)

    Returns:
        Exit code (0 for success, 1 for error)
    """
    print(f"{Colors.BOLD}Fetching database dumps...{Colors.RESET}")

    dumps = get_database_dumps()
    if not dumps:
        print(
            f"{Colors.RED}Failed to fetch database dumps or no dumps available.{Colors.RESET}"
        )
        return 1

    dumps.sort(key=lambda x: x.uploaded, reverse=True)

    if dumps_index is not None:
        if 1 <= dumps_index <= len(dumps):
            selected_dump = dumps[dumps_index - 1]
            print(
                f"{Colors.BOLD}Selected dump by index:{Colors.RESET} {selected_dump.filename}"
            )
        else:
            print(
                f"{Colors.RED}Error: Dump index {dumps_index}"
                f" out of range (1-{len(dumps)}).{Colors.RESET}"
            )
            return 1
    else:
        selected_dump = display_database_dumps(dumps)
        if not selected_dump:
            print("No dump selected.")
            return 0

    print(f"Size: {format_file_size(selected_dump.size)}")
    print(f"Uploaded: {selected_dump.uploaded.strftime('%Y-%m-%d %H:%M UTC')}")

    while not dumps_index:
        response = input("\nDownload this dump? (y/N): ").strip().lower()
        if response in ["y", "yes"]:
            break
        elif response in ["n", "no", ""]:
            print("Download canceled.")
            return 0
        else:
            print("Please enter 'y' for yes or 'n' for no.")

    custom_path = None
    if not dumps_index:
        custom_path = input("Custom download path (press Enter for default): ").strip()
    download_path = custom_path if custom_path else None

    success = download_dump_with_progress(selected_dump, download_path)
    return 0 if success else 1


def display_search_results(
    results: List[Lyrics], search_query: str
) -> Optional[Lyrics]:
    """
    Display search results in an interactive UI with arrow key navigation.

    Args:
        results: List of Lyrics objects from search
        search_query: The original search query

    Returns:
        Selected Lyrics object or None if canceled
    """
    if not results or len(results) == 0:
        print(f"{Colors.RED}No results found for '{search_query}'.{Colors.RESET}")
        return None

    selected_idx = 0
    start_idx = 0
    page_size = 4
    max_idx = len(results) - 1

    while True:
        clear_screen()
        print(f"{Colors.BOLD}Search results for '{search_query}':{Colors.RESET}")
        print(
            f"Found {len(results)} results. Use {Colors.YELLOW}↑/↓{Colors.RESET}"
            f" arrows to navigate, {Colors.YELLOW}'Enter'{Colors.RESET} to select, "
            f"or {Colors.YELLOW}'1-9'{Colors.RESET} to choose directly."
        )
        print(f"Press {Colors.YELLOW}'q'{Colors.RESET} to quit.\n")

        if selected_idx >= start_idx + page_size:
            start_idx = min(selected_idx - page_size + 1, max_idx - page_size + 1)
        elif selected_idx < start_idx:
            start_idx = max(0, selected_idx)

        if start_idx > 0:
            print(f"{Colors.BRIGHT_BLACK}   ↑ more results above ↑{Colors.RESET}")

        end_idx = min(start_idx + page_size, len(results))

        for i in range(start_idx, end_idx):
            result = results[i]

            album_info = f" - {result.album_name}" if result.album_name else ""
            duration = f"{int(result.duration // 60)}:{int(result.duration % 60):02d}"
            has_synced = bool(result.synced_lyrics and result.synced_lyrics.strip())
            sync_indicator = (
                f"{Colors.GREEN}[synced]{Colors.RESET}"
                if has_synced
                else f"{Colors.YELLOW}[plain]{Colors.RESET}"
            )

            if i == selected_idx:
                selector = (
                    f"{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD}[{i+1}]{Colors.RESET} "
                )
            else:
                selector = f"{Colors.BRIGHT_CYAN}[{i+1}]{Colors.RESET} "

            print(
                f"{selector}{result.track_name} - {result.artist_name}{album_info} "
                f"({duration}) {sync_indicator}"
            )

        if end_idx < len(results):
            print(f"{Colors.BRIGHT_BLACK}   ↓ more results below ↓{Colors.RESET}")

        key = get_keypress()

        if key == "q":
            return None
        if key in ("\r", "\n"):
            return results[selected_idx]
        if key in "123456789":
            idx = int(key) - 1
            if 0 <= idx < len(results):
                return results[idx]
        if key == "\x1b":
            next_char = get_keypress()
            if next_char == "[":
                arrow = get_keypress()
                if arrow == "A":
                    selected_idx = max(0, selected_idx - 1)
                elif arrow == "B":
                    selected_idx = min(max_idx, selected_idx + 1)


def main() -> int:
    """
    Main function for the CLI tool.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(description="Fetch and display song lyrics")
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="show version message and exit",
    )
    parser.add_argument("--id", type=int, default=None, help="ID of the song")
    parser.add_argument(
        "song_name",
        nargs="?",
        default=None,
        help="Name of the song (optional)",
    )
    parser.add_argument(
        "artist_name",
        nargs="?",
        default=None,
        help="Name of the artist (optional)",
    )
    parser.add_argument(
        "album_name", nargs="?", default=None, help="Name of the album (optional)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        nargs="?",
        default=None,
        help="Duration of the song (optional)",
    )
    parser.add_argument(
        "--search",
        nargs="?",
        const=True,
        default=False,
        help="Search for lyrics by song name and artist name. Optionally provide a search query.",
    )
    parser.add_argument(
        "--search-index",
        type=int,
        default=None,
        help="Select search result at specified index directly (1-based)",
    )
    parser.add_argument(
        "--none-char", default="♪", help="Character to use for empty lines"
    )
    parser.add_argument(
        "--no-info", action="store_true", help="Do not display track information"
    )
    parser.add_argument(
        "--plain",
        nargs="?",
        const="plain",
        default=None,
        help="Display only plain lyrics (default), or specify 'lrc' or 'json' for other formats",
        choices=["plain", "lrc", "json"],
    )
    parser.add_argument("--file", default=None, help="File to save lyrics to and exit")
    parser.add_argument(
        "--file-format",
        default="plain",
        help="Format to save lyrics to",
        choices=["plain", "lrc", "json"],
    )
    parser.add_argument(
        "--load",
        default=None,
        help="Load lyrics from file",
    )
    parser.add_argument(
        "--dumps",
        action="store_true",
        help="List and download database dumps",
    )
    parser.add_argument(
        "--dumps-index",
        type=int,
        default=None,
        help="Select database dump at specified index directly (1-based)",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish lyrics to the database. Requires --load with song_name and artist_name",
    )

    args = parser.parse_args()

    if args.dumps:
        return handle_database_dumps(args.dumps_index)

    if args.publish:
        if not args.load:
            print(
                f"{Colors.RED}Error: --publish requires --load to specify a lyrics file.{Colors.RESET}"
            )
            return 1
        if not args.song_name or not args.artist_name or not args.album_name:
            print(
                f"{Colors.RED}Error: --publish requires song_name, artist_name, and album_name.{Colors.RESET}"
            )
            return 1

        if args.load.endswith(".json"):
            try:
                lyrics = Lyrics.from_json_file(args.load, args.none_char)
            except JSONDecodeError:
                print(
                    f"{Colors.RED}Error: Invalid JSON file: {args.load}.{Colors.RESET}"
                )
                return 1
        else:
            lyrics = Lyrics.from_lrc_file(args.load, args.none_char)

        track_name = args.song_name
        artist_name = args.artist_name
        album_name = args.album_name
        duration = args.duration or lyrics.duration or 0

        if duration <= 0:
            print(
                f"{Colors.RED}Error: Duration is required. Use --duration or include it in the file.{Colors.RESET}"
            )
            return 1

        print(f"{Colors.BOLD}Publishing lyrics...{Colors.RESET}")
        print(f"Track: {track_name}")
        print(f"Artist: {artist_name}")
        print(f"Album: {album_name}")
        print(f"Duration: {duration}s")

        try:
            success = publish_lyrics(
                track_name=track_name,
                artist_name=artist_name,
                album_name=album_name,
                duration=duration,
                plain_lyrics=lyrics.plain_lyrics,
                synced_lyrics=lyrics.synced_lyrics,
            )
            if success:
                print(f"{Colors.GREEN}✓ Lyrics published successfully!{Colors.RESET}")
                return 0
            else:
                print(f"{Colors.RED}✗ Failed to publish lyrics.{Colors.RESET}")
                return 1
        except Exception as e:
            print(f"{Colors.RED}✗ Error publishing lyrics: {e}{Colors.RESET}")
            return 1

    if args.search is not False:
        search_query = None
        search_results = None

        if isinstance(args.search, str):
            search_query = args.search
            search_results = search_lyrics(q=search_query, none_char=args.none_char)
        elif args.song_name and args.artist_name:
            search_query = f"{args.song_name} {args.artist_name}"
            search_results = search_lyrics(
                song_name=args.song_name,
                artist_name=args.artist_name,
                album_name=args.album_name,
                none_char=args.none_char,
            )
        else:
            print(
                f"{Colors.RED}Error: Search requires either a query"
                f"or song and artist names.{Colors.RESET}"
            )
            parser.print_help()
            return 1

        if not search_results:
            print(f"{Colors.RED}No results found for '{search_query}'.{Colors.RESET}")
            return 1

        if args.search_index is not None:
            if 1 <= args.search_index <= len(search_results):
                lyrics = search_results[args.search_index - 1]
            else:
                print(
                    f"{Colors.RED}Error: Search index {args.search_index}"
                    f"out of range (1-{len(search_results)}).{Colors.RESET}"
                )
                return 1
        else:
            lyrics = display_search_results(search_results, search_query)
            if not lyrics:
                return 1

    elif args.id:
        lyrics = get_lyrics_by_id(args.id, args.none_char)
    elif args.load:
        if args.load.endswith(".json"):
            try:
                lyrics = Lyrics.from_json_file(args.load, args.none_char)
            except JSONDecodeError:
                print(
                    f"{Colors.RED}Error: Invalid JSON file: {args.load}.{Colors.RESET}"
                )
                return 1
        else:
            lyrics = Lyrics.from_lrc_file(args.load, args.none_char)
    elif not args.song_name and not args.artist_name:
        print(
            f"{Colors.RED}Error: Song name and artist name are required.{Colors.RESET}"
        )
        parser.print_help()
        return 1
    elif not args.song_name:
        print(f"{Colors.RED}Error: Song name is required.{Colors.RESET}")
        parser.print_help()
        return 1
    elif not args.artist_name:
        print(f"{Colors.RED}Error: Artist name is required.{Colors.RESET}")
        parser.print_help()
        return 1
    else:
        lyrics = get_lyrics(
            args.song_name,
            args.artist_name,
            args.album_name,
            args.duration,
            args.none_char,
        )

    if not lyrics:
        print(
            f"No lyrics found for {args.id or f'{args.song_name} by {args.artist_name}'}"
        )
        return 1

    if args.file:
        if args.file_format == "plain":
            lyrics.to_plain_file(args.file)
        elif args.file_format == "lrc":
            lyrics.to_lrc_file(args.file)
        elif args.file_format == "json":
            lyrics.to_json_file(args.file)
        print(
            f"{Colors.GREEN}{args.file_format.upper()} lyrics saved to {args.file}{Colors.RESET}"
        )
        return 0

    if not args.no_info:
        display_track_info(lyrics)

    if args.plain == "plain":
        display_plain_lyrics(lyrics.lyrics)
        return 0

    if args.plain == "lrc":
        print(lyrics.to_lrc_string())
        return 0

    if args.plain == "json":
        print(json.dumps(lyrics.to_dict(), indent=2))
        return 0

    has_synced = bool(lyrics.synced_lyrics and lyrics.synced_lyrics.strip())

    if has_synced:
        play_synced_lyrics(lyrics, no_info=args.no_info)
    else:
        print(f"{Colors.YELLOW}Only plain lyrics available.{Colors.RESET}\n")
        display_plain_lyrics(lyrics.lyrics)

    return 0


if __name__ == "__main__":
    sys.exit(main())
