#!/usr/bin/env python3
"""Download GTFS ZIP feeds and audit the Day 1 TravelWise data requirements.

Install: python -m pip install pandas
Run:     python scripts/audit_gtfs.py
Optional: python scripts/audit_gtfs.py --feed-name mtc --feed-url URL

The default public archives are mirrors, not a claim that each archive was
retrieved directly from CUMTA. See docs/day-1-data-audit.md for provenance.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import zipfile
from collections import Counter
from io import BytesIO, TextIOWrapper
from typing import Any

import pandas as pd

SOURCE = "https://raw.githubusercontent.com/ungalsoththu/ChennaiGTFS/af0742dba777f9657ed6fda2046d6c2a721d630b/data"
DEFAULT_FEEDS = {
    "mtc": f"{SOURCE}/mtc-gtfs.zip",
    "cmrl": f"{SOURCE}/cmrl-gtfs.zip",
    "srr": f"{SOURCE}/srr-gtfs.zip",
}
CORE_FILES = ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt", "calendar.txt")
FARE_FILES = ("fare_attributes.txt", "fare_rules.txt")
TIME_PATTERN = re.compile(r"^\d{1,3}:[0-5]\d:[0-5]\d$")


def read_csv_from_zip(archive: zipfile.ZipFile, filename: str) -> pd.DataFrame:
    """Find a GTFS file at the archive root or inside a containing directory."""
    matches = [name for name in archive.namelist() if name == filename or name.endswith("/" + filename)]
    if not matches:
        raise KeyError(filename)
    # Prefer the shallowest path if an archive unexpectedly contains duplicates.
    member = min(matches, key=lambda name: (name.count("/"), name))
    with archive.open(member) as binary:
        return pd.read_csv(TextIOWrapper(binary, encoding="utf-8-sig"), dtype=str, keep_default_na=False)


def inspect_feed(name: str, url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "TravelWise-GTFS-Day1-Audit/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read()

    report: dict[str, Any] = {"feed": name, "url": url, "archive_bytes": len(payload), "files": {}}
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        available = {member.rsplit("/", 1)[-1] for member in archive.namelist() if not member.endswith("/")}
        frames: dict[str, pd.DataFrame] = {}
        for filename in (*CORE_FILES, *FARE_FILES):
            present = filename in available
            entry: dict[str, Any] = {"exists": present, "non_empty": False, "rows": None}
            if present:
                frame = read_csv_from_zip(archive, filename)
                frames[filename] = frame
                entry["rows"] = len(frame)
                entry["non_empty"] = len(frame.index) > 0 and len(frame.columns) > 0
                entry["columns"] = list(frame.columns)
            report["files"][filename] = entry

    for filename, key in (("stops.txt", "stops"), ("routes.txt", "routes"), ("trips.txt", "trips"), ("stop_times.txt", "stop_time_rows")):
        if filename in frames:
            report[key] = len(frames[filename])

    if "stop_times.txt" in frames:
        stop_times = frames["stop_times.txt"]
        time_stats: dict[str, Any] = {}
        for column in ("arrival_time", "departure_time"):
            if column not in stop_times.columns:
                time_stats[column] = {"column_exists": False}
                continue
            values = stop_times[column].astype(str).str.strip()
            nonblank = values[values.ne("")]
            valid = nonblank.str.match(TIME_PATTERN)
            counts = Counter(nonblank[~valid].tolist())
            time_stats[column] = {
                "column_exists": True,
                "nonblank_rows": int(len(nonblank)),
                "blank_rows": int(len(values) - len(nonblank)),
                "valid_gtfs_time_rows": int(valid.sum()),
                "invalid_nonblank_rows": int((~valid).sum()),
                "unique_nonblank_values": int(nonblank.nunique()),
                "most_common_values": counts.most_common(5) if counts else nonblank.value_counts().head(5).to_dict(),
                "placeholder_00_00_15_rows": int(nonblank.eq("00:00:15").sum()),
            }
        report["times"] = time_stats

        sequence_result: dict[str, Any] = {"column_exists": "stop_sequence" in stop_times.columns}
        if "trip_id" in stop_times.columns and "stop_sequence" in stop_times.columns:
            sequence = stop_times[["trip_id", "stop_sequence"]].copy()
            sequence["sequence_numeric"] = pd.to_numeric(sequence["stop_sequence"], errors="coerce")
            missing_trip = sequence["trip_id"].eq("")
            invalid = sequence["sequence_numeric"].isna()
            valid_rows = sequence.loc[~missing_trip & ~invalid].sort_values(
                ["trip_id", "sequence_numeric"], kind="stable"
            )
            duplicated = valid_rows.duplicated(["trip_id", "sequence_numeric"], keep=False)
            # In original feed order, GTFS stop_sequence must strictly increase per trip.
            ordered = sequence.loc[~missing_trip & ~invalid].copy()
            ordered["previous"] = ordered.groupby("trip_id")["sequence_numeric"].shift()
            non_increasing_rows = ordered["previous"].notna() & (ordered["sequence_numeric"] <= ordered["previous"])
            group_stats = valid_rows.groupby("trip_id")["sequence_numeric"].agg(["min", "max", "count"])
            gaps = int((group_stats["max"] - group_stats["min"] + 1 - group_stats["count"]).clip(lower=0).sum())
            sequence_result.update({
                "trip_ids_missing": int(missing_trip.sum()),
                "invalid_sequence_rows": int(invalid.sum()),
                "duplicate_sequence_rows": int(duplicated.sum()),
                "non_increasing_rows_in_feed_order": int(non_increasing_rows.sum()),
                "trips_with_non_increasing_order": int(ordered.loc[non_increasing_rows, "trip_id"].nunique()),
                "trips_with_sequence_gaps": int((group_stats["max"] - group_stats["min"] + 1 > group_stats["count"]).sum()),
                "missing_integer_positions_within_min_max": gaps,
                "note": "GTFS requires increasing stop_sequence within a trip; numeric gaps are reported but are not by themselves invalid.",
            })
        report["sequence"] = sequence_result

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed-name", action="append", help="Name for a custom feed; pair with --feed-url")
    parser.add_argument("--feed-url", action="append", help="GTFS ZIP URL; pair with --feed-name")
    args = parser.parse_args()

    if bool(args.feed_name) != bool(args.feed_url) or (args.feed_name and len(args.feed_name) != len(args.feed_url)):
        parser.error("provide the same number of --feed-name and --feed-url options")
    feeds = dict(zip(args.feed_name, args.feed_url)) if args.feed_name else DEFAULT_FEEDS

    reports = []
    for name, url in feeds.items():
        try:
            reports.append(inspect_feed(name, url))
        except (OSError, ValueError, zipfile.BadZipFile, KeyError, pd.errors.ParserError) as error:
            reports.append({"feed": name, "url": url, "error": f"{type(error).__name__}: {error}"})

    print(json.dumps({"audit": "TravelWise Day 1 GTFS feasibility", "feeds": reports}, indent=2, ensure_ascii=False))
    return 1 if any("error" in report for report in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
