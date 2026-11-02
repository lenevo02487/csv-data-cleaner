#!/usr/bin/env python3
"""
csv-data-cleaner — turn a messy CSV export into a clean, analysis-ready CSV.

What it does:
  * trims stray whitespace from every cell (header included)
  * removes fully-empty rows
  * drops repeated header rows that appear in the middle of the file
    (a classic artifact of merged monthly exports)
  * normalizes dates in date columns to YYYY-MM-DD
  * optionally removes duplicate rows (--dedupe) — duplicates are detected
    AFTER cleaning, so the same row written with two different date
    formats still counts as one duplicate
  * prints a summary of everything it changed

Standard library only — nothing to install. Python 3.8+.

Usage:
    python3 csv_cleaner.py messy.csv
        -> writes messy_clean.csv
    python3 csv_cleaner.py messy.csv -o clean.csv --dedupe
    python3 csv_cleaner.py messy.csv --date-columns order_date,signup_date

Date handling: day-first formats (DD/MM/YYYY) are tried before month-first,
which matches most non-US exports. Unparseable values are left unchanged.
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

DATE_FORMATS = [
    "%Y-%m-%d",   # 2026-01-05 (already clean)
    "%Y/%m/%d",   # 2026/01/05
    "%d/%m/%Y",   # 05/01/2026
    "%d-%m-%Y",   # 05-01-2026
    "%d.%m.%Y",   # 05.01.2026
    "%d %b %Y",   # 5 Jan 2026
    "%d %B %Y",   # 5 January 2026
    "%b %d, %Y",  # Jan 5, 2026
    "%B %d, %Y",  # January 5, 2026
    "%m/%d/%Y",   # 01/05/2026 (month-first, tried last)
]


def normalize_date(value):
    """Return (new_value, changed). Unparseable values pass through as-is."""
    v = value.strip()
    if not v:
        return value, False
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(v, fmt)
        except ValueError:
            continue
        out = parsed.strftime("%Y-%m-%d")
        return out, out != v
    return value, False


def pick_date_columns(header, requested):
    """Column indexes to treat as dates: the user's list, or auto-detect
    any header whose name contains 'date'."""
    if requested:
        names = [c.strip() for c in requested.split(",") if c.strip()]
        missing = [n for n in names if n not in header]
        if missing:
            sys.exit(f"Date column(s) not found in header: {', '.join(missing)}\n"
                     f"Header is: {', '.join(header)}")
        return [header.index(n) for n in names], names
    idx = [i for i, h in enumerate(header) if "date" in h.lower()]
    return idx, [header[i] for i in idx]


def clean(input_path, output_path, dedupe=False, date_columns=None):
    with open(input_path, newline="", encoding="utf-8-sig") as f:
        raw_rows = list(csv.reader(f))

    stats = {"rows_in": 0, "empty_removed": 0, "header_dropped": 0,
             "duplicates_removed": 0, "dates_normalized": 0}

    # The header is the first non-empty row.
    header = None
    body_start = 0
    for i, row in enumerate(raw_rows):
        cells = [c.strip() for c in row]
        if any(cells):
            header = cells
            body_start = i + 1
            break
    if header is None:
        sys.exit("Input file has no header row (file is empty or all blank).")

    width = len(header)
    date_idx, date_names = pick_date_columns(header, date_columns)

    cleaned = []
    seen = set()
    for row in raw_rows[body_start:]:
        stats["rows_in"] += 1
        cells = [c.strip() for c in row]

        if not any(cells):  # fully-empty row (blank line or only commas)
            stats["empty_removed"] += 1
            continue
        if cells == header:  # repeated header from a merged export
            stats["header_dropped"] += 1
            continue

        if len(cells) < width:  # pad short rows so columns stay aligned
            cells += [""] * (width - len(cells))

        for i in date_idx:
            if i < len(cells):
                new_value, changed = normalize_date(cells[i])
                cells[i] = new_value
                if changed:
                    stats["dates_normalized"] += 1

        if dedupe:
            key = tuple(cells)
            if key in seen:
                stats["duplicates_removed"] += 1
                continue
            seen.add(key)

        cleaned.append(cells)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(cleaned)

    stats["rows_out"] = len(cleaned)
    stats["date_columns"] = date_names
    return stats


def main():
    ap = argparse.ArgumentParser(
        description="Clean a messy CSV: trim cells, drop empty/repeated-header "
                    "rows, normalize dates, optionally dedupe.")
    ap.add_argument("input", help="messy input CSV file")
    ap.add_argument("-o", "--output",
                    help="output CSV file (default: <input>_clean.csv)")
    ap.add_argument("--dedupe", action="store_true",
                    help="remove duplicate rows (checked after cleaning)")
    ap.add_argument("--date-columns",
                    help="comma-separated date column names "
                         "(default: auto-detect headers containing 'date')")
    args = ap.parse_args()

    output = args.output or str(Path(args.input).with_name(
        Path(args.input).stem + "_clean.csv"))

    stats = clean(args.input, output, dedupe=args.dedupe,
                  date_columns=args.date_columns)

    print(f"Cleaned {args.input} -> {output}")
    print(f"  Rows in:             {stats['rows_in']}")
    print(f"  Rows out:            {stats['rows_out']}")
    print(f"  Empty rows removed:  {stats['empty_removed']}")
    print(f"  Header rows dropped: {stats['header_dropped']}")
    print(f"  Duplicates removed:  {stats['duplicates_removed']}"
          f"{'' if args.dedupe else '  (run with --dedupe to enable)'}")
    cols = ", ".join(stats["date_columns"]) or "none detected"
    print(f"  Date columns:        {cols}")
    print(f"  Dates normalized:    {stats['dates_normalized']}")


if __name__ == "__main__":
    main()
