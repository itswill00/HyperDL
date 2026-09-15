#!/usr/bin/env python3
# Shim for backwards compat - real implementation moved to engine.core
# `python -m engine.downloader` and `from downloader import main` still work
from engine.core import *  # noqa: F401,F403
from engine.core import main

if __name__ == "__main__":
    main()
