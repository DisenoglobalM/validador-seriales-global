# app.py — Validador de Seriales (DI) — 2 columnas

import io
import re
import streamlit as st
import pandas as pd

from serial_utils import (
    extract_text_from_pdf,
    normalize_token,
    extract_tokens_by_regex,
    fuzzy_match_candidates,
)

# ---------------------------
# Configuración de la página
# ---------------------------
st.set_page_config(
    page_title="Validador de Seriales (DI) — 2 columnas",
    page_icon="✅",
    layout="centered",
)
st.title("Validador de Seriales — Declaración de Importación (2 columnas)")
st.caption("Sube tu Excel/CSV con dos columnas de seriales (Interno y Externo) y el PDF de la DI. Compara y genera un reporte unificado.")

with st.expander("Configuración (opcional)", expanded=False):
    sheet_name = st.text_input("Nombre de la hoja (solo para XLSX)", value="")
    regex_pattern = st.text_input(
        "Patrón regex para extraer seriales del PDF",
        value=r"[A-Za-z0-9\-/\.]{6,}",
        help="Ajusta según el formato de tus seriales. Por defecto, alfanumérico y separadores comunes con longitud ≥ 6.",
    )
    st.write("Normalización de tokens")
    do_upper = st.checkbox("Forzar MAYÚSCULAS", value=True)
    strip_spaces = st.checkbox("Quitar espacios internos", value=True)
    strip_dashes = st.checkbox("Quitar guiones (-)", value=True)
    strip_dots = st.checkbox("Quitar puntos (.)", value=True)
    strip_slashes = st.checkbox("Quitar slashes (/ y \\)", value=True)

    max_distance = st.slider(
        "Distancia máxima (fuzzy) para sugerir coincidencias",
        min_value=0, max_value=3, value=1,
        help="0 = coincidencia exacta tras normalizar. 1–3 tolera OCR/errores menores."
    )

st.subheader("1) Sube los archivos")

xlsx_file = st.file_uploader(
    "Excel con seriales esperados (XLSX **o CSV**)",
    type=["xlsx", "csv"],
)

pdf_file = st.file_uploader(
    "Declaración de Importación (PDF)",
    type=["pdf"],
)

default_col1 = "SERIAL FISICO INTERNO"
default_col2 = "SERIAL FISICO EXTERNO"
col1 = st.text_input("Nombre de la columna #1 (Interno)", value=default_col1)
col2 = st.text_input("Nombre de la columna #2 (Externo)", value=default_col2)

run_btn = st.button("Validar ahora", type="primary", use_container_width=True)

# ---------------------------
# Utilidades locales
# ---------------------------
def normalize_series(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).apply(
        lambda x: normalize_token(
            x,
            do_upper=do_upper,
            strip_spaces=strip_spaces,
            strip_dashes=strip_dashes,
            strip_dots=strip_dots,
            strip_slashes=strip_slashes,
        )
    )

def load_expected_table(uploaded, sheet: str | int | None) -> pd.DataFrame:
    """
    Lee el archivo de esperados:
      - CSV (si termina en .csv) → pd.read_csv (no requiere openpyxl)
      - XLSX (si termina en .xlsx) → pd.read_excel(engine='openpyxl')
    Si openpyxl falta en el entorno, muestra un error claro pidiendo CSV.
    """
    name = (uploaded.name or "").lower()
    try:
        if name.endswith(".csv"):
            return pd.read_csv(uploaded, encoding="utf-8")
        else:
            # XLSX
            try:
                import openpyxl  # puede no estar disponible en Py 3.13 en algunos entornos
                sh = sheet if sheet else 0
                return pd.read_excel(uploaded, sheet_name=sh, engine="openpyxl")
            except Exception as e:
                st.error(
                    "No pude leer el XLSX con **openpyxl** en este entorno. "
                    "Exporta tu archivo a **CSV (UTF-8)** desde Excel y súbelo de nuevo.\n\n"
                    f"Detalle técnico: {e}"
                )
                st.stop()
    except Exception as e:
        st.error(f"No se pudo leer el archivo de esperados: {e}")
        st.stop()

def resolve_column(df: pd.DataFrame, name: str) -> str | None:
    """Devuelve el nombre real de la columna en df (case-insensitive)."""
    if name in df.columns:
        return name
    cols_lower = {c.lower(): c for c in df.columns}
    return cols_lower.get(name.lower())

# ---------------------------
# Ejecución
# ---------------------------
if run_btn:
    if not xlsx_file or not pdf_file:
        st.error("Por favor, sube **ambos** archivos (Excel/CSV y PDF).")
        st.stop()

    # 1) Cargar tabla de esperados
    df = load_expected_table(xlsx_file, sheet_name)

    # 2) Resolver columnas (case-insensitive) y validar
    real_c1 = resolve_column(df, col1)
    real_c2 = resolve_column(df, col2)
    missing = []
    if not real_c1:
        missing.append(col1)
    if not real_c2:
        missing.append(col2)
    if missing:
        st.error(f"No encuentro estas columnas: {missing}. Columnas disponibles: {list(df.columns)}")
        st.stop()

    # 3) Unificar y normalizar esperados
    ser1 = normalize_series(df[real_c1])
    ser2 = normalize_series(df[real_c2])
    expected = pd.concat([ser1, ser2], ignore_index=True)
    expected = expected[expected != ""].drop_duplicates()
    expected_set = set(expected.tolist())

    st.success(f"Leídos {len(expected_set)} seriales 'esperados' de {real_c1} + {real_c2}.")

    # 4) Extraer seriales del PDF
    raw_text = extract_text_from_pdf(pdf_file)
    if not raw_text.strip():
        st.warning("El PDF parece no tener texto extraíble (¿escaneado?). Haz OCR y vuelve a subir.")
        st.stop()

    tokens_raw = extract_tokens_by_regex(raw_text, regex_pattern)
    tokens = [normalize_token(
        t,
        do_upper=do_upper,
        strip_spaces=strip_spaces,
        strip_dashes=strip_dashes,
        strip_dots=strip_dots,
        strip_slashes=strip_slashes,
    ) for t in tokens_raw]

    tokens = [t for t in tokens if t]
    found_set = set(tokens)

    # 5) Comparaciones
    encontrados = sorted(list(expected_set & found_set))
    faltantes = sorted(list(expected_set - found_set))
    extras_doc = sorted(list(found_set - expected_set))

    c1, c2, c3 = st.columns(3)
    c1.metric("Encontrados", len(encontrados))
    c2.metric("Faltantes", len(faltantes))
    c3.metric("Extras en documento", len(extras_doc))

    st.subheader("Resultados")

    st.write("**Encontrados**")
    df_encontrados = pd.DataFrame({"serial": encontrados})
    st.dataframe(df_encontrados, use_container_width=True, height=220)

    st.write("**Faltantes**")
    df_faltantes = pd.DataFrame({"serial_esperado": faltantes})
    st.dataframe(df_faltantes, use_container_width=True, height=220)

    st.write("**Extras en documento**")
    df_extras = pd.DataFrame({"serial_en_di": extras_doc})
    st.dataframe(df_extras, use_container_width=True, height=220)

    # 6) Sugerencias fuzzy para faltantes
    st.write("**Posibles coincidencias (fuzzy)**")
    fuzzy_rows = []
    for s in faltantes:
        suggestions = fuzzy_match_candidates(s, encontrados + extras_doc, max_distance=max_distance, top_k=3)
        for sug, dist in suggestions:
            fuzzy_rows.append({"serial_esperado": s, "posible_en_di": sug, "dist": dist})

    df_fuzzy = pd.DataFrame(fuzzy_rows) if fuzzy_rows else pd.DataFrame(columns=["serial_esperado", "posible_en_di", "dist"])
    st.dataframe(df_fuzzy, use_container_width=True, height=240)

    # 7) Descargar reporte XLSX
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        df_encontrados.to_excel(writer, index=False, sheet_name="encontrados")
        df_faltantes.to_excel(writer, index=False, sheet_name="faltantes")
        df_extras.to_excel(writer, index=False, sheet_name="extras_en_documento")
        df_fuzzy.to_excel(writer, index=False, sheet_name="posibles_coincidencias")
    st.download_button(
        "📥 Descargar reporte (XLSX)",
        data=out.getvalue(),
        file_name="reporte_validacion_seriales.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# Nota: si el PDF es escaneado, necesitarás hacer OCR previo o desplegar esta app con OCR.
