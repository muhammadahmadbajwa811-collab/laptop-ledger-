"""Searching algorithms + composite filter evaluation (AND / OR / NOT).

Linear search scans the raw rows. Binary, Jump, Interpolation and Exponential search work on a sorted
index of a column (built once with our own merge sort, then cached), each finding the first position
whose key is >= the target ("lower bound"), after which matches are read off in order."""
import math
import threading
import time

from sorting import merge_sort, Stats

STR_OPS = ["contains", "starts with", "ends with", "equals"]
NUM_OPS = ["=", ">", ">=", "<", "<=", "between"]
ALGOS = ["Linear Search", "Binary Search", "Jump Search", "Exponential Search", "Interpolation Search"]
INFO = {
    "Linear Search": "O(n). Works on unsorted data and every operator.",
    "Binary Search": "O(log n). Needs a sorted column (index built automatically).",
    "Jump Search": "O(√n). Needs a sorted column.",
    "Exponential Search": "O(log n). Needs a sorted column.",
    "Interpolation Search": "O(log log n) on evenly spread numbers, O(n) worst. Numeric columns only.",
}


def indexable(kind, op, algo):
    """Can this algorithm answer this operator via the sorted index?"""
    if algo == "Linear Search":
        return False
    if kind == "num":
        return True
    return op in ("equals", "starts with") and algo != "Interpolation Search"


# ---- lower-bound searches: first index with keys[i] >= t. c is a one-item list used as a comparison counter.
def lb_binary(keys, t, c, lo=0, hi=None):
    hi = len(keys) if hi is None else hi
    while lo < hi:
        mid = (lo + hi) // 2
        c[0] += 1
        if keys[mid] < t:
            lo = mid + 1
        else:
            hi = mid
    return lo


def lb_jump(keys, t, c):
    n = len(keys)
    if n == 0:
        return 0
    step = max(1, int(math.sqrt(n)))
    prev, cur = 0, step
    while prev < n:
        c[0] += 1
        if keys[min(cur, n) - 1] < t:
            prev, cur = cur, cur + step
        else:
            break
    i = prev
    while i < n:
        c[0] += 1
        if keys[i] < t:
            i += 1
        else:
            break
    return min(i, n)


def lb_exponential(keys, t, c):
    n = len(keys)
    if n == 0:
        return 0
    c[0] += 1
    if keys[0] >= t:
        return 0
    b = 1
    while b < n:
        c[0] += 1
        if keys[b] < t:
            b *= 2
        else:
            break
    return lb_binary(keys, t, c, b // 2 + 1, min(b, n))


def lb_interpolation(keys, t, c):
    lo, hi = 0, len(keys) - 1
    while lo <= hi:
        c[0] += 1
        if keys[lo] >= t:
            return lo
        c[0] += 1
        if keys[hi] < t:
            return hi + 1
        pos = lo + int((t - keys[lo]) * (hi - lo) / (keys[hi] - keys[lo]))
        c[0] += 1
        if keys[pos] < t:
            lo = pos + 1
        else:
            hi = pos - 1
    return lo


LOWER_BOUND = {"Binary Search": lb_binary, "Jump Search": lb_jump,
               "Exponential Search": lb_exponential, "Interpolation Search": lb_interpolation}


def _scan(keys, i, pred, c):
    """Advance i while pred(keys[i]) holds, counting comparisons."""
    n = len(keys)
    while i < n:
        c[0] += 1
        if pred(keys[i]):
            i += 1
        else:
            break
    return i


class IndexCache:
    """Sorted (key, row) index per column, built with our own merge sort and reused until data changes."""

    def __init__(self):
        self.data = {}

    def clear(self):
        self.data.clear()

    def get(self, records, col, kind):
        if col not in self.data:
            items = []
            for i, r in enumerate(records):
                v = r.get(col)
                if v is None or v == "":
                    continue
                items.append((v if kind == "num" else str(v).lower(), i))
            merge_sort(items, Stats(), threading.Event())
            self.data[col] = ([k for k, _ in items], [i for _, i in items])
        return self.data[col]


def parse_value(kind, text):
    text = text.strip()
    if kind == "num":
        return float(text.replace(",", ""))
    return text.lower()


def search(records, cache, col, kind, op, v1, v2, algo):
    """Return (set_of_row_indices, comparisons, milliseconds)."""
    a = parse_value(kind, v1)
    b = parse_value(kind, v2) if op == "between" else None
    t0 = time.perf_counter()
    c = [0]
    if not indexable(kind, op, algo):
        out = set()
        for i, r in enumerate(records):
            v = r.get(col)
            if v is None or v == "":
                continue
            c[0] += 1
            if kind == "num":
                ok = (v == a if op == "=" else v > a if op == ">" else v >= a if op == ">="
                      else v < a if op == "<" else v <= a if op == "<=" else a <= v <= b)
            else:
                s = str(v).lower()
                ok = (a in s if op == "contains" else s.startswith(a) if op == "starts with"
                      else s.endswith(a) if op == "ends with" else s == a)
            if ok:
                out.add(i)
        return out, c[0], (time.perf_counter() - t0) * 1000

    keys, rows = cache.get(records, col, kind)
    lb = LOWER_BOUND[algo]
    if kind == "str":
        lo = lb(keys, a, c)
        hi = _scan(keys, lo, (lambda k: k == a) if op == "equals" else (lambda k: k.startswith(a)), c)
    elif op == "=":
        lo = lb(keys, a, c)
        hi = _scan(keys, lo, lambda k: k == a, c)
    elif op == ">=":
        lo, hi = lb(keys, a, c), len(keys)
    elif op == ">":
        lo = _scan(keys, lb(keys, a, c), lambda k: k == a, c)
        hi = len(keys)
    elif op == "<":
        lo, hi = 0, lb(keys, a, c)
    elif op == "<=":
        lo, hi = 0, _scan(keys, lb(keys, a, c), lambda k: k == a, c)
    else:  # between (inclusive)
        lo = lb(keys, a, c)
        hi = _scan(keys, lb(keys, b, c), lambda k: k == b, c)
    return set(rows[lo:hi]), c[0], (time.perf_counter() - t0) * 1000


def combine(n_rows, conditions, results):
    """Evaluate left to right: result = c1; then (AND|OR) the next condition, each optionally NOT-ed.
    conditions[i] = {'connector': 'AND'|'OR', 'negate': bool}; results[i] = set of matching rows."""
    everything = set(range(n_rows))
    acc = None
    for cond, res in zip(conditions, results):
        cur = everything - res if cond["negate"] else res
        if acc is None:
            acc = set(cur)
        elif cond["connector"] == "AND":
            acc &= cur
        else:
            acc |= cur
    return acc if acc is not None else everything
