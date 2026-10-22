"""Sorting algorithms written from scratch. Each sorts a list of (key, payload) tuples in place by key,
counting comparisons and swaps (a 'swap' is a swap, shift or element move/write)."""
import math
import threading
import time


class Cancelled(Exception):
    pass


class Stats:
    __slots__ = ("comparisons", "swaps")

    def __init__(self):
        self.comparisons = 0
        self.swaps = 0


def _check(stop):
    if stop and stop.is_set():
        raise Cancelled()


def bubble_sort(a, st, stop):
    n, c, s = len(a), 0, 0
    try:
        for i in range(n - 1):
            _check(stop)
            swapped = False
            for j in range(n - 1 - i):
                c += 1
                if a[j][0] > a[j + 1][0]:
                    a[j], a[j + 1] = a[j + 1], a[j]
                    s += 1
                    swapped = True
            if not swapped:
                break
    finally:
        st.comparisons += c
        st.swaps += s




def insertion_sort(a, st, stop):
    c = s = 0
    try:
        for i in range(1, len(a)):
            if i % 256 == 0:
                _check(stop)
            x, j = a[i], i - 1
            while j >= 0:
                c += 1
                if a[j][0] > x[0]:
                    a[j + 1] = a[j]
                    s += 1
                    j -= 1
                else:
                    break
            a[j + 1] = x
    finally:
        st.comparisons += c
        st.swaps += s


def _merge(a, lo, mid, hi, st):
    """Merge a[lo:mid] and a[mid:hi] (stable)."""
    left, right = a[lo:mid], a[mid:hi]
    i = j = 0
    k, c, s = lo, 0, 0
    while i < len(left) and j < len(right):
        c += 1
        if right[j][0] < left[i][0]:
            a[k] = right[j]
            j += 1
        else:
            a[k] = left[i]
            i += 1
        k += 1
        s += 1
    while i < len(left):
        a[k] = left[i]
        i += 1
        k += 1
        s += 1
    while j < len(right):
        a[k] = right[j]
        j += 1
        k += 1
        s += 1
    st.comparisons += c
    st.swaps += s


def merge_sort(a, st, stop):
    def rec(lo, hi):
        if hi - lo < 2:
            return
        _check(stop)
        mid = (lo + hi) // 2
        rec(lo, mid)
        rec(mid, hi)
        _merge(a, lo, mid, hi, st)
    rec(0, len(a))


def quick_sort(a, st, stop):
    """Iterative 3-way quicksort (safe on sorted input and on columns full of duplicates)."""
    c = s = 0
    stack = [(0, len(a) - 1)]
    try:
        while stack:
            _check(stop)
            lo, hi = stack.pop()
            if lo >= hi:
                continue
            pivot = a[(lo + hi) // 2][0]
            lt, i, gt = lo, lo, hi
            while i <= gt:
                k = a[i][0]
                c += 1
                if k < pivot:
                    a[lt], a[i] = a[i], a[lt]
                    lt += 1
                    i += 1
                    s += 1
                else:
                    c += 1
                    if k > pivot:
                        a[i], a[gt] = a[gt], a[i]
                        gt -= 1
                        s += 1
                    else:
                        i += 1
            stack.append((lo, lt - 1))
            stack.append((gt + 1, hi))
    finally:
        st.comparisons += c
        st.swaps += s












def selection_sort(a, st, stop):
    """Selection sort: repeatedly finds the minimum element and swaps it into place."""
    n, c, s = len(a), 0, 0
    try:
        for i in range(n - 1):
            if i % 128 == 0:
                _check(stop)
            min_idx = i
            for j in range(i + 1, n):
                c += 1
                if a[j][0] < a[min_idx][0]:
                    min_idx = j
            if min_idx != i:
                a[i], a[min_idx] = a[min_idx], a[i]
                s += 1
    finally:
        st.comparisons += c
        st.swaps += s


def count_sort(a, st, stop):
    """Counting sort: counts key frequencies and reconstructs sorted order stably.
    Supports numbers (integer/scaled), strings, and multi-level keys with missing INF."""
    n = len(a)
    if n < 2:
        return
    c = s = 0
    try:
        _check(stop)
        valid = []
        infs = []
        for item in a:
            k = item[0]
            if k == INF or k == "\U0010ffff" or k == (10**9,):
                infs.append(item)
            else:
                valid.append(item)
            s += 1

        if not valid:
            return

        all_numeric = all(isinstance(x[0], (int, float)) for x in valid)
        if all_numeric:
            min_val = min(x[0] for x in valid)
            max_val = max(x[0] for x in valid)
            c += 2 * len(valid)
            has_float = any(isinstance(x[0], float) and not x[0].is_integer() for x in valid)
            scale = 100 if has_float else 1
            span = int(round((max_val - min_val) * scale))

            if span <= 2_000_000:
                counts = [0] * (span + 1)
                for item in valid:
                    idx = int(round((item[0] - min_val) * scale))
                    counts[idx] += 1
                for i in range(1, len(counts)):
                    counts[i] += counts[i - 1]
                output = [None] * len(valid)
                for item in reversed(valid):
                    idx = int(round((item[0] - min_val) * scale))
                    counts[idx] -= 1
                    output[counts[idx]] = item
                    s += 1
                for i, item in enumerate(output):
                    a[i] = item
                    s += 1
                for i, item in enumerate(infs):
                    a[len(valid) + i] = item
                    s += 1
                return

        freq = {}
        for item in valid:
            k = item[0]
            freq[k] = freq.get(k, 0) + 1
        sorted_keys = sorted(freq.keys())
        c += len(sorted_keys) * int(math.log2(max(1, len(sorted_keys))))
        pos = {}
        cur = 0
        for k in sorted_keys:
            pos[k] = cur
            cur += freq[k]
        output = [None] * len(valid)
        for item in valid:
            k = item[0]
            output[pos[k]] = item
            pos[k] += 1
            s += 1
        for i, item in enumerate(output):
            a[i] = item
            s += 1
        for i, item in enumerate(infs):
            a[len(valid) + i] = item
            s += 1
    finally:
        st.comparisons += c
        st.swaps += s


counting_sort = count_sort


def radix_sort(a, st, stop):
    """LSD Radix Sort: stably sorts digit-by-digit or character-by-character."""
    n = len(a)
    if n < 2:
        return
    c = s = 0
    try:
        _check(stop)
        valid = []
        infs = []
        for item in a:
            k = item[0]
            if k == INF or k == "\U0010ffff" or k == (10**9,):
                infs.append(item)
            else:
                valid.append(item)
            s += 1

        if not valid:
            return

        all_numeric = all(isinstance(x[0], (int, float)) for x in valid)
        if all_numeric:
            min_val = min(x[0] for x in valid)
            c += len(valid)
            has_float = any(isinstance(x[0], float) and not x[0].is_integer() for x in valid)
            scale = 100 if has_float else 1
            keys = [int(round((x[0] - min_val) * scale)) for x in valid]
            max_val = max(keys)
            c += len(keys)

            exp = 1
            cur_items = list(zip(valid, keys))
            while max_val // exp > 0:
                _check(stop)
                buckets = [[] for _ in range(10)]
                for it, k in cur_items:
                    digit = (k // exp) % 10
                    buckets[digit].append((it, k))
                    s += 1
                cur_items = []
                for b in buckets:
                    for entry in b:
                        cur_items.append(entry)
                        s += 1
                exp *= 10
            for i, (it, _) in enumerate(cur_items):
                a[i] = it
                s += 1
            for i, it in enumerate(infs):
                a[len(valid) + i] = it
                s += 1
            return

        all_strings = all(isinstance(x[0], str) for x in valid)
        if all_strings:
            max_len = max(len(x[0]) for x in valid)
            cur = list(valid)
            for pos in range(max_len - 1, -1, -1):
                if pos % 4 == 0:
                    _check(stop)
                buckets = {}
                for it in cur:
                    ch = ord(it[0][pos]) if pos < len(it[0]) else 0
                    if ch not in buckets:
                        buckets[ch] = []
                    buckets[ch].append(it)
                    s += 1
                cur = []
                for ch in sorted(buckets.keys()):
                    for it in buckets[ch]:
                        cur.append(it)
                        s += 1
            for i, it in enumerate(cur):
                a[i] = it
                s += 1
            for i, it in enumerate(infs):
                a[len(valid) + i] = it
                s += 1
            return

        if isinstance(valid[0][0], tuple):
            max_k_len = max(len(it[0]) for it in valid)
            cur = list(valid)
            for col_idx in range(max_k_len - 1, -1, -1):
                _check(stop)
                sentinel = -float('inf') if isinstance(valid[0][0][0], (int, float)) else ''
                buckets = {}
                for it in cur:
                    val = it[0][col_idx] if col_idx < len(it[0]) else sentinel
                    if val not in buckets:
                        buckets[val] = []
                    buckets[val].append(it)
                    s += 1
                cur = []
                for k in sorted(buckets.keys()):
                    for it in buckets[k]:
                        cur.append(it)
                        s += 1
            for i, it in enumerate(cur):
                a[i] = it
                s += 1
            for i, it in enumerate(infs):
                a[len(valid) + i] = it
                s += 1
            return

        insertion_sort(a, st, stop)
    finally:
        st.comparisons += c
        st.swaps += s


def bucket_sort(a, st, stop):
    """Bucket sort: distributes elements into buckets, sorts each with insertion_sort, and concatenates."""
    n = len(a)
    if n < 2:
        return
    c = s = 0
    try:
        _check(stop)
        valid = []
        infs = []
        for item in a:
            k = item[0]
            if k == INF or k == "\U0010ffff" or k == (10**9,):
                infs.append(item)
            else:
                valid.append(item)
            s += 1

        if not valid:
            return

        num_buckets = max(1, int(math.sqrt(len(valid))))
        buckets = [[] for _ in range(num_buckets)]

        all_numeric = all(isinstance(x[0], (int, float)) for x in valid)
        if all_numeric:
            min_val = min(x[0] for x in valid)
            max_val = max(x[0] for x in valid)
            c += 2 * len(valid)
            span = max_val - min_val
            if span == 0:
                buckets = [list(valid)]
            else:
                for item in valid:
                    norm = (item[0] - min_val) / span
                    b_idx = min(num_buckets - 1, int(norm * num_buckets))
                    buckets[b_idx].append(item)
                    s += 1
        elif all(isinstance(x[0], str) for x in valid):
            ords = [ord(x[0][0]) if x[0] else 0 for x in valid]
            min_ord, max_ord = min(ords), max(ords)
            c += 2 * len(valid)
            span = max_ord - min_ord
            if span == 0:
                buckets = [list(valid)]
            else:
                for item in valid:
                    ch = ord(item[0][0]) if item[0] else 0
                    norm = (ch - min_ord) / span
                    b_idx = min(num_buckets - 1, int(norm * num_buckets))
                    buckets[b_idx].append(item)
                    s += 1
        else:
            first_keys = sorted(set(x[0][0] if isinstance(x[0], tuple) else x[0] for x in valid))
            c += len(first_keys) * int(math.log2(max(1, len(first_keys))))
            span = len(first_keys) - 1
            if span <= 0:
                buckets = [list(valid)]
            else:
                key_map = {k: i for i, k in enumerate(first_keys)}
                for item in valid:
                    fk = item[0][0] if isinstance(item[0], tuple) else item[0]
                    norm = key_map[fk] / span
                    b_idx = min(num_buckets - 1, int(norm * num_buckets))
                    buckets[b_idx].append(item)
                    s += 1

        idx = 0
        for bucket in buckets:
            _check(stop)
            if bucket:
                sub_st = Stats()
                insertion_sort(bucket, sub_st, stop)
                c += sub_st.comparisons
                s += sub_st.swaps
                for item in bucket:
                    a[idx] = item
                    idx += 1
                    s += 1

        for item in infs:
            a[idx] = item
            idx += 1
            s += 1
    finally:
        st.comparisons += c
        st.swaps += s


# name -> (function, average, worst, stable)
ALGORITHMS = {
    "Bubble Sort": (bubble_sort, "O(n²)", "O(n²)", True),
    "Insertion Sort": (insertion_sort, "O(n²)", "O(n²)", True),
    "Selection Sort": (selection_sort, "O(n²)", "O(n²)", False),
    "Merge Sort": (merge_sort, "O(n log n)", "O(n log n)", True),
    "Quick Sort": (quick_sort, "O(n log n)", "O(n²)", False),
    "Count Sort": (count_sort, "O(n + k)", "O(n + k)", True),
    "Radix Sort": (radix_sort, "O(d · (n + k))", "O(d · (n + k))", True),
    "Bucket Sort": (bucket_sort, "O(n + k)", "O(n²)", True),
}
QUADRATIC = {"Bubble Sort", "Insertion Sort", "Selection Sort"}


def describe(name):
    _, avg, worst, stable = ALGORITHMS[name]
    return f"Average {avg}, worst {worst}, {'stable' if stable else 'not stable'}"


def run_sort(name, items, stop=None):
    """Sort a copy of items. Returns (sorted_items, Stats, milliseconds)."""
    stop = stop or threading.Event()
    data, st = list(items), Stats()
    t0 = time.perf_counter()
    ALGORITHMS[name][0](data, st, stop)
    return data, st, (time.perf_counter() - t0) * 1000


# ---------------------------------------------------------------- keys
INF = float("inf")


def make_key(rec, col, kind, desc=False):
    """Comparable key for one column. Missing values always sort last. Descending is done by inverting
    the key, so every algorithm (stable or not) works in one pass and multi-level keys can be tuples."""
    v = rec.get(col)
    if kind == "num":
        if v is None:
            return INF
        return -v if desc else v
    s = (v or "").lower()
    if not s:
        return (10 ** 9,) if desc else "\U0010ffff"
    return tuple(-ord(ch) for ch in s) + (1,) if desc else s


def build_items(records, indices, specs, kinds):
    """specs: [(column, desc), ...] -> [(key, index)]; one spec gives plain keys, several give tuple keys."""
    if len(specs) == 1:
        col, desc = specs[0]
        return [(make_key(records[i], col, kinds[col], desc), i) for i in indices]
    return [(tuple(make_key(records[i], c, kinds[c], d) for c, d in specs), i) for i in indices]
