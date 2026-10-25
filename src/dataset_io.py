"""Read CSV / JSON-lines / JSON-array files in chunks so big files do not fill memory."""
import json
from pathlib import Path

import pandas as pd


class DatasetFormatError(Exception):
    """Raised with a beginner-friendly message when the input file cannot be used."""


def detect_format(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix in (".jsonl", ".ndjson"):
        return "jsonl"
    if suffix == ".json":
        return "json"
    raise DatasetFormatError(f"Unsupported file type '{suffix}'. Use .csv, .jsonl, .ndjson or .json")


def _clean_frame(frame: pd.DataFrame) -> list:
    frame = frame.astype(object).where(frame.notna(), None)
    return frame.to_dict("records")


def read_header(path: str) -> list:
    """Return the column names found in the file (first rows only)."""
    for chunk in iter_chunks(path, chunksize=50):
        return list(chunk.columns)
    return []


def iter_chunks(path: str, chunksize: int = 5000, bad_line_counter: dict = None):
    """Yield pandas DataFrames. Malformed CSV lines are COUNTED in bad_line_counter['bad_lines']."""
    file_format = detect_format(path)
    if not Path(path).is_file():
        raise DatasetFormatError(f"Dataset file not found: {path}")
    counter = bad_line_counter if bad_line_counter is not None else {}
    counter.setdefault("bad_lines", 0)

    if file_format == "csv":
        def on_bad_line(line):
            counter["bad_lines"] += 1
            return None  # skip the line but we have counted it

        reader = pd.read_csv(path, chunksize=chunksize, dtype=str, keep_default_na=False,
                             engine="python", on_bad_lines=on_bad_line, encoding="utf-8",
                             encoding_errors="replace")
        yield from reader
    elif file_format == "jsonl":
        reader = pd.read_json(path, lines=True, chunksize=chunksize, dtype=False, convert_dates=False)
        yield from reader
    else:  # json array - loaded fully (documented limitation)
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            data = next((v for v in data.values() if isinstance(v, list)), [data])
        frame = pd.DataFrame(data)
        for start in range(0, len(frame), chunksize):
            yield frame.iloc[start:start + chunksize]


def iter_records(path: str, chunksize: int = 5000, bad_line_counter: dict = None):
    """Yield lists of plain Python dicts (one list per chunk)."""
    for chunk in iter_chunks(path, chunksize, bad_line_counter):
        yield _clean_frame(chunk)
