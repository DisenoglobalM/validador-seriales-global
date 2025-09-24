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

def extract_text_from_pdf(file) -> str:
    """
    Intenta extraer texto con pdfplumber.
    Si falla o devuelve vacío, cae a pdfminer.six (100% Python).
    """
    # 1) Intento con pdfplumber
    try:
        import pdfplumber  # lazy import
        with pdfplumber.open(file) as pdf:
            parts = []
            for p in pdf.pages:
                txt = p.extract_text() or ""
                parts.append(txt)
        text = "\n".join(parts)
        if text.strip():
            return text
    except Exception:
        pass  # seguimos al plan B

    # 2) Fallback: pdfminer.six
    try:
        from pdfminer.high_level import extract_text as miner_extract_text
        # Asegura el puntero al inicio (Streamlit UploadedFile es un buffer)
        if hasattr(file, "seek"):
            file.seek(0)
        text = miner_extract_text(file)
        return text or ""
    except Exception as e:
        raise RuntimeError(f"No pude extraer texto del PDF (fallback pdfminer): {e}")
