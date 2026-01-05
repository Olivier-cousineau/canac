"""
README
======
Installation:
    pip install -r requirements.txt

Exécution:
    python scripts/scrape_canac_aub_50plus.py

Le script génère:
    data/canac/canac_aub_50plus.csv
    data/canac/canac_aub_50plus.json (optionnel)
"""

from __future__ import annotations

import csv
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.canac.ca"
START_URL = "https://www.canac.ca/canac/fr/2/c/AUB"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8",
}

OUTPUT_DIR = Path("data/canac")
CSV_PATH = OUTPUT_DIR / "canac_aub_50plus.csv"
JSON_PATH = OUTPUT_DIR / "canac_aub_50plus.json"


@dataclass
class Product:
    name: str
    image: str
    price_original: float
    price_reduced: float
    discount_pct: float
    availability: str
    link: str
    sku: str


def parse_price(text: str) -> float | None:
    if not text:
        return None
    value = (
        text.replace("\xa0", " ")
        .replace("$", "")
        .replace(" ", "")
        .strip()
    )
    match = re.findall(r"\d+(?:[.,]\d+)?", value)
    if not match:
        return None
    try:
        return float(match[0].replace(",", "."))
    except ValueError:
        return None


def extract_prices(block_text: str) -> tuple[float | None, float | None]:
    prices = re.findall(r"(\d[\d\s]*[.,]\d{2})\s*\$", block_text)
    parsed = [parse_price(price) for price in prices]
    parsed = [price for price in parsed if price is not None]
    if len(parsed) < 2:
        return None, None
    sale_price = min(parsed)
    regular_price = max(parsed)
    if sale_price == regular_price:
        return None, None
    return regular_price, sale_price


def find_product_blocks(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    code_nodes = soup.find_all(string=re.compile(r"Code produit\s*:", re.I))
    product_blocks = []
    for node in code_nodes:
        parent = node
        for _ in range(6):
            if parent and parent.name in ("article", "li", "div"):
                if parent.find("a", href=True):
                    product_blocks.append(parent)
                    break
            parent = parent.parent
    unique = []
    seen = set()
    for block in product_blocks:
        marker = str(block)[:300]
        if marker not in seen:
            seen.add(marker)
            unique.append(block)
    return unique


def parse_availability(text: str) -> str:
    if re.search(r"Inventaire\s+epuise", text, re.I):
        return "Inventaire epuise"
    if re.search(r"En\s+inventaire", text, re.I):
        return "En inventaire"
    return ""


def extract_product(block) -> Product | None:
    text = " ".join(block.get_text(" ", strip=True).split())
    regular_price, sale_price = extract_prices(text)
    if regular_price is None or sale_price is None:
        return None

    discount_pct = round((1 - (sale_price / regular_price)) * 100, 2)
    if discount_pct < 50:
        return None

    link_tag = block.find("a", href=True)
    link = urljoin(BASE, link_tag["href"]) if link_tag else ""
    name = link_tag.get_text(" ", strip=True) if link_tag else ""

    image_tag = block.find("img")
    image = urljoin(BASE, image_tag["src"]) if image_tag and image_tag.get("src") else ""

    sku_match = re.search(r"Code produit\s*:\s*([A-Z0-9-]+)", text, re.I)
    sku = sku_match.group(1) if sku_match else ""

    availability = parse_availability(text)

    if not name:
        return None

    return Product(
        name=name,
        image=image,
        price_original=regular_price,
        price_reduced=sale_price,
        discount_pct=discount_pct,
        availability=availability,
        link=link,
        sku=sku,
    )


def iter_products(session: requests.Session, max_pages: int = 300) -> Iterable[Product]:
    for page in range(1, max_pages + 1):
        url = f"{START_URL}?currentPage={page}"
        response = session.get(url, timeout=30)
        if response.status_code != 200:
            print(f"Page {page}: HTTP {response.status_code} -> stop")
            return

        blocks = find_product_blocks(response.text)
        kept = 0
        for block in blocks:
            product = extract_product(block)
            if product:
                kept += 1
                yield product

        print(f"Page {page}: {len(blocks)} produits détectés | {kept} gardés (>=50%)")

        if not blocks:
            return

        time.sleep(1.3)


def write_outputs(products: list[Product]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "Nom du produit",
                "Image",
                "Prix original",
                "Prix réduit",
                "Pourcentage rabais",
                "Disponibilité",
                "Lien",
                "SKU",
            ]
        )
        for product in products:
            writer.writerow(
                [
                    product.name,
                    product.image,
                    f"{product.price_original:.2f}",
                    f"{product.price_reduced:.2f}",
                    f"{product.discount_pct:.2f}",
                    product.availability,
                    product.link,
                    product.sku,
                ]
            )

    with JSON_PATH.open("w", encoding="utf-8") as json_file:
        json.dump([asdict(product) for product in products], json_file, ensure_ascii=False, indent=2)


def main() -> None:
    session = requests.Session()
    session.headers.update(HEADERS)

    products = list(iter_products(session))
    write_outputs(products)

    print(f"Total produits sauvegardés: {len(products)}")
    print(f"CSV: {CSV_PATH}")
    print(f"JSON: {JSON_PATH}")


if __name__ == "__main__":
    main()
