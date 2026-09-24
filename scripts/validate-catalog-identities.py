#!/usr/bin/env python3
"""Verify optional catalog IDs against the production website authority."""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Authority redirects are not allowed")


def validate(files, origin, lookup):
    seen = set()
    checked = 0
    for path in files:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for entry in data.get("apps", []):
            if "catalogId" not in entry:
                continue  # No backfill requirement.
            identity = entry["catalogId"]
            if not isinstance(identity, str) or not re.fullmatch(r"qcat_[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}", identity):
                raise ValueError("Invalid or non-production catalogId")
            if identity in seen:
                raise ValueError("Duplicate catalogId across catalog lists")
            seen.add(identity)
            if not re.fullmatch(r"https://[a-z0-9-]+\.convex\.site", origin):
                raise ValueError("Set CATALOG_PRODUCTION_ORIGIN to the production website authority")
            record = lookup(f"{origin}/catalog-authority/identities/{identity}")
            if record.get("catalogId") != identity or record.get("repository", "").lower() != entry.get("repository", "").lower() or record.get("repositorySource") != entry.get("repositorySource", "github") or record.get("folderName") != entry.get("folderName"):
                raise ValueError("catalogId does not belong to this production catalog entry")
            checked += 1
    return checked


def lookup(url):
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(urllib.request.Request(url, headers={"User-Agent": "QuiverCatalogValidation"}), timeout=20) as response:
        body = response.read(16385)
    if len(body) > 16384:
        raise ValueError("Authority response too large")
    record = json.loads(body)
    if not isinstance(record, dict):
        raise ValueError("Invalid authority response")
    return record


if __name__ == "__main__":
    try:
        count = validate(sys.argv[1:], os.environ.get("CATALOG_PRODUCTION_ORIGIN", ""), lookup)
        print(f"Verified {count} production catalog identities")
    except Exception as error:
        print(f"Catalog identity validation failed: {error}", file=sys.stderr)
        sys.exit(1)
