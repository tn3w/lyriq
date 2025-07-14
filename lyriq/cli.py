#!/usr/bin/env python
"""
CLI tool for the lyriq package.
This tool allows fetching and displaying lyrics with synchronized playback.
"""

import argparse
import os
import sys
import threading
import time
from typing import Dict, List

from . import Lyrics, __version__, get_lyrics, get_lyrics_by_id

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
                    f"{Colors.YELLOW}Press '{'Space' if control_char == ' ' else control_char}'"
                    f" to start/pause playback, 'q' to quit, 'r' to toggle repeat{Colors.RESET}"
                )
                print(
                    f"{Colors.YELLOW}Use arrow keys ← → to rewind/fast-forward 1s{Colors.RESET}\n"
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
    parser.add_argument("song_name", nargs="?", default=None, help="Name of the song")
    parser.add_argument(
        "artist_name", nargs="?", default=None, help="Name of the artist"
    )
    parser.add_argument(
        "album-name", nargs="?", default=None, help="Name of the album (optional)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        nargs="?",
        default=None,
        help="Duration of the song (optional)",
    )
    parser.add_argument(
        "--none-char", default="♪", help="Character to use for empty lines"
    )
    parser.add_argument(
        "--no-info", action="store_true", help="Do not display track information"
    )
    parser.add_argument(
        "--plain", action="store_true", help="Display only plain lyrics"
    )
    parser.add_argument("--file", default=None, help="File to save lyrics to and exit")
    parser.add_argument(
        "--file-format",
        default="plain",
        help="Format to save lyrics to",
        choices=["plain", "json"],
    )
    parser.add_argument(
        "--load",
        default=None,
        help="Load lyrics from file",
    )

    args = parser.parse_args()

    if args.id:
        lyrics = get_lyrics_by_id(args.id, args.none_char)
    elif args.load:
        lyrics = Lyrics.from_json_file(args.load, args.none_char)
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
        elif args.file_format == "json":
            lyrics.to_json_file(args.file)
        print(
            f"{Colors.GREEN}{args.file_format.upper()} lyrics saved to {args.file}{Colors.RESET}"
        )
        return 0

    if not args.no_info:
        display_track_info(lyrics)

    if args.plain:
        display_plain_lyrics(lyrics.lyrics)
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
