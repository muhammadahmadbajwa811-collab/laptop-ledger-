"""Text parsing + record normalisation + CSV helpers for laptop data."""
import csv
import re
from urllib.parse import urljoin

# key, header label, kind ("str" / "num")
COLUMNS = [
    ("name", "Name", "str"),
    ("brand", "Brand", "str"),
    ("price", "Price", "num"),
    ("rating", "Rating", "num"),
    ("reviews", "Reviews", "num"),
    ("cpu", "Processor", "str"),
    ("ram", "RAM (GB)", "num"),
    ("storage", "Storage (GB)", "num"),
    ("screen", "Screen (in)", "num"),
    ("gpu", "Graphics", "str"),
    ("source", "Source", "str"),
    ("url", "URL", "str"),
]
KEYS = [c[0] for c in COLUMNS]
KIND = {c[0]: c[2] for c in COLUMNS}
LABEL = {c[0]: c[1] for c in COLUMNS}

BRANDS = ["HP", "Dell", "Lenovo", "Asus", "Acer", "MSI", "Apple", "Razer", "Microsoft",
          "Samsung", "Huawei", "Infinix", "Gigabyte", "LG", "Toshiba", "Alienware",
          "Honor", "Xiaomi", "Chuwi", "Haier", "Dynabook", "Tecno", "Realme", "Fujitsu"]
_BRAND_RE = re.compile(r"\b(" + "|".join(re.escape(b) for b in BRANDS) + r")\b", re.I)

PRICE_RE = re.compile(r"(?:rs\.?|pkr|₨|usd|\$|£|€)\s*([\d][\d,]*(?:\.\d+)?)", re.I)
_MEM_RE = re.compile(
    r"(\d{1,4})\s*(GB|TB)\b(?:\s*(GDDR\d\w*|LPDDR\d\w*|DDR\d\w*|RAM|SSD|HDD|NVME|EMMC|M\.2|PCIE|STORAGE|MEMORY|UNIFIED))?",
    re.I)
_CPU_RE = re.compile(
    r"(Core\s*Ultra\s*[3579](?:\s*\d{3}\w*)?|Core\s*i[3579](?:[-\s]\d{4,5}\w*|\s*\d{1,2}(?:th|st|nd|rd)\s*Gen)?|\bi[3579]-\d{4,5}\w*|Ryzen\s*[3579](?:\s*\d{4}\w*)?|"
    r"Apple\s*M[1-5]\s*(?:Pro|Max|Ultra)?|\bM[1-5]\s*(?:Pro|Max|Ultra)?\b|Celeron\s*\w*|Pentium\s*\w*|"
    r"Athlon\s*\w*|Snapdragon\s*(?:X\s*)?\w*|Core\s*[3579]\s*\d{3}\w*)", re.I)
_GPU_RE = re.compile(
    r"(RTX\s*\d{4}\w*(?:\s*Ti)?|GTX\s*\d{3,4}\w*(?:\s*Ti)?|Radeon\s*RX\s*\w+|Radeon\s*\d{3}\w*|"
    r"Iris\s*Xe|Intel\s*UHD|Intel\s*Arc\s*\w*|MX\s*\d{3}|Quadro\s*\w+|RTX\s*A\d{3,4})", re.I)
_SCREEN_RE = re.compile(r"\b(1[0-9](?:\.\d{1,2})?|20(?:\.\d)?)\s*(?:\"|”|″|'')|\b(1[0-9](?:\.\d{1,2})?)\s*-?\s*inch", re.I)
ACCESSORY_RE = re.compile(r"\b(bag|backpack|sleeve|charger|adapter|adaptor|mouse|keyboard|cooler|cooling pad|"
                          r"skin|screen protector|docking|dock|hub|cable|stand|headset|battery)\b", re.I)
LAPTOP_RE = re.compile(r"laptop|notebook|macbook|chromebook|thinkpad|ideapad|legion|vivobook|zenbook|inspiron|"
                       r"latitude|pavilion|probook|elitebook|omen|victus|aspire|swift|nitro|predator|katana|"
                       r"\bROG\b|\bTUF\b|surface|\bXPS\b|yoga|\bLOQ\b|envy|spectre|zbook|\bgram\b|galaxy book|"
                       r"thinkbook|vostro|inspire|\bmodern\b|\bprestige\b", re.I)


def clean(v):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(v))).strip() if v not in (None, "") else ""


def to_float(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"\d+(?:\.\d+)?", str(v).replace(",", ""))
    return float(m.group()) if m else None


def parse_price(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    s = str(v)
    m = PRICE_RE.search(s)
    num = m.group(1) if m else s
    val = to_float(num.replace(",", ""))
    return val if val and val > 0 else None


def to_gb(v):
    """'16GB' -> 16, '1TB' -> 1024, 512 -> 512."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(TB|GB)?", str(v), re.I)
    if not m:
        return None
    val = float(m.group(1))
    return val * 1024 if (m.group(2) or "").upper() == "TB" else val


def to_rating(v):
    r = to_float(v)
    return r if r and 0 < r <= 5 else None


def to_int(v):
    r = to_float(v)
    return int(r) if r is not None else None


def guess_brand(name):
    if re.search(r"macbook|\bimac\b", name, re.I):
        return "Apple"
    m = _BRAND_RE.search(name)
    return m.group(1).upper() if m and m.group(1).lower() in ("hp", "msi", "lg") else (m.group(1).title() if m else "")


def parse_specs(text):
    """Pull RAM / storage / CPU / GPU / screen out of free text (titles, descriptions)."""
    out = {}
    for m in _MEM_RE.finditer(text):
        val, unit, tag = float(m.group(1)), m.group(2).upper(), (m.group(3) or "").upper()
        gb = val * 1024 if unit == "TB" else val
        if tag.startswith("GDDR"):
            continue
        if tag in ("SSD", "HDD", "NVME", "EMMC", "M.2", "PCIE", "STORAGE") or unit == "TB" or gb >= 128:
            out.setdefault("storage", gb)
        elif tag.startswith(("DDR", "LPDDR")) or tag in ("RAM", "MEMORY", "UNIFIED") or gb <= 64:
            out.setdefault("ram", gb)
    m = _CPU_RE.search(text)
    if m:
        out["cpu"] = re.sub(r"\s+", " ", m.group(1)).strip()
    m = _GPU_RE.search(text)
    if m:
        out["gpu"] = re.sub(r"\s+", " ", m.group(1)).strip()
    m = _SCREEN_RE.search(text)
    if m:
        v = float(m.group(1) or m.group(2))
        if 10 <= v <= 20:
            out["screen"] = v
    return out


def normalize(raw, source="", base=""):
    """raw dict (name, price, url, rating, reviews, text, ...) -> clean record or None."""
    name = clean(raw.get("name"))
    if len(name) < 4:
        return None
    if ACCESSORY_RE.search(name) and not LAPTOP_RE.search(name):
        return None
    sp = parse_specs(name + " " + clean(raw.get("text")))
    url = ""
    if raw.get("url"):
        url = urljoin(base, str(raw["url"])) if base else str(raw["url"])
    rec = {
        "name": name,
        "brand": guess_brand(name) or clean(raw.get("brand")) or "Unknown",
        "price": parse_price(raw.get("price")),
        "rating": to_rating(raw.get("rating")),
        "reviews": to_int(raw.get("reviews")),
        "cpu": clean(raw.get("cpu")) or sp.get("cpu", ""),
        "ram": to_gb(raw.get("ram")) or sp.get("ram"),
        "storage": to_gb(raw.get("storage")) or sp.get("storage"),
        "screen": to_float(raw.get("screen")) or sp.get("screen"),
        "gpu": clean(raw.get("gpu")) or sp.get("gpu", ""),
        "source": source,
        "url": url,
    }
    return rec


def record_key(r):
    return r["url"] or (r["name"].lower() + "|" + str(r["price"]))


# ---------------------------------------------------------------- CSV
def save_csv(path, records):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KEYS)
        w.writeheader()
        for r in records:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in KEYS})


def load_csv(path):
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rec = {}
            for k in KEYS:
                v = row.get(k, "")
                rec[k] = (to_float(v) if v != "" else None) if KIND[k] == "num" else v
            if rec["reviews"] is not None:
                rec["reviews"] = int(rec["reviews"])
            out.append(rec)
    return out


_SYNONYMS = {
    "name": ("name", "title", "product", "model", "laptop"),
    "brand": ("brand", "company", "manufacturer"),
    "price": ("price",),
    "rating": ("rating", "stars"),
    "reviews": ("review", "votes"),
    "cpu": ("processor", "cpu"),
    "ram": ("ram", "memory"),
    "storage": ("storage", "ssd", "hdd", "disk"),
    "screen": ("screen", "display", "inches"),
    "gpu": ("gpu", "graphic"),
    "url": ("url", "link"),
}


def import_csv(path, source="Imported CSV"):
    """Load an arbitrary laptop CSV (e.g. from Kaggle) by guessing which header means what."""
    out = []
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        heads = reader.fieldnames or []
        mapping = {}
        for key, words in _SYNONYMS.items():
            for h in heads:
                if any(w in h.lower() for w in words) and h not in mapping.values():
                    mapping[key] = h
                    break
        for row in reader:
            raw = {k: row.get(h) for k, h in mapping.items()}
            raw["text"] = " ".join(str(v) for v in row.values() if v)
            if not raw.get("name"):
                raw["name"] = " ".join(str(row.get(h, "")) for h in heads[:3])
            rec = normalize(raw, source)
            if rec:
                out.append(rec)
    return out
