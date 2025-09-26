# app.py
import io
import sys
import pandas as pd
import streamlit as st

from serial_utils import (
    extract_text_from_pdf,     # pdfplumber -> fallback pdfminer
    extract_tokens_by_regex,   # tokenización por regex
    normalize_series,          # normalizador de tokens/series
    fuzzy_match_candidates,    # opcional: sugerencias "casi iguales"
)

# ============ CONFIG ============ #
st.set_page_config(
    page_title="Validador de Seriales — Declaración de Importación",
    page_icon="✅",
    layout="centered",
)
st.info("✅ La app cargó correctamente. Sube Excel/CSV + PDF/TXT para continuar.")

DEFAULT_REGEX = r"[A-Za-z0-9\-_/\.\]{6,}"  # al menos 6, letras/números y -,_,/,.

# ============ SUBIDA DE ARCHIVOS ============ #
left, right = st.columns(2)

with left:
    xfile = st.file_uploader(
        "Excel con seriales esperados (XLSX o CSV)",
        type=["xlsx", "csv"],
        help="Sube la matriz de 'seriales internos' + 'seriales externos'."
    )

with right:
    dfile = st.file_uploader(
        "Declaración de Importación (PDF o TXT con texto)",
        type=["pdf", "txt"],
        help="Si el PDF es escaneado, exporta a TXT (OCR) y súbelo aquí."
    )

# nombres de columnas
col1 = st.text_input("Nombre de la columna #1 (Interno)", "SERIAL FISICO INTERNO")
col2 = st.text_input("Nombre de la columna #2 (Externo)", "SERIAL FISICO EXTERNO")

regex_pattern = st.text_input(
    "Patrón (regex) para extraer seriales del PDF/TXT",
    DEFAULT_REGEX,
    help="Edita si tus seriales tienen otro formato."
)

run_btn = st.button("Validar ahora", type="primary", use_container_width=True)


# ============ FUNCIONES AUXILIARES ============ #
def _read_table(file) -> pd.DataFrame:
    """
    Lee el XLSX o CSV en un DataFrame.
    - Si XLSX y no está openpyxl instalado, recomienda subir CSV.
    """
    name = (file.name or "").lower()
    if name.endswith(".csv"):
        file.seek(0)
        return pd.read_csv(file)
    else:
        try:
            file.seek(0)
            # pandas intentará usar 'openpyxl' si está disponible
            return pd.read_excel(file)
        except ImportError as e:
            st.error(
                "No puedo leer XLSX porque falta el motor 'openpyxl' en el servidor. "
                "Por favor exporta tu Excel a CSV y súbelo de nuevo."
            )
            st.stop()
        except Exception as e:
            st.error(f"No se pudo leer el Excel: {e}")
            st.stop()


def _resolve_columns(df: pd.DataFrame, a: str, b: str) -> tuple[str, str]:
    """Resuelve nombres de columnas sin sensibilidad a mayúsculas/minúsculas."""
    mapping = {c.lower(): c for c in df.columns}
    c1 = mapping.get(a.lower())
    c2 = mapping.get(b.lower())
    return c1, c2


def _combine_expected(df: pd.DataFrame, c1: str, c2: str) -> list[str]:
    """
    Une ambas columnas de seriales y devuelve la lista de 'esperados' normalizados.
    """
    serie = pd.concat([df[c1], df[c2]], ignore_index=True).astype(str)
    # normaliza (quita espacios, mayúsculas, etc.) y quita duplicados
    norm = normalize_series(serie).dropna()
    return pd.unique(norm).tolist()


def _read_text_from_doc(file) -> str:
    """
    Devuelve el texto plano:
    - Si es TXT: decodifica como utf-8.
    - Si es PDF: usa extract_text_from_pdf() (pdfplumber -> pdfminer fallback).
    """
    name = (file.name or "").lower()
    if name.endswith(".txt"):
        try:
            file.seek(0)
        except Exception:
            pass
        return file.read().decode("utf-8", errors="ignore")
    else:
        return extract_text_from_pdf(file)


# ============ EJECUCIÓN ============ #
if run_btn:
    if not xfile or not dfile:
        st.error("Por favor, sube **ambos** archivos (Excel/CSV y PDF/TXT).")
        st.stop()

    # ---- 1) Leer Excel/CSV ----
    df = _read_table(xfile)

    # Mostrar columnas y muestra para depurar
    with st.expander("Ver columnas detectadas (depuración)", expanded=False):
        st.write("Columnas:")
        st.write(list(df.columns))
        st.write("Vista previa:")
        st.dataframe(df.head(10))

    c1, c2 = _resolve_columns(df, col1, col2)
    if not c1 or not c2:
        st.error(
            f"No encuentro estas columnas: { [col1, col2] }. "
            f"Columnas disponibles: {list(df.columns)}"
        )
        st.stop()

    esperados = _combine_expected(df, c1, c2)
    st.success(
        f"Leídos {len(esperados)} seriales 'esperados' de {c1} + {c2}."
    )

    # ---- 2) Obtener texto del documento (PDF o TXT) ----
    try:
        raw_text = _read_text_from_doc(dfile)
    except Exception as e:
        st.error(f"No se pudo leer el documento. Detalle: {e}")
        st.stop()

    with st.expander("Ver muestra de texto extraído del PDF/TXT (depuración)"):
        st.write(f"Longitud del texto extraído: {len(raw_text)} caracteres")
        st.text(raw_text[:2000] or "[vacío]")

    if not raw_text.strip():
        st.error(
            "El documento no contiene texto legible. "
            "Si es un PDF escaneado (solo imágenes), aplica OCR o exporta a TXT y vuelve a subirlo."
        )
        st.stop()

    # ---- 3) Extraer tokens candidatos del texto ----
    try:
        tokens = extract_tokens_by_regex(raw_text, regex_pattern)
    except Exception as e:
        st.error(f"Error en el patrón regex: {e}")
        st.stop()

    # normalizar tokens del documento
    tokens_norm = normalize_series(pd.Series(tokens)).dropna().tolist()
    tokens_norm_set = set(tokens_norm)

    # ---- 4) Cruce: encontrados / faltantes ----
    encontrados = [s for s in esperados if s in tokens_norm_set]
    faltantes   = [s for s in esperados if s not in tokens_norm_set]

    st.subheader("Resultados")
    st.write(f"✅ Encontrados: **{len(encontrados)}** / {len(esperados)} totales")
    st.write(f"❌ Faltantes: **{len(faltantes)}**")

    colA, colB = st.columns(2)
    with colA:
        with st.expander("Ver ejemplo de ENCONTRADOS"):
            st.write(encontrados[:50] or "[vacío]")
    with colB:
        with st.expander("Ver ejemplo de FALTANTES"):
            st.write(faltantes[:50] or "[vacío]")

    # Opcional: sugerencias de "casi iguales" (más lento si la lista es grande)
    with st.expander("Sugerencias (coincidencias cercanas) para algunos faltantes", expanded=False):
        sample = faltantes[:20]  # limita por rendimiento
        rows = []
        for s in sample:
            sug = fuzzy_match_candidates(s, tokens_norm, max_distance=1, top_k=3)
            rows.append({
                "serial_faltante": s,
                "sugerencias": ", ".join(f"{c} (d={d})" for c, d in sug) or "-"
            })
        st.dataframe(pd.DataFrame(rows))
