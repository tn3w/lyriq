"""Main entry point for running lyriq as a package."""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
