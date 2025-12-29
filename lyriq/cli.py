#!/usr/bin/env python
"""CLI tool for the lyriq package - fetch and display lyrics with sync playback."""

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

    def get_keypress() -> str:
        """Get a single keypress from the terminal."""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

except ImportError:
    import msvcrt

    def get_keypress() -> str:
        """Get a single keypress from the terminal."""
        return msvcrt.getch().decode("utf-8")


class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m" if sys.stdout.isatty() else ""
    BOLD = "\033[1m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_BLACK = "\033[90m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    BRIGHT_CYAN = "\033[96m"
    BG_BLUE = "\033[44m"


def clear_screen() -> None:
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def format_time(seconds: float) -> str:
    """Format seconds to MM:SS."""
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def parse_timestamp(timestamp: str) -> float:
    """Parse a timestamp string to seconds."""
    if ":" in timestamp:
        mins, secs = timestamp.split(":")
        return float(mins) * 60 + float(secs)
    return float(timestamp)


def format_lrc_timestamp(seconds: float) -> str:
    """Format seconds to LRC timestamp format [MM:SS.ms]."""
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"[{minutes:02d}:{secs:05.2f}]"


def display_track_info(lyrics: Lyrics) -> None:
    """Display track information."""
    print(f"\n{Colors.BOLD}Track Information:{Colors.RESET}")
    print(f"ID: {lyrics.id}")
    print(f"Name: {lyrics.name}")
    print(f"Track: {lyrics.track_name}")
    print(f"Artist: {lyrics.artist_name}")
    if lyrics.album_name:
        print(f"Album: {lyrics.album_name}")
    print(f"Duration: {format_time(lyrics.duration)}")
    print(f"Instrumental: {'Yes' if lyrics.instrumental else 'No'}")
    print()


def display_plain_lyrics(lyrics: Dict[str, str]) -> None:
    """Display plain lyrics."""
    sorted_lyrics = [(parse_timestamp(ts), text) for ts, text in lyrics.items()]
    sorted_lyrics.sort()
    for _, text in sorted_lyrics:
        print(text)


def display_lyrics(
    lyrics_dict: Dict[str, str], current_time: float, display_height: int = 5
) -> List[str]:
    """Display lyrics with the current line highlighted."""
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
        _, _, line = sorted_lyrics[i]
        if i == current_idx:
            formatted = (
                f"{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD}▶ {line}{Colors.RESET}"
            )
        else:
            formatted = f"{Colors.BRIGHT_CYAN}{line}{Colors.RESET}"
        print(formatted)
        displayed_lines.append(formatted)
    return displayed_lines


def handle_playback_input(event: threading.Event, state: dict, control_char: str):
    """Handle keyboard input for playback control."""
    while not event.is_set():
        char = get_keypress()
        if char == "q":
            event.set()
        elif char == control_char:
            state["playing"] = not state["playing"]
            if state["playing"]:
                state["start_time"] = time.time() - state["current_time"]
        elif char == "\x1b":
            next_char = get_keypress()
            if next_char == "[":
                arrow = get_keypress()
                if arrow == "D":
                    state["current_time"] = max(0, state["current_time"] - 1)
                    if state["playing"]:
                        state["start_time"] = time.time() - state["current_time"]
                elif arrow == "C":
                    state["current_time"] += 1
                    if state["playing"]:
                        state["start_time"] = time.time() - state["current_time"]
        elif char == "r":
            state["repeat"] = not state["repeat"]


def play_synced_lyrics(
    lyrics: Lyrics, control_char: str = " ", no_info: bool = False
) -> None:
    """Play synchronized lyrics."""
    if not lyrics.lyrics:
        print("No lyrics available for playback.")
        return

    state = {
        "playing": False,
        "current_time": 0.0,
        "start_time": None,
        "repeat": True,
    }
    event = threading.Event()
    last_update = 0.0

    input_thread = threading.Thread(
        target=handle_playback_input, args=(event, state, control_char), daemon=True
    )
    input_thread.start()

    try:
        while not event.is_set():
            if state["playing"] and state["start_time"] is not None:
                state["current_time"] = time.time() - state["start_time"]

            if time.time() - last_update > 0.5:
                render_playback_screen(lyrics, state, control_char, no_info)
                last_update = time.time()
            time.sleep(0.5)
    except KeyboardInterrupt:
        event.set()
    finally:
        clear_screen()


def render_playback_screen(
    lyrics: Lyrics, state: dict, control_char: str, no_info: bool
) -> None:
    """Render the playback screen."""
    clear_screen()
    if not no_info:
        display_track_info(lyrics)

    key_name = "Space" if control_char == " " else control_char
    print(
        f"Press {Colors.YELLOW}'{key_name}'{Colors.RESET} to start/pause, "
        f"{Colors.YELLOW}'r'{Colors.RESET} to toggle repeat, "
        f"{Colors.YELLOW}'q'{Colors.RESET} to quit."
    )
    print(f"Use {Colors.YELLOW}arrow keys ← →{Colors.RESET} to rewind/fast-forward\n")

    if state["current_time"] > lyrics.duration:
        state["playing"] = state["repeat"]
        state["start_time"] = time.time() if state["repeat"] else None
        state["current_time"] = 0.0

    status = "▶ PLAYING" if state["playing"] else "❚❚ PAUSED"
    repeat_str = " REPEAT" if state["repeat"] else ""
    time_str = f"{format_time(state['current_time'])}/{format_time(lyrics.duration)}"
    print(
        f"{Colors.BOLD}{status}{Colors.RESET}{repeat_str} "
        f"{Colors.BRIGHT_BLACK}[{time_str}]{Colors.RESET}"
    )
    display_lyrics(lyrics.lyrics, state["current_time"])


def display_database_dumps(dumps: List[DatabaseDump]) -> Optional[DatabaseDump]:
    """Display database dumps in an interactive UI with arrow key navigation."""
    if not dumps:
        print(f"{Colors.RED}No database dumps found.{Colors.RESET}")
        return None

    selected_idx = 0
    page_size = 5

    while True:
        clear_screen()
        print(f"{Colors.BOLD}Available Database Dumps:{Colors.RESET}")
        print(
            f"Found {len(dumps)} dumps. Use {Colors.YELLOW}↑/↓{Colors.RESET} to "
            f"navigate, {Colors.YELLOW}'Enter'{Colors.RESET} to download, "
            f"{Colors.YELLOW}'1-9'{Colors.RESET} to choose."
        )
        print(f"Press {Colors.YELLOW}'q'{Colors.RESET} to quit.\n")

        start_idx = calculate_page_start(selected_idx, page_size, len(dumps))
        render_dump_list(dumps, selected_idx, start_idx, page_size)

        result = handle_list_navigation(selected_idx, len(dumps) - 1)
        if result == "quit":
            return None
        if result == "select":
            return dumps[selected_idx]
        if isinstance(result, int) and 0 <= result < len(dumps):
            return dumps[result]
        if isinstance(result, int):
            selected_idx = result


def calculate_page_start(selected: int, page_size: int, total: int) -> int:
    """Calculate the starting index for pagination."""
    if selected >= page_size:
        return min(selected - page_size + 1, total - page_size)
    return 0


def render_dump_list(
    dumps: List[DatabaseDump], selected: int, start: int, page_size: int
) -> None:
    """Render the dump list with pagination indicators."""
    if start > 0:
        print(f"{Colors.BRIGHT_BLACK}   ↑ more dumps above ↑{Colors.RESET}")

    end_idx = min(start + page_size, len(dumps))
    for i in range(start, end_idx):
        dump = dumps[i]
        size_str = format_file_size(dump.size)
        date_str = dump.uploaded.strftime("%Y-%m-%d %H:%M UTC")

        if i == selected:
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


def handle_list_navigation(current: int, max_idx: int):
    """Handle navigation input for list selection."""
    key = get_keypress()
    if key == "q":
        return "quit"
    if key in ("\r", "\n"):
        return "select"
    if key in "123456789":
        return int(key) - 1
    if key == "\x1b":
        next_char = get_keypress()
        if next_char == "[":
            arrow = get_keypress()
            if arrow == "A":
                return max(0, current - 1)
            if arrow == "B":
                return min(max_idx, current + 1)
    return current


def download_dump_with_progress(
    dump: DatabaseDump, download_path: Optional[str] = None
) -> bool:
    """Download a database dump with progress display."""
    print(f"\n{Colors.BOLD}Downloading {dump.filename}...{Colors.RESET}")
    print(f"Size: {format_file_size(dump.size)}")
    print(f"URL: {dump.download_url}")
    print(f"Destination: {download_path or 'Cache directory'}")
    print(f"\n{Colors.YELLOW}Press Ctrl+C to cancel download{Colors.RESET}\n")

    progress_state = {"last_progress": 0}

    def progress_callback(downloaded: int, total: int):
        if total <= 0:
            return
        percent = (downloaded / total) * 100
        if int(percent) <= progress_state["last_progress"]:
            return

        filled = int((downloaded / total) * 50)
        bar = "█" * filled + "░" * (50 - filled)
        print(
            f"\r{Colors.GREEN}[{bar}]{Colors.RESET} {percent:5.1f}% "
            f"({format_file_size(downloaded)}/{format_file_size(total)})",
            end="",
            flush=True,
        )
        progress_state["last_progress"] = int(percent)

    try:
        result_path = download_database_dump(dump, download_path, progress_callback)
        if result_path:
            print(f"\n\n{Colors.GREEN}✓ Download completed!{Colors.RESET}")
            print(f"File saved to: {result_path}")
            return True
        print(f"\n\n{Colors.RED}✗ Download failed.{Colors.RESET}")
        return False
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Download canceled.{Colors.RESET}")
        return False
    except Exception as error:
        print(f"\n\n{Colors.RED}✗ Download failed: {error}{Colors.RESET}")
        return False


def handle_database_dumps(dumps_index: Optional[int] = None) -> int:
    """Handle the database dumps CLI functionality."""
    print(f"{Colors.BOLD}Fetching database dumps...{Colors.RESET}")

    dumps = get_database_dumps()
    if not dumps:
        print(f"{Colors.RED}Failed to fetch database dumps.{Colors.RESET}")
        return 1

    dumps.sort(key=lambda x: x.uploaded, reverse=True)

    if dumps_index is not None:
        if not 1 <= dumps_index <= len(dumps):
            print(
                f"{Colors.RED}Error: Dump index {dumps_index} "
                f"out of range (1-{len(dumps)}).{Colors.RESET}"
            )
            return 1
        selected_dump = dumps[dumps_index - 1]
        print(f"{Colors.BOLD}Selected:{Colors.RESET} {selected_dump.filename}")
    else:
        selected_dump = display_database_dumps(dumps)
        if not selected_dump:
            print("No dump selected.")
            return 0

    print(f"Size: {format_file_size(selected_dump.size)}")
    print(f"Uploaded: {selected_dump.uploaded.strftime('%Y-%m-%d %H:%M UTC')}")

    if not dumps_index:
        while True:
            response = input("\nDownload this dump? (y/N): ").strip().lower()
            if response in ["y", "yes"]:
                break
            if response in ["n", "no", ""]:
                print("Download canceled.")
                return 0

    download_path = None
    if not dumps_index:
        custom = input("Custom download path (Enter for default): ").strip()
        download_path = custom if custom else None

    return 0 if download_dump_with_progress(selected_dump, download_path) else 1


def display_search_results(
    results: List[Lyrics], search_query: str
) -> Optional[Lyrics]:
    """Display search results in an interactive UI."""
    if not results:
        print(f"{Colors.RED}No results found for '{search_query}'.{Colors.RESET}")
        return None

    selected_idx = 0
    page_size = 4

    while True:
        clear_screen()
        print(f"{Colors.BOLD}Search results for '{search_query}':{Colors.RESET}")
        print(
            f"Found {len(results)} results. Use {Colors.YELLOW}↑/↓{Colors.RESET} to "
            f"navigate, {Colors.YELLOW}'Enter'{Colors.RESET} to select."
        )
        print(f"Press {Colors.YELLOW}'q'{Colors.RESET} to quit.\n")

        start_idx = calculate_page_start(selected_idx, page_size, len(results))
        render_search_results(results, selected_idx, start_idx, page_size)

        result = handle_list_navigation(selected_idx, len(results) - 1)
        if result == "quit":
            return None
        if result == "select":
            return results[selected_idx]
        if isinstance(result, int) and 0 <= result < len(results):
            return results[result]
        if isinstance(result, int):
            selected_idx = result


def render_search_results(
    results: List[Lyrics], selected: int, start: int, page_size: int
) -> None:
    """Render search results with pagination."""
    if start > 0:
        print(f"{Colors.BRIGHT_BLACK}   ↑ more results above ↑{Colors.RESET}")

    end_idx = min(start + page_size, len(results))
    for i in range(start, end_idx):
        result = results[i]
        album = f" - {result.album_name}" if result.album_name else ""
        duration = format_time(result.duration)
        has_synced = bool(result.synced_lyrics and result.synced_lyrics.strip())
        sync_tag = (
            f"{Colors.GREEN}[synced]{Colors.RESET}"
            if has_synced
            else f"{Colors.YELLOW}[plain]{Colors.RESET}"
        )

        if i == selected:
            selector = (
                f"{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD}[{i+1}]{Colors.RESET} "
            )
        else:
            selector = f"{Colors.BRIGHT_CYAN}[{i+1}]{Colors.RESET} "

        print(
            f"{selector}{result.track_name} - {result.artist_name}{album} "
            f"({duration}) {sync_tag}"
        )

    if end_idx < len(results):
        print(f"{Colors.BRIGHT_BLACK}   ↓ more results below ↓{Colors.RESET}")


def handle_sync_lyrics(
    lyrics_file: str,
    audio_file: Optional[str] = None,
    output_file: Optional[str] = None,
) -> int:
    """Handle the lyrics sync CLI functionality."""
    if not os.path.exists(lyrics_file):
        print(f"{Colors.RED}Error: Lyrics file not found: {lyrics_file}{Colors.RESET}")
        return 1

    with open(lyrics_file, "r", encoding="utf-8") as file:
        lines = [line.strip() for line in file if line.strip()]

    if not lines:
        print(f"{Colors.RED}Error: No lyrics found in file.{Colors.RESET}")
        return 1

    if not output_file:
        from pathlib import Path

        output_file = str(Path(lyrics_file).stem) + ".lrc"

    pygame_mixer = setup_audio(audio_file)
    synced_lyrics = run_sync_session(lines, pygame_mixer)

    if pygame_mixer:
        pygame_mixer.music.stop()
        pygame_mixer.quit()

    with open(output_file, "w", encoding="utf-8") as file:
        file.write("\n".join(synced_lyrics))

    print(f"\n{Colors.GREEN}✓ Saved synced lyrics to: {output_file}{Colors.RESET}")
    return 0


def setup_audio(audio_file: Optional[str]):
    """Setup audio playback if available."""
    if not audio_file:
        return None

    if not os.path.exists(audio_file):
        print(f"{Colors.RED}Error: Audio file not found: {audio_file}{Colors.RESET}")
        return None

    try:
        import pygame

        pygame.mixer.init()
        pygame.mixer.music.load(audio_file)
        print(f"{Colors.GREEN}✓ Audio loaded: {audio_file}{Colors.RESET}")
        return pygame.mixer
    except ImportError:
        print(
            f"{Colors.YELLOW}Warning: pygame not installed. "
            f"Syncing without audio.{Colors.RESET}"
        )
    except Exception as error:
        print(f"{Colors.YELLOW}Warning: Could not load audio: {error}{Colors.RESET}")
    return None


def run_sync_session(lines: List[str], pygame_mixer) -> List[str]:
    """Run the interactive sync session."""
    print(f"\nPress {Colors.YELLOW}ENTER{Colors.RESET} to start...")
    get_keypress()

    if pygame_mixer:
        pygame_mixer.music.play()

    start_time = time.time()
    synced_lyrics = []
    current_index = 0

    print(
        f"\nPress {Colors.YELLOW}SPACE{Colors.RESET} to sync, "
        f"{Colors.YELLOW}Q{Colors.RESET} to quit and save\n"
    )

    while current_index < len(lines):
        render_sync_context(lines, current_index)

        while True:
            key = get_keypress()
            if key == " ":
                elapsed = time.time() - start_time
                timestamp = format_lrc_timestamp(elapsed)
                synced_lyrics.append(f"{timestamp}{lines[current_index]}")
                print(f"  {Colors.GREEN}✓ Synced at {timestamp}{Colors.RESET}")
                current_index += 1
                break
            if key.lower() == "q":
                return synced_lyrics

    return synced_lyrics


def render_sync_context(lines: List[str], current: int) -> None:
    """Render the sync context showing surrounding lines."""
    remaining = len(lines) - current
    print(f"\n{Colors.BRIGHT_BLACK}[{remaining} lines left]{Colors.RESET}")
    print("-" * 40)

    if current > 0:
        print(f"  {Colors.BRIGHT_BLACK}{lines[current - 1]}{Colors.RESET}")
    else:
        print()

    print(
        f"{Colors.BG_BLUE}{Colors.WHITE}{Colors.BOLD}>>> "
        f"{lines[current]}{Colors.RESET}"
    )

    for offset in range(1, 3):
        if current + offset < len(lines):
            print(f"  {Colors.BRIGHT_BLACK}{lines[current + offset]}{Colors.RESET}")

    print("-" * 40)


def handle_publish(args) -> int:
    """Handle the publish command."""
    if args.load.endswith(".json"):
        try:
            lyrics = Lyrics.from_json_file(args.load, args.none_char)
        except JSONDecodeError:
            print(f"{Colors.RED}Error: Invalid JSON file: {args.load}.{Colors.RESET}")
            return 1
    else:
        lyrics = Lyrics.from_lrc_file(args.load, args.none_char)

    duration = args.duration or lyrics.duration or 0
    if duration <= 0:
        print(f"{Colors.RED}Error: Duration required. Use --duration.{Colors.RESET}")
        return 1

    print(f"{Colors.BOLD}Publishing lyrics...{Colors.RESET}")
    print(f"Track: {args.song_name}")
    print(f"Artist: {args.artist_name}")
    print(f"Album: {args.album_name}")
    print(f"Duration: {duration}s")

    try:
        success = publish_lyrics(
            track_name=args.song_name,
            artist_name=args.artist_name,
            album_name=args.album_name,
            duration=duration,
            plain_lyrics=lyrics.plain_lyrics,
            synced_lyrics=lyrics.synced_lyrics,
        )
        if success:
            print(f"{Colors.GREEN}✓ Lyrics published successfully!{Colors.RESET}")
            return 0
        print(f"{Colors.RED}✗ Failed to publish lyrics.{Colors.RESET}")
        return 1
    except Exception as error:
        print(f"{Colors.RED}✗ Error publishing lyrics: {error}{Colors.RESET}")
        return 1


def handle_search(args) -> Optional[Lyrics]:
    """Handle the search command and return selected lyrics."""
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
            f"{Colors.RED}Error: Search requires a query "
            f"or song and artist names.{Colors.RESET}"
        )
        return None

    if not search_results:
        print(f"{Colors.RED}No results found for '{search_query}'.{Colors.RESET}")
        return None

    if args.search_index is not None:
        if 1 <= args.search_index <= len(search_results):
            return search_results[args.search_index - 1]
        print(
            f"{Colors.RED}Error: Search index {args.search_index} "
            f"out of range (1-{len(search_results)}).{Colors.RESET}"
        )
        return None

    return display_search_results(search_results, search_query)


def get_lyrics_from_args(args) -> Optional[Lyrics]:
    """Get lyrics based on command line arguments."""
    if args.id:
        return get_lyrics_by_id(args.id, args.none_char)

    if args.load:
        if args.load.endswith(".json"):
            try:
                return Lyrics.from_json_file(args.load, args.none_char)
            except JSONDecodeError:
                print(
                    f"{Colors.RED}Error: Invalid JSON file: {args.load}.{Colors.RESET}"
                )
                return None
        return Lyrics.from_lrc_file(args.load, args.none_char)

    if not args.song_name or not args.artist_name:
        print(
            f"{Colors.RED}Error: Song name and artist name are required.{Colors.RESET}"
        )
        return None

    return get_lyrics(
        args.song_name,
        args.artist_name,
        args.album_name,
        args.duration,
        args.none_char,
    )


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(description="Fetch and display song lyrics")
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("--id", type=int, default=None, help="ID of the song")
    parser.add_argument("song_name", nargs="?", default=None, help="Name of the song")
    parser.add_argument(
        "artist_name", nargs="?", default=None, help="Name of the artist"
    )
    parser.add_argument("album_name", nargs="?", default=None, help="Name of the album")
    parser.add_argument("--duration", type=int, default=None, help="Song duration")
    parser.add_argument(
        "--search", nargs="?", const=True, default=False, help="Search for lyrics"
    )
    parser.add_argument(
        "--search-index", type=int, default=None, help="Select search result (1-based)"
    )
    parser.add_argument("--none-char", default="♪", help="Character for empty lines")
    parser.add_argument("--no-info", action="store_true", help="Hide track information")
    parser.add_argument(
        "--plain",
        nargs="?",
        const="plain",
        default=None,
        choices=["plain", "lrc", "json"],
        help="Output format",
    )
    parser.add_argument("--file", default=None, help="Save lyrics to file")
    parser.add_argument(
        "--file-format", default="plain", choices=["plain", "lrc", "json"]
    )
    parser.add_argument("--load", default=None, help="Load lyrics from file")
    parser.add_argument(
        "--dumps", action="store_true", help="List and download database dumps"
    )
    parser.add_argument(
        "--dumps-index", type=int, default=None, help="Select dump index (1-based)"
    )
    parser.add_argument(
        "--publish", action="store_true", help="Publish lyrics to database"
    )
    parser.add_argument(
        "--sync", nargs="?", const=True, default=None, help="Sync plain lyrics to LRC"
    )
    parser.add_argument("--audio", default=None, help="Audio file for sync playback")
    return parser


def main() -> int:
    """Main function for the CLI tool."""
    parser = create_parser()
    args = parser.parse_args()

    if args.dumps:
        return handle_database_dumps(args.dumps_index)

    if args.sync is not None:
        if not args.load:
            print(f"{Colors.RED}Error: --sync requires --load.{Colors.RESET}")
            return 1
        output_file = args.sync if isinstance(args.sync, str) else None
        return handle_sync_lyrics(args.load, args.audio, output_file)

    if args.publish:
        if not args.load:
            print(f"{Colors.RED}Error: --publish requires --load.{Colors.RESET}")
            return 1
        if not args.song_name or not args.artist_name or not args.album_name:
            print(
                f"{Colors.RED}Error: --publish requires song_name, "
                f"artist_name, and album_name.{Colors.RESET}"
            )
            return 1
        return handle_publish(args)

    if args.search is not False:
        lyrics = handle_search(args)
        if not lyrics:
            return 1
    else:
        lyrics = get_lyrics_from_args(args)

    if not lyrics:
        identifier = args.id or f"{args.song_name} by {args.artist_name}"
        print(f"No lyrics found for {identifier}")
        return 1

    return output_lyrics(lyrics, args)


def output_lyrics(lyrics: Lyrics, args) -> int:
    """Output lyrics in the requested format."""
    if args.file:
        if args.file_format == "plain":
            lyrics.to_plain_file(args.file)
        elif args.file_format == "lrc":
            lyrics.to_lrc_file(args.file)
        elif args.file_format == "json":
            lyrics.to_json_file(args.file)
        print(
            f"{Colors.GREEN}{args.file_format.upper()} lyrics saved to "
            f"{args.file}{Colors.RESET}"
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
