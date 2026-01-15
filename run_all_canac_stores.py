import json
import re
import shutil
from pathlib import Path
import subprocess
import sys

BASE_DIR = Path(__file__).resolve().parent

# Le scraper magasin écrit ici (d'après tes logs)
SOURCE_DIR = BASE_DIR / "data"

# Dossier final propre (nom ville + id) à publier
FINAL_DIR = BASE_DIR / "out_canac_json"

CATEGORY = "AUB"
STORES_FILE = BASE_DIR / "stores_canac.json"

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

def wanted_paths(store_id: int, city: str, province: str):
    store_id_str = f"{store_id:04d}"
    city_slug = slugify(city)
    prov_slug = slugify(province)
    base = f"{store_id_str}-{city_slug}-{prov_slug}_{CATEGORY}_liquidation"
    return (FINAL_DIR / f"{base}.json", FINAL_DIR / f"{base}.csv")

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

def copy_as(src: Path, dst: Path) -> bool:
    if src is None:
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True

def run_one_store(store_id: int, city: str, province: str):
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
    wanted_json, wanted_csv = wanted_paths(store_id, city, province)
    src_json, src_csv = find_store_outputs(store_id)

    if src_json is None:
        raise FileNotFoundError(
            f"Aucun JSON trouvé pour store {store_id} dans {SOURCE_DIR}. "
            f"Tes logs disent que ça devrait être dans data/. "
            f"Vérifie que le fichier existe vraiment."
        )

    copy_as(src_json, wanted_json)
    print(f"OK JSON -> {wanted_json}")

    if src_csv is not None:
        copy_as(src_csv, wanted_csv)
        print(f"OK CSV  -> {wanted_csv}")
    else:
        print(f"WARNING: Aucun CSV trouvé pour store {store_id} dans {SOURCE_DIR} (on continue).")

def main():
    if not STORES_FILE.exists():
        raise FileNotFoundError(f"Missing {STORES_FILE}. Create it with store_id/city/province.")

    stores = json.loads(STORES_FILE.read_text(encoding="utf-8"))

    for s in stores:
        run_one_store(
            int(s["store_id"]),
            str(s.get("city", f"store-{s['store_id']}")),
            str(s.get("province", "")),
        )

    print("\nDone. Final files written to:", FINAL_DIR)

if __name__ == "__main__":
    main()
