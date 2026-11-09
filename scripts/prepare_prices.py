#!/usr/bin/env python3

import argparse
import re
import sys
from pathlib import Path


LINE_RE = re.compile(
    r"^\s*(?P<slug>[^|]+)\|(?P<bin>\d+\s*-\s*\d+)\|(?P<price>\d+(?:\.\d+)?)\s*$"
)
URL_SLUG_RE = re.compile(r"https?://polymarket\.com/event/(?P<slug>[a-z0-9-]+)")
SLUG_RE = re.compile(r"donald-trump-of-truth-social-posts-[a-z0-9-]+")
BIN_RE = re.compile(r"(?P<low>\d+)\s*-\s*(?P<high>\d+)")
PRICE_RE = re.compile(r"(?P<price>\d+(?:\.\d+)?)\s*%?")


def normalize_slug(value: str) -> str:
    return value.strip()


def normalize_bin(value: str) -> str:
    low, high = [part.strip() for part in value.split("-")]
    return f"{int(low)}-{int(high)}"


def normalize_price(value: str) -> str:
    price = float(value.strip())
    if price > 1:
        price /= 100.0
    return f"{price:.4f}".rstrip("0").rstrip(".")


def extract_slug(line: str) -> str | None:
    url_match = URL_SLUG_RE.search(line)
    if url_match:
        return url_match.group("slug")
    slug_match = SLUG_RE.search(line)
    if slug_match:
        return slug_match.group(0)
    return None


def extract_bin(line: str) -> str | None:
    match = BIN_RE.search(line)
    if not match:
        return None
    return normalize_bin(f"{match.group('low')}-{match.group('high')}")


def extract_price(line: str) -> str | None:
    cleaned = (
        line.replace("Yes", " ")
        .replace("YES", " ")
        .replace("yes", " ")
        .replace("@", " ")
    )
    matches = PRICE_RE.findall(cleaned)
    if not matches:
        return None
    return normalize_price(matches[-1])


def convert_flexible_line(line: str) -> str:
    slug = extract_slug(line)
    bin_label = extract_bin(line)
    price = extract_price(line)
    if not slug or not bin_label or not price:
        raise ValueError(
            "Invalid line format. Expected either slug|low-high|price or a line containing a market slug/url, a low-high bin, and a price."
        )
    return f"{slug}:{bin_label}:{price}"


def convert_lines(lines: list[str]) -> list[str]:
    output = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = LINE_RE.match(line)
        if match:
            slug = normalize_slug(match.group("slug"))
            bin_label = normalize_bin(match.group("bin"))
            price = normalize_price(match.group("price"))
            output.append(f"{slug}:{bin_label}:{price}")
            continue

        output.append(convert_flexible_line(line))
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert simple Polymarket price snapshots into price-file format."
    )
    parser.add_argument(
        "input",
        help="Input text file with one line per market. Supports strict slug|low-high|price lines and flexible copy-paste lines.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Optional output file. Defaults to stdout.",
    )
    args = parser.parse_args()

    source = Path(args.input)
    lines = source.read_text(encoding="utf-8").splitlines()
    converted = convert_lines(lines)
    rendered = "\n".join(converted) + ("\n" if converted else "")

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)

    return 0


if __name__ == "__main__":
    sys.exit(main())
