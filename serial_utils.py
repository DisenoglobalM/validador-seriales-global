# serial_utils.py
# Utilidades para extracción y comparación de seriales.

from __future__ import annotations
import re
from typing import Iterable, List, Tuple, Set

# -----------------------------
# Extracción de texto de PDF
# -----------------------------
def extract_text_from_pdf(file) -> str:
    """
    Intenta extraer texto con pdfplumber y, si es poco o vacío,
    hace fallback a pdfminer.six. Devuelve texto plano (puede ser '').
    """
    text = ""

    # 1) Primer intento: pdfplumber
    try:
        try:
            file.seek(0)
        except Exception:
            pass
        import pdfplumber
        parts = []
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                parts.append(t)
        text = "\n".join(parts).strip()
    except Exception:
        text = ""

    # 2) Fallback: pdfminer.six (si quedó poco o nada)
    if len(text) < 20:  # umbral conservador
        try:
            try:
                file.seek(0)
            except Exception:
                pass
            from pdfminer.high_level import extract_text as miner_extract_text
            text2 = miner_extract_text(file) or ""
            if len(text2.strip()) > len(text):
                text = text2.strip()
        except Exception:
            pass

    return text or ""

# --- En serial_utils.py ---

def _read_text_file(uploaded_file):
    """
    Lee un .txt de manera robusta. Intenta varias codificaciones y
    no revienta si hay caracteres extraños.
    """
    # Lee los bytes (Streamlit UploadedFile funciona con getvalue/seek)
    try:
        data = uploaded_file.getvalue()
    except Exception:
        data = uploaded_file.read()

    # Regresa el puntero al inicio, por si luego el mismo handle se reusa
    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    # Intenta decodificar con varias codificaciones comunes
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            text = data.decode(enc, errors="ignore")
            if text is not None:
                return text
        except Exception:
            continue
    return ""


def extract_text_from_file(uploaded_file):
    """
    Si es .txt -> leer como texto (robusto).
    Si es PDF -> usa la función existente extract_text_from_pdf(uploaded_file).
    """
    name = (getattr(uploaded_file, "name", "") or "").lower()
    if name.endswith(".txt"):
        return _read_text_file(uploaded_file)
    # Para PDF u otros, mantenemos tu flujo actual:
    return extract_text_from_pdf(uploaded_file)


# -----------------------------
# Normalización y regex
# -----------------------------
def normalize_token(
    s,
    *,
    do_upper: bool = True,
    strip_spaces: bool = True,
    strip_dashes: bool = True,
    strip_dots: bool = True,
    strip_slashes: bool = True,
) -> str:
    """Normaliza un token para comparación robusta."""
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
    """
    Normaliza una Serie de pandas aplicando normalize_token.
    (Import local para no forzar pandas al importar el módulo si no se usa.)
    """
    import pandas as pd  # import perezoso
    s = pd.Series(series, copy=True)
    return s.fillna("").astype(str).apply(lambda x: normalize_token(x, **kwargs))


def extract_tokens_by_regex(text: str, pattern: str) -> List[str]:
    """Extrae tokens del texto según un patrón regex dado."""
    if not (isinstance(text, str) and text):
        return []
    try:
        rgx = re.compile(pattern)
    except re.error:
        rgx = re.compile(r"[A-Za-z0-9\-_/\.]{6,}")
    return rgx.findall(text)


# -----------------------------
# Fuzzy matching (Levenshtein)
# -----------------------------
def _lev(a: str, b: str) -> int:
    """
    Distancia de Levenshtein (ediciones) entre a y b.
    Implementación iterativa O(len(a)*len(b)) sin dependencias extra.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    # Asegurar que a sea la cadena más corta para usar menos memoria
    if len(a) > len(b):
        a, b = b, a

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            insert_cost = curr[j - 1] + 1
            delete_cost = prev[j] + 1
            replace_cost = prev[j - 1] + (0 if ca == cb else 1)
            curr.append(min(insert_cost, delete_cost, replace_cost))
        prev = curr
    return prev[-1]


def fuzzy_match_candidates(
    target: str,
    candidates: Iterable[str],
    max_distance: int = 1,
    top_k: int = 3,
) -> List[Tuple[str, int]]:
    """
    Devuelve hasta top_k candidatos de 'candidates' cuya distancia con 'target'
    sea <= max_distance, ordenados por distancia ascendente.
    """
    tgt = target or ""
    out: List[Tuple[str, int]] = []
    for c in candidates:
        d = _lev(tgt, c)
        if d <= max_distance:
            out.append((c, d))
    out.sort(key=lambda x: x[1])
    return out[:top_k]


__all__ = [
    "extract_text_from_pdf",
    "normalize_token",
    "normalize_series",
    "extract_tokens_by_regex",
    "fuzzy_match_candidates",
]
