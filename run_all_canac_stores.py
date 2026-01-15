import json
import re
from pathlib import Path
from typing import Optional
import subprocess
import sys

BASE_DIR = Path(__file__).resolve().parent

# Le scraper magasin écrit ici (d'après tes logs)
SOURCE_DIR = BASE_DIR / "data"

# Dossier final propre (nom ville + id) à publier
FINAL_DIR = BASE_DIR / "public" / "canac"
FINAL_INDEX = FINAL_DIR / "stores.json"

CATEGORY = "AUB"
STORES_FILE = BASE_DIR / "stores_canac.json"
FALLBACK_STORES_FILE = BASE_DIR / "stores.json"

HEADLESS = True
MAX_PAGES = None
TIMEOUT_MS = None
DEBUG = False

def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = (
        text.replace("é", "e").replace("è", "e").replace("ê", "e")
            .replace("à", "a").replace("â", "a")
            .replace("î", "i").replace("ï", "i")
            .replace("ô", "o")
            .replace("ù", "u").replace("û", "u")
            .replace("ç", "c")
    )
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text

def wanted_paths(store_id: int, city_slug: str, province: str):
    store_id_str = f"{store_id:04d}"
    prov_slug = slugify(province)
    base = f"{store_id_str}-{city_slug}-{prov_slug}_{CATEGORY}_liquidation"
    return FINAL_DIR / f"{base}.json"

def find_store_outputs(store_id: int):
    """
    Cherche dans SOURCE_DIR (data/) les fichiers produits par le scraper magasin
    ex: data/canac_store39_AUB_liquidation.json
    """
    sid = str(store_id)

    jsons = sorted(
        SOURCE_DIR.glob(f"*{sid}*{CATEGORY}*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    csvs = sorted(
        SOURCE_DIR.glob(f"*{sid}*{CATEGORY}*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return (jsons[0] if jsons else None, csvs[0] if csvs else None)

def load_stores():
    if STORES_FILE.exists():
        path = STORES_FILE
    elif FALLBACK_STORES_FILE.exists():
        path = FALLBACK_STORES_FILE
    else:
        raise FileNotFoundError(
            f"Missing {STORES_FILE} or {FALLBACK_STORES_FILE}. "
            "Create it with store_id/city/province."
        )
    return json.loads(path.read_text(encoding="utf-8"))

def format_label(store_id: int, city: str, province: str, store_label: Optional[str]):
    if store_label:
        return store_label.strip()
    city_clean = " ".join(city.split()).strip()
    suffix = f" ({province})" if province else ""
    if city_clean:
        return f"{city_clean}{suffix}".strip()
    return f"Store {store_id}{suffix}".strip()

def to_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value) if isinstance(value, float) and value.is_integer() else value
    if isinstance(value, str):
        cleaned = value.strip().replace("$", "").replace("%", "")
        cleaned = cleaned.replace(",", ".")
        if not cleaned:
            return None
        try:
            num = float(cleaned)
            return int(num) if num.is_integer() else num
        except ValueError:
            return None
    return None

def get_first(item: dict, keys):
    for key in keys:
        if key in item:
            return item[key]
    return None

def normalize_item(item: dict, store_id: int, store_label: str):
    updated = dict(item)
    price_regular = to_number(get_first(item, ["price_regular", "priceRegular", "regular_price"]))
    price_sale = to_number(get_first(item, ["price_sale", "priceSale", "sale_price"]))
    discount_pct = to_number(get_first(item, ["discount_pct", "discountPercent", "discount_percent"]))
    stock_text = get_first(item, ["stock_text", "stockText"])

    updated["store_id"] = store_id
    updated["store_label"] = store_label
    updated["price_regular"] = price_regular
    updated["price_sale"] = price_sale
    updated["discount_pct"] = discount_pct
    updated["stock_text"] = stock_text
    updated["storeId"] = store_id
    updated["storeLabel"] = store_label
    updated["priceRegular"] = price_regular
    updated["priceSale"] = price_sale
    updated["discountPercent"] = discount_pct
    updated["stockText"] = stock_text
    return updated

def load_items(src_json: Path):
    payload = json.loads(src_json.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload, None
    if isinstance(payload, dict):
        items = payload.get("items", [])
        return items, payload
    return [], None

def write_output(dst_json: Path, items: list, payload: Optional[dict]):
    dst_json.parent.mkdir(parents=True, exist_ok=True)
    if payload is None:
        dst_json.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    payload = dict(payload)
    payload["items"] = items
    dst_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def run_one_store(store_id: int, city: str, province: str, store_label: str, city_slug: str):
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Store {store_id} {city} ({province}) ===")

    python_exe = sys.executable
    script = str(BASE_DIR / "canac_scraper_magasin.py")

    cmd = [
        python_exe,
        script,
        "--store-id", str(store_id),
        "--category", CATEGORY,
    ]

    if MAX_PAGES is not None:
        cmd += ["--max-pages", str(MAX_PAGES)]
    if TIMEOUT_MS is not None:
        cmd += ["--timeout-ms", str(TIMEOUT_MS)]
    if DEBUG:
        cmd += ["--debug"]

    cmd += ["--headless"] if HEADLESS else ["--headed"]

    print("CMD:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    # Renommage/copie vers FINAL_DIR (format ville + id)
    wanted_json = wanted_paths(store_id, city_slug, province)
    src_json, src_csv = find_store_outputs(store_id)

    if src_json is None:
        raise FileNotFoundError(
            f"Aucun JSON trouvé pour store {store_id} dans {SOURCE_DIR}. "
            f"Tes logs disent que ça devrait être dans data/. "
            f"Vérifie que le fichier existe vraiment."
        )

    items, payload = load_items(src_json)
    normalized = [normalize_item(item, store_id, store_label) for item in items]
    write_output(wanted_json, normalized, payload)
    print(f"OK JSON -> {wanted_json}")

    if src_csv is None:
        print(f"WARNING: Aucun CSV trouvé pour store {store_id} dans {SOURCE_DIR} (on continue).")

def main():
    stores = load_stores()
    index_entries = []

    for s in stores:
        store_id = int(s["store_id"])
        city = str(s.get("city", f"store-{store_id}"))
        province = str(s.get("province", ""))
        store_label = format_label(store_id, city, province, s.get("store_label") or s.get("label"))
        city_slug = slugify(city)

        run_one_store(store_id, city, province, store_label, city_slug)

        filename = wanted_paths(store_id, city_slug, province).name
        index_entries.append(
            {
                "storeId": store_id,
                "citySlug": city_slug,
                "province": province,
                "label": store_label,
                "filePath": f"/canac/{filename}",
            }
        )

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_INDEX.write_text(json.dumps(index_entries, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nDone. Final files written to:", FINAL_DIR)

if __name__ == "__main__":
    main()
