#!/usr/bin/env python3
"""Post newly in-stock GigaParts items to the notification Worker."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "stock-data.json"


def event_key(item: dict[str, object]) -> str:
    variant = item.get("productId") or item.get("sku") or item.get("name") or ""
    return f"{item.get('brand', '')}|{item.get('line', '')}|{variant}"


def payload_from_data(data: dict[str, object]) -> dict[str, object]:
    changes = data.get("changes") if isinstance(data.get("changes"), dict) else {}
    in_stock = changes.get("inStock", []) if isinstance(changes, dict) else []
    items = []
    for item in in_stock if isinstance(in_stock, list) else []:
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "key": event_key(item),
                "brand": item.get("brand", ""),
                "line": item.get("line", ""),
                "name": item.get("name", ""),
                "sku": item.get("sku", ""),
                "url": item.get("url", ""),
            }
        )
    return {
        "updatedAt": data.get("updatedAt", ""),
        "changes": {"inStock": items},
    }


def main() -> int:
    worker_url = os.environ.get("NOTIFY_WORKER_URL", "").strip()
    token = os.environ.get("NOTIFY_WORKER_TOKEN", "").strip()
    if not worker_url or not token:
        print("NOTIFY_WORKER_URL or NOTIFY_WORKER_TOKEN is not configured; skipping notifications.")
        return 0

    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    payload = payload_from_data(data)
    items = payload["changes"]["inStock"]  # type: ignore[index]
    if not items:
        print("No newly in-stock items to notify.")
        return 0

    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(
        worker_url,
        data=body,
        method="POST",
        headers={
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
            "user-agent": "gigaparts-filament-stock-github-action",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            print(f"Posted {len(items)} stock event item(s): HTTP {response.status}")
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"warning: failed to post stock events: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
