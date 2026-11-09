#!/usr/bin/env python3

import importlib.util
import sys
from pathlib import Path


def load_module():
    script_path = Path(__file__).with_name("elon_weekly_signal.py")
    spec = importlib.util.spec_from_file_location("elon_weekly_signal", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load elon_weekly_signal.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


elon = load_module()


def main() -> int:
    sys.argv = [
        "elon_weekly_signal.py",
        "--mode",
        "no_upper_only",
        "--upper-cutoff",
        "300",
        "--min-hours-since-start",
        "24",
        "--max-hours-since-start",
        "36",
        "--one-per-window",
        "--top",
        "1",
    ]
    return elon.main()


if __name__ == "__main__":
    raise SystemExit(main())
