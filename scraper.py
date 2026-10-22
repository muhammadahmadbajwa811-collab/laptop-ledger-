"""Background scraper. Runs in a QThread so the UI stays responsive; supports pause / resume / stop."""
import threading
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from PyQt5.QtCore import QThread, pyqtSignal

import extractors
from parsers import record_key

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

PRESETS = {
    "PakLap": "https://www.paklap.pk/laptops.html",
    "PriceOye": "https://priceoye.pk/laptops",
}


class ScraperWorker(QThread):
    batch = pyqtSignal(list)       # new, de-duplicated records
    log = pyqtSignal(str)
    finished_with = pyqtSignal(str)

    def __init__(self, seeds, target, delay, known_keys, current_total, respect_robots=True, parent=None):
        super().__init__(parent)
        self.seeds, self.target, self.delay = seeds, target, delay
        self.known = set(known_keys)
        self.total = current_total          # records already held (so the target counts everything)
        self.respect_robots = respect_robots
        self._running = threading.Event()
        self._running.set()
        self._stop = False
        self._robots = {}
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ---- controls (called from the UI thread)
    def pause(self):
        self._running.clear()
        self.log.emit("Paused.")

    def resume(self):
        self._running.set()
        self.log.emit("Resumed.")

    def stop(self):
        self._stop = True
        self._running.set()

    # ---- helpers
    def _checkpoint(self):
        """Block while paused; return False if we should stop."""
        while not self._running.wait(0.2):
            if self._stop:
                return False
        return not self._stop

    def _sleep(self, seconds):
        end = time.time() + seconds
        while time.time() < end and not self._stop:
            time.sleep(0.05)

    def _allowed(self, url):
        if not self.respect_robots:
            return True
        p = urlparse(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self._robots:
            rp = RobotFileParser()
            try:
                r = self.session.get(origin + "/robots.txt", timeout=10)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except requests.RequestException:
                rp.parse([])
            self._robots[origin] = rp
        return self._robots[origin].can_fetch(HEADERS["User-Agent"], url)

    def _get(self, url):
        for attempt in range(3):
            if self._stop:
                return None
            try:
                r = self.session.get(url, timeout=20)
                if r.status_code == 200:
                    return r
                self.log.emit(f"HTTP {r.status_code} for {url}")
                if r.status_code in (403, 429, 503):
                    self._sleep(3 * (attempt + 1))
                else:
                    return None
            except requests.RequestException as e:
                self.log.emit(f"Network error ({type(e).__name__}); retrying…")
                self._sleep(2 ** attempt)
        return None

    def _emit_new(self, records):
        new = []
        for r in records:
            k = record_key(r)
            if k not in self.known and self.total + len(new) < self.target:
                self.known.add(k)
                new.append(r)
        if new:
            self.total += len(new)
            self.batch.emit(new)
        return len(new)

    # ---- main loop
    def run(self):
        reason = "Finished."
        try:
            for seed in self.seeds:
                if self._stop or self.total >= self.target:
                    break
                self.log.emit(f"Starting {seed}")
                self._scrape_site(seed)
            reason = "Stopped." if self._stop else ("Target reached." if self.total >= self.target else "Finished: no more pages.")
        except Exception as e:  # never let the thread die silently
            reason = f"Stopped on error: {e}"
        self.finished_with.emit(reason)

    def _scrape_site(self, seed):
        source = urlparse(seed).netloc.replace("www.", "")
        if self._try_shopify(seed, source):
            return
        url, seen, empty = seed, set(), 0
        while url and url not in seen and self.total < self.target:
            if not self._checkpoint():
                return
            seen.add(url)
            if not self._allowed(url):
                self.log.emit(f"robots.txt disallows {url}")
                return
            r = self._get(url)
            if r is None:
                return
            recs, how = extractors.extract_products(r.text, url, source)
            added = self._emit_new(recs)
            self.log.emit(f"Page {extractors.page_number(url)}: {len(recs)} found, {added} new via {how}  [{self.total}/{self.target}]")
            if recs == [] and extractors.page_number(url) == 1:
                self.log.emit("No products detected. The site may load items with JavaScript or block bots.")
                return
            empty = empty + 1 if added == 0 else 0
            if empty >= 2:
                return
            url = extractors.find_next(r.text, url)
            self._sleep(self.delay)

    def _try_shopify(self, seed, source):
        """Shopify stores expose /collections/<x>/products.json — much faster and cleaner than HTML."""
        p = urlparse(seed)
        base = f"{p.scheme}://{p.netloc}{p.path.rstrip('/')}"
        if "/collections/" not in p.path and not p.path.endswith("products.json"):
            return False
        endpoint = base if base.endswith("products.json") else base + "/products.json"
        page = 1
        while self.total < self.target:
            if not self._checkpoint():
                return True
            try:
                r = self.session.get(endpoint, params={"limit": 250, "page": page}, timeout=20)
                data = r.json()
            except (requests.RequestException, ValueError):
                return page > 1
            if not isinstance(data, dict) or "products" not in data:
                return page > 1
            if not data["products"]:
                return True
            recs = extractors.from_shopify(data, seed, source)
            added = self._emit_new(recs)
            self.log.emit(f"Shopify page {page}: {len(recs)} found, {added} new  [{self.total}/{self.target}]")
            page += 1
            self._sleep(self.delay)
        return True
