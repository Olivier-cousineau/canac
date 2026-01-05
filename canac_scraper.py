import csv
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

BASE = "https://www.canac.ca"
START_URL = "https://www.canac.ca/canac/fr/2/c/AUB"

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


def scrape_canac_50_plus(
    output_csv="data/canac/canac_aub_50plus.csv", max_pages=300, sleep_s=1.3
):
    rows = []
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=HEADERS["User-Agent"], locale="fr-CA"
        )
        page = context.new_page()

        for page_number in range(1, max_pages + 1):
            url = f"{START_URL}?currentPage={page_number}"
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except PlaywrightTimeoutError:
                print(f"Page {page_number}: timeout -> stop")
                if os.environ.get("GITHUB_ACTIONS") == "true":
                    print(
                        "Le site peut bloquer les IP datacenter; tester aussi en local"
                    )
                break

            status = response.status if response else None
            if status == 403:
                print(f"Page {page_number}: HTTP 403 -> stop")
                if os.environ.get("GITHUB_ACTIONS") == "true":
                    print(
                        "Le site peut bloquer les IP datacenter; tester aussi en local"
                    )
                break
            if status and status != 200:
                print(f"Page {page_number}: HTTP {status} -> stop")
                break

            try:
                page.wait_for_selector("text=Code produit", timeout=20000)
            except PlaywrightTimeoutError:
                print(f"Page {page_number}: aucun produit detecte -> stop")
                if os.environ.get("GITHUB_ACTIONS") == "true":
                    print(
                        "Le site peut bloquer les IP datacenter; tester aussi en local"
                    )
                break

            html = page.content()
            blocks = find_products_on_page(html)
            if not blocks:
                print(f"Page {page_number}: 0 produit detecte -> stop")
                break

            page_count = 0
            for b in blocks:
                p = extract_product(b)

                if p["discount_pct"] is not None and p["discount_pct"] >= 50:
                    rows.append(p)
                    page_count += 1

            print(
                f"Page {page_number}: {len(blocks)} produits détectés | "
                f"{page_count} gardés (>=50%)"
            )
            time.sleep(sleep_s)

        context.close()
        browser.close()

    # Ecriture CSV
    fieldnames = [
        "Nom",
        "Image",
        "Prix original",
        "Prix réduit",
        "% rabais",
        "Disponibilité",
        "Lien",
        "SKU",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "Nom": r.get("name"),
                    "Image": r.get("image"),
                    "Prix original": r.get("price_regular"),
                    "Prix réduit": r.get("price_sale"),
                    "% rabais": r.get("discount_pct"),
                    "Disponibilité": r.get("availability"),
                    "Lien": r.get("url"),
                    "SKU": r.get("sku"),
                }
            )

    print(f"OK: {len(rows)} produits >=50% ecrits dans {output_path}")


if __name__ == "__main__":
    scrape_canac_50_plus()
