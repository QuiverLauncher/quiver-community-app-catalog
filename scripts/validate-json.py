#!/usr/bin/env python3
"""Validate repository JSON files and reject duplicate object keys."""

from __future__ import annotations

import json
import sys
from pathlib import Path


class DuplicateKeyError(ValueError):
    pass


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate object key: {key!r}")
        result[key] = value
    return result


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    raw = path.read_bytes()

    if b"\x00" in raw:
        errors.append("contains NUL bytes")
    if b"\t" in raw:
        errors.append("contains tabs; use two-space indentation")

    for number, line in enumerate(raw.splitlines(), start=1):
        if line.rstrip(b" \r\n") != line:
            errors.append(f"line {number}: trailing whitespace")
        indentation = len(line) - len(line.lstrip(b" "))
        if indentation % 2:
            errors.append(f"line {number}: indentation is not a multiple of two spaces")

    try:
        json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateKeyError) as error:
        errors.append(f"invalid JSON: {error}")

    return errors


def main() -> int:
    files = [Path(argument) for argument in sys.argv[1:]]
    if not files:
        print("usage: validate-json.py FILE ...", file=sys.stderr)
        return 2

    failed = False
    for path in files:
        errors = validate(path)
        if errors:
            failed = True
            for error in errors:
                print(f"{path}: {error}")
        else:
            print(f"{path}: valid")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
