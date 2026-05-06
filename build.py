#!/usr/bin/env python3
"""
Build a static Bambu Lab filament stock tracker for GigaParts.

The script downloads configured GigaParts configurable-product pages, parses the
embedded Magento variant config, and writes a self-contained index.html.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
OUT_PATH = ROOT / "index.html"
DATA_PATH = ROOT / "stock-data.json"
BASE_URL = "https://www.gigaparts.com"
OPTION_LABELS = {
    "3899": "Blue",
    "3901": "Black",
    "3902": "White",
    "3903": "Green",
    "3906": "Red",
    "3907": "Orange",
    "3910": "Purple",
    "3913": "Gray",
    "3964": "Gold",
    "4099": "Natural",
    "4101": "Yellow",
    "4109": "Clear",
    "4111": "Dark Gray",
    "4122": "Blue Gray",
    "4244": "1kg",
    "4246": "Spool",
    "4247": "Refill",
}
OPTION_HEX = {
    "3899": "#2a4b91",
    "3901": "#000000",
    "3902": "#ffffff",
    "3903": "#0b8f42",
    "3906": "#e8102d",
    "3907": "#ff4800",
    "3910": "#b500b5",
    "3913": "#878787",
    "3964": "#ab8b3f",
    "4099": "#f0e2c7",
    "4101": "#f4ed2a",
    "4109": "#dcebf2",
    "4111": "#515151",
    "4122": "#5b6579",
}

PRODUCT_URLS = [
    "https://www.gigaparts.com/bambu-lab-pla-basic-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pla-basic-gradient-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pla-glow-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pla-metal-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pla-sparkle-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pla-cf-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pla-marble-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pla-silk-multi-color-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pla-wood-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pla-translucent-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pla-aero-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pla-galaxy-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pla-matte-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pla-silk-plus-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pla-tough-plus-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-petg-basic-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-petg-translucent-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-petg-hf-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-petg-cf-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-tpu-95a-hf-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-tpu-for-ams-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-tpu-90a-85a-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-abs-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-abs-gf-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-asa-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pc-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pc-fr-3d-printer-filament.html",
    "https://www.gigaparts.com/bambu-lab-pa6-gf-3d-printer-filament.html",
]


def fetch(url: str) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        },
    )
    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def read_balanced_json(source: str, start: int) -> tuple[dict[str, Any], int]:
    depth = 0
    in_string = False
    escape = False
    for pos in range(start, len(source)):
        ch = source[pos]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                raw = source[start : pos + 1]
                return json.loads(raw), pos + 1
    raise ValueError("Could not find balanced JSON object")


def parse_ld_product(source: str) -> dict[str, Any]:
    for match in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', source, re.S):
        try:
            data = json.loads(html.unescape(match.group(1)))
        except json.JSONDecodeError:
            continue
        if data.get("@type") == "Product":
            return data
    return {}


def parse_configurable(source: str) -> dict[str, Any]:
    marker = "initConfigurableOptions("
    marker_pos = source.find(marker)
    if marker_pos == -1:
        raise ValueError("No initConfigurableOptions call found")
    first_quote = source.find("'", marker_pos)
    first_comma = source.find(",", first_quote)
    json_start = source.find("{", first_comma)
    config, _ = read_balanced_json(source, json_start)
    return config


def parse_swatches(source: str) -> dict[str, Any]:
    marker = "const swatchOptionsComponent = initSwatchOptions("
    marker_pos = source.find(marker)
    if marker_pos == -1:
        return {}
    data_start = marker_pos + len(marker)
    while data_start < len(source) and source[data_start].isspace():
        data_start += 1
    if data_start < len(source) and source[data_start] == "[":
        return {}
    json_start = source.find("{", data_start)
    swatches, _ = read_balanced_json(source, json_start)
    return swatches


def option_lookup(config: dict[str, Any]) -> dict[str, dict[str, str]]:
    lookups = {}
    for attr_id, attr in config.get("attributes", {}).items():
        lookups[attr_id] = {str(opt["id"]): opt["label"] for opt in attr.get("options", [])}
    return lookups


def swatch_hex(swatches: dict[str, Any], attr_id: str, option_id: str) -> str:
    value = swatches.get(attr_id, {}).get(option_id, {}).get("value", "")
    return value if isinstance(value, str) and value.startswith("#") else ""


def salable_product_ids(config: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for attr_map in config.get("salable", {}).values():
        for products in attr_map.values():
            ids.update(str(product_id) for product_id in products)
    return ids


def product_name_from_ld(ld_product: dict[str, Any], url: str) -> str:
    name = ld_product.get("name")
    if name:
        return re.sub(r"\s+", " ", name).strip()
    slug = url.rsplit("/", 1)[-1].removesuffix(".html")
    return slug.replace("-", " ").title()


def main_product_id(source: str) -> str:
    match = re.search(r'"ProductID":"(\d+)"', source)
    return match.group(1) if match else ""


def parse_notification_option_config(source: str, product_id: str) -> dict[str, Any]:
    if not product_id:
        return {}
    component = f"amNotificationProductViewComponent_{product_id}"
    component_pos = source.find(component)
    if component_pos == -1:
        return {}
    marker = "optionConfig:"
    marker_pos = source.find(marker, component_pos)
    if marker_pos == -1:
        return {}
    json_start = source.find("{", marker_pos)
    option_config, _ = read_balanced_json(source, json_start)
    return option_config


def short_line_name(name: str) -> str:
    cleaned = name.replace("Bambu Lab ", "").replace(" 3D Printer Filament", "")
    return cleaned.strip()


def group_for_line(line: str) -> str:
    upper = line.upper()
    for group in ("PLA", "PETG", "TPU", "ABS", "ASA", "PC", "PA"):
        if upper.startswith(group) or f" {group}" in upper:
            return group
    return "Other"


def product_page_link(url: str, sku: str, product_id: str) -> str:
    sku_part = f"?sku={sku}" if sku else ""
    return f"{url}{sku_part}#product-{product_id}"


def item_key(line: dict[str, Any], item: dict[str, Any]) -> str:
    variant_id = item.get("productId") or item.get("sku") or item.get("name")
    return f"{line.get('name', '')}|{variant_id}"


def stock_index(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    indexed = {}
    for line in data.get("lines", []):
        for item in line.get("items", []):
            indexed[item_key(line, item)] = {
                "line": line.get("name", ""),
                "group": line.get("group", ""),
                "name": item.get("name", ""),
                "sku": item.get("sku", ""),
                "productId": item.get("productId", ""),
                "url": item.get("url", line.get("url", "")),
                "price": item.get("price"),
                "inStock": bool(item.get("inStock")),
            }
    return indexed


def stock_changes(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    if not previous:
        return {"inStock": [], "outOfStock": []}
    old = stock_index(previous)
    new = stock_index(current)
    changes = {"inStock": [], "outOfStock": []}
    for key, item in sorted(new.items(), key=lambda row: (row[1]["line"], row[1]["name"])):
        old_item = old.get(key)
        if old_item is None or old_item["inStock"] == item["inStock"]:
            continue
        if item["inStock"]:
            changes["inStock"].append(item)
        else:
            changes["outOfStock"].append(item)
    return changes


def load_previous_data() -> dict[str, Any] | None:
    if not DATA_PATH.exists():
        return None
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def parse_product(url: str, source: str) -> dict[str, Any]:
    ld_product = parse_ld_product(source)
    config = parse_configurable(source)
    swatches = parse_swatches(source)
    page_product_id = main_product_id(source)
    lookups = option_lookup(config)
    salable = salable_product_ids(config)
    color_attr = next(
        (attr_id for attr_id, attr in config.get("attributes", {}).items() if attr.get("code") == "color"),
        None,
    )
    product_name = product_name_from_ld(ld_product, url)
    line = short_line_name(product_name)
    group = group_for_line(line)
    items = []

    if page_product_id and str(config.get("productId")) != page_product_id:
        option_config = parse_notification_option_config(source, page_product_id)
        price = ld_product.get("offers", {}).get("price")
        for key, stock_info in option_config.items():
            if not isinstance(stock_info, dict):
                continue
            option_ids = key.split(",")
            color_id = option_ids[0]
            labels = [OPTION_LABELS.get(option_id, option_id) for option_id in option_ids]
            color_name = labels[0]
            label = color_name
            if len(labels) > 1:
                label = f"{label} ({', '.join(labels[1:])})"
            product_id = str(stock_info.get("product_id", ""))
            items.append(
                {
                    "name": label,
                    "color": color_name,
                    "hex": OPTION_HEX.get(color_id, ""),
                    "sku": "",
                    "productId": product_id,
                    "inStock": bool(stock_info.get("is_in_stock")),
                    "price": price,
                    "url": product_page_link(url, "", product_id),
                }
            )
        if items:
            return {
                "name": line,
                "group": group,
                "url": url,
                "items": items,
            }

    for product_id, attr_values in sorted(config.get("index", {}).items(), key=lambda row: int(row[0])):
        label_parts = []
        color_name = ""
        color_hex = ""
        for attr_id, option_id in attr_values.items():
            attr_label = lookups.get(attr_id, {}).get(str(option_id), str(option_id))
            attr_code = config["attributes"].get(attr_id, {}).get("code", attr_id)
            if attr_code == "color":
                color_name = attr_label
                color_hex = swatch_hex(swatches, attr_id, str(option_id))
            else:
                label_parts.append(attr_label)

        price = None
        price_info = config.get("optionPrices", {}).get(str(product_id), {}).get("finalPrice", {})
        if isinstance(price_info, dict):
            price = price_info.get("amount")

        sku = config.get("sku", {}).get(str(product_id), "")
        label = color_name or "Default"
        if label_parts:
            label = f"{label} ({', '.join(label_parts)})"

        items.append(
            {
                "name": label,
                "color": color_name,
                "hex": color_hex,
                "sku": sku,
                "productId": str(product_id),
                "inStock": str(product_id) in salable,
                "price": price,
                "url": product_page_link(url, sku, str(product_id)),
            }
        )

    return {
        "name": line,
        "group": group,
        "url": url,
        "items": items,
    }


def build_data(previous: dict[str, Any] | None = None) -> dict[str, Any]:
    lines = []
    errors = []
    for i, url in enumerate(PRODUCT_URLS, 1):
        print(f"[{i:02d}/{len(PRODUCT_URLS)}] {url}")
        try:
            source = fetch(url)
            lines.append(parse_product(url, source))
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            errors.append({"url": url, "error": str(exc)})
            print(f"  warning: {exc}", file=sys.stderr)
        time.sleep(0.2)

    data = {
        "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "previousUpdatedAt": previous.get("updatedAt") if previous else None,
        "source": BASE_URL,
        "lines": lines,
        "changes": {"inStock": [], "outOfStock": []},
        "errors": errors,
    }
    data["changes"] = stock_changes(previous, data)
    return data


def render_html(data: dict[str, Any]) -> str:
    payload = json.dumps(data, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="en" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GigaParts Filament Stock</title>
  <style>
    *,*::before,*::after{{box-sizing:border-box}}
    :root{{
      --bg:#f7f8fb;--surface:#fff;--surface2:#eef2f7;--border:#d8dee8;--text:#172033;
      --muted:#5a667a;--dim:#8490a3;--accent:#1768ac;--in-bg:#dff4e7;--in-fg:#126133;
      --out-bg:#f8e1e1;--out-fg:#982626;--shadow:0 8px 26px rgba(25,34,52,.08)
    }}
    [data-theme="dark"]{{
      --bg:#14171d;--surface:#20252e;--surface2:#2a313c;--border:#384250;--text:#eef2f7;
      --muted:#b8c1cf;--dim:#808a9b;--accent:#66aee8;--in-bg:#143b27;--in-fg:#a8ecc1;
      --out-bg:#421f22;--out-fg:#ffb8b8;--shadow:0 10px 28px rgba(0,0,0,.22)
    }}
    body{{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
    header{{position:sticky;top:0;z-index:5;background:var(--surface);border-bottom:1px solid var(--border);box-shadow:var(--shadow)}}
    .topbar{{max-width:1280px;margin:0 auto;padding:14px 18px;display:flex;gap:14px;align-items:center;justify-content:space-between;flex-wrap:wrap}}
    h1{{font-size:18px;line-height:1.2;margin:0;font-weight:750}}
    .meta{{color:var(--muted);font-size:13px;margin-top:3px}}
    .controls{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
    input,select,button{{border:1px solid var(--border);background:var(--surface);color:var(--text);border-radius:7px;padding:8px 10px;font:inherit;font-size:13px}}
    button{{cursor:pointer}}
    button:hover{{background:var(--surface2)}}
    main{{max-width:1280px;margin:0 auto;padding:18px}}
    .summary{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:16px}}
    .stat{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px;box-shadow:var(--shadow)}}
    .stat strong{{display:block;font-size:22px;margin-bottom:2px}}
    .stat span{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}}
    .alerts{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-bottom:16px}}
    .alert-panel{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px;box-shadow:var(--shadow);min-height:84px}}
    .alert-panel h2{{font-size:13px;text-transform:uppercase;letter-spacing:.06em;margin:0 0 8px;color:var(--muted)}}
    .alert-panel ul{{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px}}
    .alert-panel li{{font-size:13px;color:var(--muted)}}
    .alert-panel a{{color:var(--accent);text-decoration:none}}
    .new-in li{{font-weight:800;color:var(--text)}}
    .no-alerts{{color:var(--dim);font-size:13px}}
    .saved-list{{background:var(--surface);border:1px solid var(--border);border-radius:8px;box-shadow:var(--shadow);margin-bottom:16px;overflow:hidden}}
    .saved-head{{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px;border-bottom:1px solid var(--border);flex-wrap:wrap}}
    .saved-head h2{{font-size:15px;margin:0}}
    .saved-actions{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
    .saved-items{{list-style:none;margin:0;padding:0}}
    .saved-items li{{display:grid;grid-template-columns:minmax(180px,1fr) auto auto;gap:10px;align-items:center;padding:10px 12px;border-top:1px solid var(--border);font-size:13px}}
    .saved-items li:first-child{{border-top:0}}
    .saved-main strong{{display:block;font-size:13px}}
    .saved-main span{{display:block;color:var(--muted);font-size:12px;margin-top:2px}}
    .saved-status{{border-radius:999px;padding:4px 8px;font-size:12px;white-space:nowrap}}
    .saved-status.in{{background:var(--in-bg);color:var(--in-fg)}}
    .saved-status.out{{background:var(--out-bg);color:var(--out-fg)}}
    .remove-saved,.save-btn{{font-size:12px;padding:6px 8px}}
    .save-btn{{width:100%;margin-top:7px}}
    .groups{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;align-items:start}}
    .group{{background:var(--surface);border:1px solid var(--border);border-radius:8px;overflow:visible;box-shadow:var(--shadow)}}
    .group-header{{padding:14px 14px 10px;border-bottom:1px solid var(--border);background:linear-gradient(180deg,var(--surface),var(--surface2))}}
    .group-title{{display:flex;align-items:baseline;justify-content:space-between;gap:10px}}
    .group-title h2{{font-size:16px;margin:0}}
    .group-title span{{font-size:13px;color:var(--muted)}}
    .bar{{height:6px;background:var(--border);border-radius:99px;overflow:hidden;margin-top:10px}}
    .bar i{{display:block;height:100%;background:#25955a;border-radius:inherit}}
    details{{border-top:1px solid var(--border)}}
    details:first-of-type{{border-top:0}}
    summary{{list-style:none;padding:10px 12px;display:flex;align-items:center;gap:8px;cursor:pointer}}
    summary::-webkit-details-marker{{display:none}}
    summary:hover{{background:var(--surface2)}}
    .twisty{{font-size:13px;color:var(--dim);transition:transform .16s}}
    details[open] .twisty{{transform:rotate(90deg)}}
    .line-name{{font-weight:700;font-size:14px;flex:1}}
    .counts{{font-size:12px;color:var(--muted);white-space:nowrap}}
    .shop{{font-size:12px;color:var(--accent);text-decoration:none}}
    .pills{{display:flex;flex-wrap:wrap;gap:6px;padding:0 12px 12px}}
    .pill{{position:relative;border:1px solid transparent;border-radius:999px;padding:5px 9px;font-size:12px;line-height:1.25;white-space:nowrap}}
    .pill.in{{background:var(--in-bg);color:var(--in-fg)}}
    .pill.out{{background:var(--out-bg);color:var(--out-fg)}}
    .pill[data-hex]::before{{content:"";display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--chip);border:1px solid rgba(0,0,0,.24);margin-right:5px;vertical-align:-1px}}
    .pill a{{color:inherit;text-decoration:none}}
    .pill::after{{content:"";display:none;position:absolute;left:0;right:0;top:100%;height:10px}}
    .pill .hover-card{{display:none;position:absolute;left:0;top:calc(100% - 1px);min-width:210px;background:var(--surface);border:1px solid var(--border);border-radius:8px;box-shadow:var(--shadow);padding:9px;z-index:20;color:var(--text)}}
    .pill:hover::after,.pill:focus-within::after{{display:block}}
    .pill:hover .hover-card,.pill:focus-within .hover-card{{display:block}}
    .hover-card a{{display:block;background:var(--accent);color:white;text-align:center;border-radius:6px;padding:7px 8px;margin-top:7px;font-weight:700}}
    .hover-card small{{display:block;color:var(--muted);margin-top:3px}}
    .empty{{padding:18px;background:var(--surface);border:1px solid var(--border);border-radius:8px;color:var(--muted)}}
    footer{{max-width:1280px;margin:0 auto;padding:8px 18px 28px;color:var(--dim);font-size:12px}}
    footer a{{color:var(--muted)}}
    @media (max-width:1000px){{.groups{{grid-template-columns:repeat(2,minmax(0,1fr))}}.summary{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
    @media (max-width:680px){{.groups{{grid-template-columns:1fr}}main{{padding:12px}}.summary{{grid-template-columns:1fr 1fr}}.saved-items li{{grid-template-columns:1fr}}}}
  </style>
</head>
<body>
<header>
  <div class="topbar">
    <div>
      <h1>GigaParts Filament Stock</h1>
      <div class="meta" id="updated"></div>
    </div>
    <div class="controls">
      <input id="search" type="search" placeholder="Search color, type, SKU...">
      <select id="status">
        <option value="all">All stock</option>
        <option value="in">In stock</option>
        <option value="out">Out of stock</option>
      </select>
      <select id="sort">
      <option value="line">Sort by line</option>
        <option value="stock">Sort in-stock first</option>
        <option value="name">Sort by color</option>
      </select>
      <button id="notify" type="button" title="Subscribe to browser alerts">Notify</button>
      <button id="theme" type="button" title="Toggle theme">Dark</button>
    </div>
  </div>
</header>
<main>
  <section class="alerts" id="alerts"></section>
  <section class="saved-list" id="saved-list"></section>
  <section class="summary" id="summary"></section>
  <section class="groups" id="groups"></section>
</main>
<footer>
  Data from <a href="https://www.gigaparts.com" target="_blank" rel="noreferrer">GigaParts</a>.
  In-stock pills show an add-to-cart link on hover or keyboard focus.
</footer>
<script>
let DATA={payload};
const GROUP_ORDER=["PLA","PETG","TPU","ABS","ASA","PC","PA","Other"];
const POLL_MS=60*60*1000;
const NOTIFY_KEY="gigapartsNotifyInStock";
const SAVED_KEY="gigapartsSavedFilaments";
const BROWSER_ID_KEY="gigapartsBrowserListId";
let query="", statusFilter="all", sortMode="line";
let currentItems=new Map();

const $=id=>document.getElementById(id);
const money=v=>typeof v==="number"?"$"+v.toFixed(2):"";
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[c]));
const words=item=>[item.name,item.color,item.sku,item.productId].join(" ").toLowerCase();
const itemId=(line,item)=>`${{line.name}}|${{item.productId||item.sku||item.name}}`;
function browserListId(){{
  let id=localStorage.getItem(BROWSER_ID_KEY);
  if(!id){{
    id=(crypto.randomUUID?crypto.randomUUID():`${{Date.now()}}-${{Math.random().toString(16).slice(2)}}`);
    localStorage.setItem(BROWSER_ID_KEY,id);
  }}
  return id;
}}
function flatten(data){{
  const map=new Map();
  for(const line of data.lines){{
    for(const item of line.items){{
      const key=itemId(line,item);
      map.set(key,{{key,line:line.name,group:line.group,...item}});
    }}
  }}
  return map;
}}
function transitionChanges(oldData,newData){{
  const oldMap=flatten(oldData), newMap=flatten(newData);
  const changes={{inStock:[],outOfStock:[]}};
  for(const [key,item] of newMap){{
    const old=oldMap.get(key);
    if(!old||old.inStock===item.inStock)continue;
    if(item.inStock)changes.inStock.push(item);
    else changes.outOfStock.push(item);
  }}
  changes.inStock.sort((a,b)=>(a.line+a.name).localeCompare(b.line+b.name));
  changes.outOfStock.sort((a,b)=>(a.line+a.name).localeCompare(b.line+b.name));
  return changes;
}}
function visibleItems(line){{
  return line.items.filter(item=>{{
    if(statusFilter==="in"&&!item.inStock)return false;
    if(statusFilter==="out"&&item.inStock)return false;
    return !query||words(item).includes(query)||line.name.toLowerCase().includes(query);
  }});
}}
function sortItems(items){{
  const copy=[...items];
  if(sortMode==="stock")copy.sort((a,b)=>Number(b.inStock)-Number(a.inStock)||a.name.localeCompare(b.name));
  else copy.sort((a,b)=>a.name.localeCompare(b.name));
  return copy;
}}
function totals(lines=DATA.lines){{
  const items=lines.flatMap(l=>l.items);
  const inStock=items.filter(i=>i.inStock).length;
  return {{lines:lines.length,total:items.length,inStock,out:items.length-inStock}};
}}
function renderSummary(filteredLines){{
  const all=totals(DATA.lines), shown=totals(filteredLines);
  $("summary").innerHTML=[
    ["Lines",shown.lines+"/"+all.lines],
    ["Shown variants",shown.total+"/"+all.total],
    ["In stock",shown.inStock],
    ["Out of stock",shown.out],
  ].map(([label,value])=>`<div class="stat"><strong>${{value}}</strong><span>${{label}}</span></div>`).join("");
}}
function loadSaved(){{
  try{{
    return JSON.parse(localStorage.getItem(SAVED_KEY)||"[]");
  }}catch(error){{
    return [];
  }}
}}
function saveSaved(items){{
  localStorage.setItem(SAVED_KEY,JSON.stringify(items));
}}
function savedWithFreshStock(){{
  const current=flatten(DATA);
  return loadSaved().map(item=>current.get(item.key)||item);
}}
function addSavedItem(key){{
  const item=currentItems.get(key);
  if(!item)return;
  const saved=loadSaved();
  if(!saved.some(row=>row.key===key)){{
    saved.push({{key,...item}});
    saveSaved(saved);
  }}
  renderSavedList();
}}
function removeSavedItem(key){{
  saveSaved(loadSaved().filter(item=>item.key!==key));
  renderSavedList();
}}
function savedListText(){{
  const items=savedWithFreshStock();
  if(!items.length)return "";
  const lines=items.map(item=>[
    `${{item.line}} - ${{item.name}}`,
    item.sku?`SKU: ${{item.sku}}`:null,
    `Status: ${{item.inStock?"In stock":"Out of stock"}}`,
    item.price!=null?`Price: ${{money(item.price)}}`:null,
    item.url
  ].filter(Boolean).join("\\n"));
  return `Saved GigaParts filament list\\nBrowser list ID: ${{browserListId()}}\\n\\n${{lines.join("\\n\\n")}}`;
}}
function emailSavedList(){{
  const body=savedListText();
  if(!body)return;
  location.href=`mailto:?subject=${{encodeURIComponent("GigaParts filament list")}}&body=${{encodeURIComponent(body)}}`;
}}
async function copySavedList(){{
  const body=savedListText();
  if(!body)return;
  await navigator.clipboard.writeText(body);
}}
function printSavedList(){{
  const body=savedListText();
  if(!body)return;
  const win=window.open("", "_blank", "noopener,noreferrer");
  if(!win)return;
  win.document.write(`<pre style="font:14px/1.5 system-ui, sans-serif; white-space:pre-wrap">${{esc(body)}}</pre>`);
  win.document.close();
  win.print();
}}
function renderSavedList(){{
  const items=savedWithFreshStock();
  $("saved-list").innerHTML=`
    <div class="saved-head">
      <div>
        <h2>Saved Filament List</h2>
        <div class="meta">${{items.length}} saved in this browser</div>
      </div>
      <div class="saved-actions">
        <button id="email-list" type="button" ${{items.length?"":"disabled"}}>Email to Myself</button>
        <button id="copy-list" type="button" ${{items.length?"":"disabled"}}>Copy</button>
        <button id="print-list" type="button" ${{items.length?"":"disabled"}}>Print</button>
        <button id="clear-list" type="button" ${{items.length?"":"disabled"}}>Clear</button>
      </div>
    </div>
    ${{items.length?`<ul class="saved-items">${{items.map(item=>`<li>
      <div class="saved-main"><strong>${{esc(item.line)}} - ${{esc(item.name)}}</strong><span>${{item.sku?esc(item.sku)+" - ":""}}${{item.price!=null?money(item.price):""}}</span></div>
      <span class="saved-status ${{item.inStock?"in":"out"}}">${{item.inStock?"In stock":"Out of stock"}}</span>
      <button class="remove-saved" type="button" data-remove-key="${{esc(item.key)}}">Remove</button>
    </li>`).join("")}}</ul>`:`<div class="empty">No saved filament yet. Hover a filament and choose Save to List.</div>`}}`;
}}
function renderAlerts(changes=DATA.changes||{{inStock:[],outOfStock:[]}}){{
  const list=(items,bold)=>items.length?`<ul>${{items.slice(0,12).map(item=>`<li><a href="${{esc(item.url)}}" target="_blank" rel="noreferrer">${{esc(item.line)}} - ${{esc(item.name)}}</a>${{item.sku?` <span>(${{esc(item.sku)}})</span>`:""}}</li>`).join("")}}${{items.length>12?`<li>+${{items.length-12}} more</li>`:""}}</ul>`:`<div class="no-alerts">No changes in this snapshot.</div>`;
  $("alerts").innerHTML=`
    <article class="alert-panel new-out">
      <h2>Newly Out of Stock</h2>
      ${{list(changes.outOfStock||[],false)}}
    </article>
    <article class="alert-panel new-in">
      <h2>Newly In Stock</h2>
      ${{list(changes.inStock||[],true)}}
    </article>`;
}}
function groupStats(lines){{
  const items=lines.flatMap(l=>visibleItems(l));
  const inStock=items.filter(i=>i.inStock).length;
  const pct=items.length?Math.round(inStock/items.length*100):0;
  return {{total:items.length,inStock,out:items.length-inStock,pct}};
}}
function lineHtml(line){{
  const items=sortItems(visibleItems(line));
  if(!items.length)return "";
  const inStock=items.filter(i=>i.inStock).length;
  const pills=items.map(item=>{{
    const key=itemId(line,item);
    currentItems.set(key,{{key,line:line.name,group:line.group,...item}});
    const style=item.hex?` style="--chip:${{esc(item.hex)}}" data-hex="${{esc(item.hex)}}"`:"";
    const body=`${{item.inStock?"In":"Out"}} &middot; ${{esc(item.name)}}`;
    const cart=item.inStock?`<a href="${{esc(item.url)}}" target="_blank" rel="noreferrer">Add to Cart</a>`:"";
    const hover=`<span class="hover-card"><strong>${{esc(item.name)}}</strong><small>${{esc(item.sku)}} ${{money(item.price)}}</small>${{cart}}<button class="save-btn" type="button" data-save-key="${{esc(key)}}">Save to List</button></span>`;
    return `<span class="pill ${{item.inStock?"in":"out"}}"${{style}} tabindex="0">${{body}}${{hover}}</span>`;
  }}).join("");
  return `<details open><summary><span class="twisty">&#9658;</span><span class="line-name">${{esc(line.name)}}</span><span class="counts">${{inStock}} in / ${{items.length-inStock}} out</span><a class="shop" href="${{esc(line.url)}}" target="_blank" rel="noreferrer" onclick="event.stopPropagation()">Shop</a></summary><div class="pills">${{pills}}</div></details>`;
}}
function render(){{
  currentItems=new Map();
  const lines=DATA.lines.map(line=>({{...line,items:visibleItems(line)}})).filter(line=>line.items.length);
  renderAlerts();
  renderSavedList();
  renderSummary(lines);
  const byGroup=new Map();
  for(const line of DATA.lines){{
    if(!visibleItems(line).length)continue;
    if(!byGroup.has(line.group))byGroup.set(line.group,[]);
    byGroup.get(line.group).push(line);
  }}
  const groups=[...byGroup.keys()].sort((a,b)=>GROUP_ORDER.indexOf(a)-GROUP_ORDER.indexOf(b)||a.localeCompare(b));
  $("groups").innerHTML=groups.map(group=>{{
    let lines=byGroup.get(group);
    lines=[...lines].sort((a,b)=>a.name.localeCompare(b.name));
    const stats=groupStats(lines);
    return `<section class="group"><div class="group-header"><div class="group-title"><h2>${{esc(group)}}</h2><span>${{stats.inStock}} in / ${{stats.out}} out</span></div><div class="bar"><i style="width:${{stats.pct}}%"></i></div></div>${{lines.map(lineHtml).join("")}}</section>`;
  }}).join("")||`<div class="empty">No filaments match the current filters.</div>`;
}}
function updateTimestamp(){{
  const updated=new Date(DATA.updatedAt).toLocaleString();
  $("updated").textContent=`Updated ${{updated}}. Auto-checks every hour.`;
}}
async function refreshStock(){{
  try{{
    const response=await fetch(`stock-data.json?ts=${{Date.now()}}`,{{cache:"no-store"}});
    if(!response.ok)throw new Error(`HTTP ${{response.status}}`);
    const latest=await response.json();
    if(!latest.updatedAt||latest.updatedAt===DATA.updatedAt)return;
    const changes=transitionChanges(DATA,latest);
    latest.changes=changes;
    DATA=latest;
    updateTimestamp();
    render();
    sendInStockNotifications(changes.inStock||[]);
  }}catch(error){{
    console.warn("Stock refresh failed",error);
  }}
}}
function notificationEnabled(){{
  return "Notification" in window&&localStorage.getItem(NOTIFY_KEY)==="1"&&Notification.permission==="granted";
}}
function updateNotifyButton(){{
  const btn=$("notify");
  if(!("Notification" in window)){{
    btn.textContent="No Notifications";
    btn.disabled=true;
    return;
  }}
  const enabled=localStorage.getItem(NOTIFY_KEY)==="1"&&Notification.permission==="granted";
  btn.textContent=enabled?"Notifying":"Notify";
}}
async function toggleNotifications(){{
  if(!("Notification" in window))return;
  if(localStorage.getItem(NOTIFY_KEY)==="1"){{
    localStorage.removeItem(NOTIFY_KEY);
    updateNotifyButton();
    return;
  }}
  const permission=Notification.permission==="granted"?"granted":await Notification.requestPermission();
  if(permission==="granted"){{
    localStorage.setItem(NOTIFY_KEY,"1");
    new Notification("GigaParts stock alerts enabled",{{body:"Newly in-stock filament alerts will appear while this page is open."}});
  }}
  updateNotifyButton();
}}
function sendInStockNotifications(items){{
  if(!notificationEnabled()||!items.length)return;
  const shown=items.slice(0,4);
  for(const item of shown){{
    new Notification(`${{item.line}} in stock`,{{body:item.sku?`${{item.name}} (${{item.sku}})`:item.name}});
  }}
  if(items.length>shown.length){{
    new Notification("More GigaParts filament in stock",{{body:`${{items.length-shown.length}} additional variants became available.`}});
  }}
}}
updateTimestamp();
$("search").addEventListener("input",e=>{{query=e.target.value.trim().toLowerCase();render();}});
$("status").addEventListener("change",e=>{{statusFilter=e.target.value;render();}});
$("sort").addEventListener("change",e=>{{sortMode=e.target.value;render();}});
$("notify").addEventListener("click",toggleNotifications);
$("saved-list").addEventListener("click",e=>{{
  const remove=e.target.closest("[data-remove-key]");
  if(remove)removeSavedItem(remove.dataset.removeKey);
  if(e.target.id==="email-list")emailSavedList();
  if(e.target.id==="copy-list")copySavedList();
  if(e.target.id==="print-list")printSavedList();
  if(e.target.id==="clear-list"){{
    saveSaved([]);
    renderSavedList();
  }}
}});
$("groups").addEventListener("click",e=>{{
  const save=e.target.closest("[data-save-key]");
  if(save)addSavedItem(save.dataset.saveKey);
}});
$("theme").addEventListener("click",()=>{{
  const html=document.documentElement;
  const dark=html.dataset.theme==="dark";
  html.dataset.theme=dark?"light":"dark";
  $("theme").textContent=dark?"Dark":"Light";
  localStorage.setItem("theme",html.dataset.theme);
}});
const saved=localStorage.getItem("theme");
if(saved){{document.documentElement.dataset.theme=saved;$("theme").textContent=saved==="dark"?"Light":"Dark";}}
updateNotifyButton();
setInterval(refreshStock,POLL_MS);
render();
</script>
</body>
</html>
"""


def main() -> int:
    previous = load_previous_data()
    data = build_data(previous)
    DATA_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    OUT_PATH.write_text(render_html(data), encoding="utf-8")
    print(f"Wrote {DATA_PATH}")
    print(f"Wrote {OUT_PATH}")
    if data["errors"]:
        print(f"Completed with {len(data['errors'])} scrape warning(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
