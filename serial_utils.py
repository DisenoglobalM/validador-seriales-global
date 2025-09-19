# serial_utils.py (versión segura para Streamlit Cloud)
import re
import io
import pandas as pd
from typing import List, Tuple

# No importes pdfplumber arriba; hazlo dentro de la función:
def _load_pdfplumber():
    try:
        import pdfplumber  # lazy import
        return pdfplumber
    except Exception as e:
        raise RuntimeError(
            "No se pudo importar pdfplumber. Revisa requirements.txt y vuelve a reiniciar la app.\n"
            f"Detalle: {e}"
        )

try:
    from rapidfuzz.distance import Levenshtein
except Exception:
    class _Lev:
        @staticmethod
        def distance(a, b):
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
                    cost = 0 if a[i-1]==b[j-1] else 1
                    dp[i][j] = min(dp[i-1][j]+1, dp[i][j-1]+1, dp[i-1][j-1]+cost)
            return dp[m][n]
    Levenshtein = _Lev

def extract_text_from_pdf(file) -> str:
    """Extrae texto concatenado de un PDF (nativo). Si es escaneado, puede venir vacío."""
    pdfplumber = _load_pdfplumber()
    text_parts = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            text_parts.append(t)
    return "\n".join(text_parts)

def extract_tokens_by_regex(text: str, pattern: str) -> List[str]:
    try:
        rgx = re.compile(pattern)
    except re.error:
        rgx = re.compile(r"[A-Za-z0-9\-_/\.]{6,}")
    return rgx.findall(text or "")

def normalize_token(s: str, do_upper=True, strip_spaces=True, strip_dashes=False, strip_dots=False, strip_slashes=False) -> str:
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

def normalize_series(series: pd.Series, **kwargs) -> pd.Series:
    return series.apply(lambda x: normalize_token(x, **kwargs))

def fuzzy_match_candidates(target: str, candidates: List[str], max_dis_

