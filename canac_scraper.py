import csv
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.canac.ca"
START_URL = "https://www.canac.ca/canac/fr/2/c/AUB?tag_product=Liquidation"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
}


def parse_price(text: str) -> float | None:
    if not text:
        return None
    # Ex: "349,00 $" or "1 249,00 $"
    t = text.strip()
    t = t.replace("\xa0", " ").replace("$", "").strip()
    t = t.replace(" ", "")
    # keep digits + comma/dot
    m = re.findall(r"[\d]+(?:[.,]\d+)?", t)
    if not m:
        return None
    v = m[0].replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def find_products_on_page(html: str):
    soup = BeautifulSoup(html, "html.parser")

    # Canac change parfois ses classes; on prend une strategie "wide net":
    # on repere les blocs qui contiennent "Code produit:"
    code_nodes = soup.find_all(string=re.compile(r"Code produit\s*:", re.I))
    product_blocks = []
    for node in code_nodes:
        # remonte a un parent raisonnable
        parent = node
        for _ in range(6):
            if parent and parent.name in ("article", "li", "div"):
                # heuristique: un bloc avec au moins 1 lien
                if parent.find("a", href=True):
                    product_blocks.append(parent)
                    break
            parent = parent.parent

    # dedupe
    uniq = []
    seen = set()
    for b in product_blocks:
        key = str(b)[:300]
        if key not in seen:
            seen.add(key)
            uniq.append(b)
    return uniq


def extract_product(block):
    text = " ".join(block.get_text(" ", strip=True).split())

    # Nom: souvent le premier gros texte avant "Code produit"
    name = None
    # Essaie: premier lien avec du texte
    a = block.find("a", href=True)
    if a and a.get_text(strip=True):
        name = a.get_text(" ", strip=True)

    # URL produit
    url = None
    if a and a["href"]:
        url = urljoin(BASE, a["href"])

    # Image
    img = block.find("img")
    image_url = None
    if img and img.get("src"):
        image_url = urljoin(BASE, img["src"])

    # Code produit (SKU)
    sku = None
    msku = re.search(r"Code produit\s*:\s*([A-Z0-9\-]+)", text, re.I)
    if msku:
        sku = msku.group(1)

    # Disponibilite / inventaire (souvent "En inventaire" ou "Inventaire epuise")
    availability = None
    if re.search(r"Inventaire\s+epuise", text, re.I):
        availability = "Inventaire epuise"
    elif re.search(r"En\s+inventaire", text, re.I):
        availability = "En inventaire"

    # Prix: Canac affiche souvent "Prix liquidation / Prix regulier"
    # Exemple apercu: "349,00 $ ... 395,00 $"
    prices = re.findall(r"(\d[\d\s]*[.,]\d{2})\s*\$", text)
    # Heuristique: le premier = prix courant, le second = prix regulier
    sale_price = parse_price(prices[0] + " $") if len(prices) >= 1 else None
    reg_price = parse_price(prices[1] + " $") if len(prices) >= 2 else None

    discount_pct = None
    if sale_price and reg_price and reg_price > 0 and sale_price <= reg_price:
        discount_pct = round((1 - (sale_price / reg_price)) * 100, 2)

    return {
        "name": name,
        "sku": sku,
        "price_regular": reg_price,
        "price_sale": sale_price,
        "discount_pct": discount_pct,
        "availability": availability,
        "url": url,
        "image": image_url,
        "raw_text": text,  # utile pour debug; tu peux enlever si tu veux
    }


def scrape_canac_50_plus(output_csv="canac_50plus.csv", max_pages=300, sleep_s=1.2):
    rows = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for page in range(1, max_pages + 1):
        url = START_URL + f"&currentPage={page}"
        r = session.get(url, timeout=30)
        if r.status_code != 200:
            print(f"Page {page}: HTTP {r.status_code} -> stop")
            break

        blocks = find_products_on_page(r.text)
        if not blocks:
            print(f"Page {page}: 0 produit detecte -> stop")
            break

        page_count = 0
        for b in blocks:
            p = extract_product(b)

            # filtre >= 50% (et seulement si % calculable)
            if p["discount_pct"] is not None and p["discount_pct"] >= 50:
                rows.append(p)
                page_count += 1

        print(f"Page {page}: {len(blocks)} blocs, {page_count} produits >=50%")
        time.sleep(sleep_s)

    # Ecriture CSV
    fieldnames = [
        "name",
        "sku",
        "price_regular",
        "price_sale",
        "discount_pct",
        "availability",
        "url",
        "image",
    ]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fieldnames})

    print(f"OK: {len(rows)} produits >=50% ecrits dans {output_csv}")


if __name__ == "__main__":
    scrape_canac_50_plus()
