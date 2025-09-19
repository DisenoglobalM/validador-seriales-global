# serial_utils.py (versión robusta)
import re
import pandas as pd

def _load_pdfplumber():
    try:
        import pdfplumber
        return pdfplumber
    except Exception as e:
        raise RuntimeError(
            "No se pudo importar pdfplumber. Revisa requirements.txt y reinicia la app.\nDetalle: %s" % e
        )

# Fallback si no está rapidfuzz
try:
    from rapidfuzz.distance import Levenshtein
    def _lev(a, b):
        return Levenshtein.distance(a, b)
except Exception:
    def _lev(a, b):
        # Levenshtein simple (DP)
        if a == b:
            return 0
        m, n = len(a), len(b)
        dp = [[0]*(n+1) for _ in range(m+1)]
        for i in range(m+1):
            dp[i][0] = i
        for j in range(n+1):
            dp[0][j] = j
        for i in range(1, m+1):
            for j in range(1, n+1):
                cost = 0 if a[i-1] == b[j-1] else 1
                dp[i][j] = min(dp[i-1][j]+1, dp[i][j-1]+1, dp[i-1][j-1]+cost)
        return dp[m][n]

def extract_text_from_pdf(file):
    """Extrae texto de un PDF nativo (si es escaneado puede venir vacío)."""
    pdfplumber = _load_pdfplumber()
    text_parts = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            text_parts.append(t)
    return "\n".join(text_parts)

def extract_tokens_by_regex(text, pattern):
    try:
        rgx = re.compile(pattern)
    except re.error:
        rgx = re.compile(r"[A-Za-z0-9\-_/\.]{6,}")
    return rgx.findall(text or "")

def normalize_token(s, do_upper=True, strip_spaces=True, strip_dashes=False, strip_dots=False, strip_slashes=False):
    if s is None:
        return ""
    s2 = str(s)
    if do_upper:
        s2 = s2.upper()
    if strip_spaces:
        s2 = s2.replace(" ", "")
    if strip_dashes:
        s2 = s2.replace("-", "")
    if strip_dots:
        s2 = s2.replace(".", "")
    if strip_slashes:
        s2 = s2.replace("/", "").replace("\\", "")
    return s2

def normalize_series(series, **kwargs):
    return series.apply(lambda x: normalize_token(x, **kwargs))

def fuzzy_match_candidates(target, candidates, max_distance=1, top_k=3):
    results = []
    for c in candidates:
        d = _lev(target, c)
        if d <= max_distance:
            results.append((c, d))
    results.sort(key=lambda x: x[1])
    return results[:top_k]
