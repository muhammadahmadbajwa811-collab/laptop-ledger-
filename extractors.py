"""Turn a web page into laptop records. Strategies are tried together; the one yielding most wins:
   1. JSON-LD / embedded JSON (Next.js etc.)   2. Shopify products.json   3. repeated product cards in HTML
"""
import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from parsers import PRICE_RE, clean, normalize, parse_price

NAME_KEYS = ("name", "title", "product_name", "productName")
PRICE_KEYS = ("price", "selling_price", "sale_price", "current_price", "final_price",
              "special_price", "discounted_price", "min_price", "lowPrice")
URL_KEYS = ("url", "link", "product_url", "permalink", "canonical_url", "slug", "handle")
TEXT_KEYS = ("description", "body_html", "short_description", "product_type", "tags", "specs", "specifications")


def make_soup(html):
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def _first(d, keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return None


def _walk(obj):
    stack = [obj]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            yield o
            stack.extend(o.values())
        elif isinstance(o, list):
            stack.extend(o)


def from_json(obj, base, source):
    out = []
    for d in _walk(obj):
        name = _first(d, NAME_KEYS)
        if not isinstance(name, str):
            continue
        price = _first(d, PRICE_KEYS)
        offers = d.get("offers")
        if price is None and offers:
            o = offers[0] if isinstance(offers, list) and offers else offers
            if isinstance(o, dict):
                price = _first(o, ("price", "lowPrice"))
        if price is None or isinstance(price, (dict, list)):
            continue
        brand = d.get("brand") or d.get("brand_name") or d.get("vendor")
        if isinstance(brand, dict):
            brand = brand.get("name")
        agg = d.get("aggregateRating") if isinstance(d.get("aggregateRating"), dict) else {}
        rating = _first(d, ("rating", "avg_rating", "average_rating", "rating_value", "ratingValue")) or agg.get("ratingValue")
        if isinstance(rating, dict):
            rating = rating.get("average") or rating.get("value")
        reviews = (_first(d, ("reviews_count", "review_count", "reviewCount", "rating_count", "total_reviews", "num_reviews"))
                   or agg.get("reviewCount") or agg.get("ratingCount"))
        text = " ".join(
            (" ".join(map(str, d[k])) if isinstance(d.get(k), list) else str(d.get(k)))
            for k in TEXT_KEYS if isinstance(d.get(k), (str, list)))
        rec = normalize({"name": name, "price": price, "url": _first(d, URL_KEYS), "brand": brand,
                         "rating": rating if not isinstance(rating, (dict, list)) else None,
                         "reviews": reviews if not isinstance(reviews, (dict, list)) else None,
                         "text": text}, source, base)
        if rec:
            out.append(rec)
    return out


def from_embedded_json(soup, base, source):
    out = []
    for s in soup.find_all("script"):
        t = (s.get("type") or "").lower()
        if s.get("id") == "__NEXT_DATA__" or "json" in t:
            try:
                out.extend(from_json(json.loads(s.string or s.get_text() or ""), base, source))
            except (ValueError, TypeError):
                continue
    return out


def from_shopify(data, base, source):
    origin = "{0.scheme}://{0.netloc}".format(urlparse(base))
    out = []
    for p in data.get("products", []):
        prices = [v.get("price") for v in p.get("variants", []) if parse_price(v.get("price"))]
        text = " ".join([str(p.get("body_html", "")), " ".join(p.get("tags", []) if isinstance(p.get("tags"), list) else [str(p.get("tags", ""))]),
                         p.get("product_type", "")])
        rec = normalize({"name": p.get("title"), "price": min(prices, key=lambda x: float(x)) if prices else None,
                         "url": f"{origin}/products/{p.get('handle')}", "brand": p.get("vendor"), "text": text},
                        source, base)
        if rec:
            out.append(rec)
    return out


def from_cards(soup, base, source):
    """Detect the most common repeated block that holds a link and a price, and read it as a product card."""
    groups = {}
    for el in soup.find_all(["div", "li", "article"]):
        a = el.find("a", href=True)
        if not a:
            continue
        txt = el.get_text(" ", strip=True)
        if not txt or len(txt) > 700:
            continue
        n = len(PRICE_RE.findall(txt))
        if not 1 <= n <= 3:
            continue
        groups.setdefault((el.name, tuple(el.get("class", []))), []).append((el, txt))
    best = [g for g in groups.values() if len(g) >= 3]
    if not best:
        return []
    cards = max(best, key=lambda g: (len(g), -sum(len(t) for _, t in g) / len(g)))
    out = []
    for el, txt in cards:
        head = el.find(re.compile(r"^h[1-6]$"))
        anchors = [a for a in el.find_all("a", href=True) if a.get_text(strip=True)]
        link = (head.find("a", href=True) if head else None) or (max(anchors, key=lambda a: len(a.get_text())) if anchors else el.find("a", href=True))
        title = (head.get_text(" ", strip=True) if head else "") or (link.get("title") if link else "") \
            or (link.get_text(" ", strip=True) if link else "")
        if not title:
            img = el.find("img", alt=True)
            title = img["alt"] if img else ""
        prices = [parse_price(p) for p in PRICE_RE.findall(txt)]
        prices = [p for p in prices if p]
        rating = re.search(r"(\d(?:\.\d)?)\s*(?:/\s*5|out of 5|stars?)", txt, re.I)
        reviews = re.search(r"\(?(\d[\d,]*)\)?\s*(?:reviews?|ratings?)", txt, re.I)
        rec = normalize({"name": title, "price": min(prices) if prices else None, "url": link["href"] if link else "",
                         "rating": rating.group(1) if rating else None,
                         "reviews": reviews.group(1) if reviews else None, "text": txt}, source, base)
        if rec:
            out.append(rec)
    return out


def extract_products(html, url, source):
    """Return (records, strategy_name) using whichever strategy finds the most laptops."""
    soup = make_soup(html)
    results = {"embedded JSON / JSON-LD": from_embedded_json(soup, url, source),
               "product cards": from_cards(soup, url, source)}
    name = max(results, key=lambda k: len(results[k]))
    return results[name], name


# ------------------------------------------------------------ pagination
_PAGE_RE = re.compile(r"([?&])(p|page)=(\d+)")
_PATH_RE = re.compile(r"/page[/-](\d+)")


def page_number(url):
    m = _PAGE_RE.search(url) or _PATH_RE.search(url)
    return int(m.group(m.lastindex)) if m else 1


def with_page(url, n):
    if _PAGE_RE.search(url):
        return _PAGE_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}={n}", url, count=1)
    if _PATH_RE.search(url):
        return _PATH_RE.sub(lambda m: m.group(0).replace(m.group(1), str(n)), url, count=1)
    return url + ("&" if "?" in url else "?") + f"page={n}"


def find_next(html, url):
    """Next page URL: rel=next, a 'next' link, a link to page+1, else a guessed ?page=N+1."""
    soup = make_soup(html)
    cur = page_number(url)
    tag = soup.find("link", rel="next") or soup.find("a", rel="next")
    if tag and tag.get("href"):
        return urljoin(url, tag["href"])
    for a in soup.find_all("a", href=True):
        if clean(a.get_text()).lower() in ("next", "next page", "›", "»", ">", "next »"):
            return urljoin(url, a["href"])
    for a in soup.find_all("a", href=True):
        full = urljoin(url, a["href"])
        if page_number(full) == cur + 1 and (_PAGE_RE.search(full) or _PATH_RE.search(full)):
            return full
    return with_page(url, cur + 1)
