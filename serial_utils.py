# serial_utils.py
import re

# ---------------------------
# Extracción de texto de PDF
# ---------------------------
def extract_text_from_pdf(file) -> str:
    """
    Intenta extraer texto con pdfplumber.
    Si falla o devuelve vacío (o el módulo no está), cae a pdfminer.six.
    Nota: si el PDF es escaneado (imágenes), ambas pueden devolver vacío.
    """
    # --- Plan A: pdfplumber ---
    try:
        import pdfplumber  # lazy import
        if hasattr(file, "seek"):
            file.seek(0)
        parts = []
        with pdfplumber.open(file) as pdf:
            for p in pdf.pages:
                txt = p.extract_text() or ""
                parts.append(txt)
        text = "\n".join(parts)
        if text.strip():
            return text
    except Exception:
        # Si falla el import o la lectura, seguimos al plan B
        pass

    # --- Plan B: pdfminer.six ---
    try:
        from pdfminer.high_level import extract_text as miner_extract_text
        if hasattr(file, "seek"):
            file.seek(0)
        text = miner_extract_text(file)
        return text or ""
    except Exception as e:
        raise RuntimeError(f"No pude extraer texto del PDF (fallback pdfminer): {e}")

# ---------------------------
# Regex de seriales
# ---------------------------
def extract_tokens_by_regex(text: str, pattern: str):
    """
    Devuelve las coincidencias del patrón dado (o uno por defecto si el patrón es inválido).
    """
    try:
        rgx = re.compile(pattern)
    except re.error:
        rgx = re.compile(r"[A-Za-z0-9\-_/\.]{6,}")
    return rgx.findall(text or "")

# ---------------------------
# Normalización
# ---------------------------
def normalize_token(
    s,
    do_upper: bool = True,
    strip_spaces: bool = True,
    strip_dashes: bool = False,
    strip_dots: bool = False,
    strip_slashes: bool = False,
) -> str:
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
    return series.fillna("").astype(str).apply(lambda x: normalize_token(x, **kwargs))

# ---------------------------
# Fuzzy matching (Levenshtein)
# ---------------------------
def _lev(a: str, b: str) -> int:
    """
    Distancia de edición Levenshtein (iterativa, O(len(a)*len(b))).
    """
    m, n = len(a), len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    dp = list(range(n + 1))
    for i, ch1 in enumerate(a, 1):
        prev = dp[0]
        dp[0] = i
        for j, ch2 in enumerate(b, 1):
            cur = dp[j]
            cost = 0 if ch1 == ch2 else 1
            dp[j] = min(
                dp[j] + 1,       # borrado
                dp[j - 1] + 1,   # inserción
                prev + cost      # sustitución
            )
            prev = cur
    return dp[n]

def fuzzy_match_candidates(target: str, candidates, max_distance: int = 1, top_k: int = 3):
    """
    Devuelve los mejores 'top_k' candidatos cuya distancia Levenshtein <= max_distance.
    """
    results = []
    for c in candidates:
        d = _lev(target, c)
        if d <= max_distance:
            results.append((c, d))
    results.sort(key=lambda x: x[1])
    return results[:top_k]
