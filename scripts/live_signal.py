#!/usr/bin/env python3

import importlib.util
import sys
from pathlib import Path


def load_rank_module():
    script_path = Path(__file__).with_name("truth_social_rank.py")
    spec = importlib.util.spec_from_file_location("truth_social_rank", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load truth_social_rank.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rank = load_rank_module()


def main() -> int:
    sys.argv = [
        "truth_social_rank.py",
        "--auto-prices",
        "--mode",
        "no_upper_only",
        "--validated-entry-window",
        "--one-per-window",
        "--top",
        "10",
    ]
    return rank.main()


if __name__ == "__main__":
    raise SystemExit(main())
