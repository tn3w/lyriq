import sys
from lyriq import get_lyrics

lyrics = get_lyrics("Circles", "Post Malone")
if not lyrics:
    print("No lyrics found for 'Circles' by Post Malone")
    sys.exit(0)

print(f"ID: {lyrics.id}")
print(f"Name: {lyrics.name}")
print(f"Track: {lyrics.track_name}")
print(f"Artist: {lyrics.artist_name}")
print(f"Album: {lyrics.album_name}")
print(f"Duration: {lyrics.duration} seconds")
print(f"Instrumental: {'Yes' if lyrics.synced_lyrics else 'No'}")
print("\nPlain Lyrics:")
print("-" * 40)
print(lyrics.plain_lyrics)
print("\nSynchronized Lyrics (timestamp: lyric):")
print("-" * 40)

for timestamp, line in sorted(lyrics.lyrics.items()):
    print(f"[{timestamp}] {line}")

print("-" * 40)