#!/usr/bin/env python3
"""
Example for publishing lyrics to the LRCLIB API with Lyriq.

This example demonstrates how to:
- Generate a publish token using proof-of-work
- Publish lyrics to the API
- Handle common errors
"""

import sys
from lyriq import LyriqError
from lyriq.lyriq import (
    request_challenge,
    verify_nonce,
    generate_publish_token,
)


def main() -> None:
    """
    Lyrics publishing example for Lyriq library.

    This example demonstrates how to:
    - Generate a publish token using proof-of-work
    - Publish lyrics to the API
    """
    print("Lyriq Lyrics Publishing Example")
    print("=" * 40)

    # Example 1: Generate a publish token
    print("\nExample 1: Generating a publish token")
    print("-" * 40)
    try:
        print("Requesting challenge from the API...")
        prefix, target = request_challenge()
        print(f"Received challenge - Prefix: {prefix[:10]}... Target: {target[:10]}...")

        print("Generating publish token (solving proof-of-work challenge)...")
        print("This could take some time...")
        token = generate_publish_token(prefix, target)
        print(f"Generated token: {token}")
    except LyriqError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Example 2: Publishing lyrics to the API
    print("\nExample 2: Publishing lyrics to the API")
    print("-" * 40)
    print("Note: This is a demonstration and we're not making the actual API call.")
    print("To publish real lyrics, you would use code like this:")

    print("\nCode example:")
    print("```python")
    print("try:")
    print("    success = publish_lyrics(")
    print('        track_name="Song Title",')
    print('        artist_name="Artist Name",')
    print('        album_name="Album Name",')
    print("        duration=180,  # in seconds")
    print('        plain_lyrics="Your plain lyrics here...",')
    print('        synced_lyrics="[00:01.00]Your synchronized lyrics here..."')
    print("    )")
    print("    ")
    print("    if success:")
    print('        print("Lyrics published successfully!")')
    print("    else:")
    print('        print("Failed to publish lyrics.")')
    print("except LyriqError as e:")
    print('    print(f"Error: {e}")')
    print("```")

    # Example 3: Verify nonce demonstration
    print("\nExample 3: Verify nonce demonstration")
    print("-" * 40)

    # Create example bytes for demonstration
    target_hex = "000000FF00000000000000000000000000000000000000000000000000000000"
    valid_hex = "000000AA00000000000000000000000000000000000000000000000000000000"
    invalid_hex = "00000100FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"

    # Convert hex to bytes
    target_bytes = bytes.fromhex(target_hex)
    valid_bytes = bytes.fromhex(valid_hex)
    invalid_bytes = bytes.fromhex(invalid_hex)

    # Verify
    print(f"Target: {target_hex[:16]}...")
    print(
        f"Valid nonce: {valid_hex[:16]}... -> {verify_nonce(valid_bytes, target_bytes)}"
    )
    print(
        f"Invalid nonce: {invalid_hex[:16]}... -> {verify_nonce(invalid_bytes, target_bytes)}"
    )


if __name__ == "__main__":
    main()
