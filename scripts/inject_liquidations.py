#!/usr/bin/env python3
"""Inject liquidation JSON files into Econoplus."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_DATA_DIR = r"C:\\Users\\Oliver\\Desktop\\canac_local\\data"
DEFAULT_ENDPOINT = "/liquidations/import"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Send liquidation JSON files to Econoplus. "
            "By default it reads from %s." % DEFAULT_DATA_DIR
        )
    )
    parser.add_argument(
        "--data-dir",
        default=DEFAULT_DATA_DIR,
        help="Directory containing liquidation .json files.",
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Base URL for Econoplus (e.g. https://econoplus.example.com/api)",
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help="Endpoint path for liquidation ingestion.",
    )
    parser.add_argument(
        "--public",
        default="canac",
        help="Public identifier (default: canac).",
    )
    parser.add_argument(
        "--ville",
        required=True,
        help="Ville (city) identifier to send.",
    )
    parser.add_argument(
        "--id",
        required=True,
        dest="site_id",
        help="Site id to send.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("ECONOPLUS_TOKEN", ""),
        help="Bearer token (or set ECONOPLUS_TOKEN).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payloads without sending them.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_payload(
    data: Any,
    public: str,
    ville: str,
    site_id: str,
    source_file: str,
) -> Dict[str, Any]:
    return {
        "public": public,
        "ville": ville,
        "id": site_id,
        "source_file": source_file,
        "liquidation": data,
    }


def send_payload(url: str, payload: Dict[str, Any], token: str) -> None:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=30) as response:
        response.read()


def main() -> int:
    args = parse_args()
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise SystemExit(f"Data directory not found: {data_dir}")

    files = sorted(data_dir.glob("*.json"))
    if not files:
        raise SystemExit(f"No .json files found in {data_dir}")

    base_url = args.base_url.rstrip("/")
    endpoint = args.endpoint.lstrip("/")
    url = f"{base_url}/{endpoint}"

    for path in files:
        payload = build_payload(
            load_json(path),
            public=args.public,
            ville=args.ville,
            site_id=args.site_id,
            source_file=path.name,
        )
        if args.dry_run:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            continue
        try:
            send_payload(url, payload, args.token)
            print(f"Uploaded {path.name}")
        except HTTPError as exc:
            raise SystemExit(
                f"Upload failed for {path.name}: {exc.code} {exc.reason}"
            ) from exc
        except URLError as exc:
            raise SystemExit(f"Upload failed for {path.name}: {exc.reason}") from exc

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
