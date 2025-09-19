import io
import re
import time
import pandas as pd
import streamlit as st
from typing import List, Tuple
from serial_utils import (
    extract_text_from_pdf,
    normalize_token,
    extract_tokens_by_regex,
    fuzzy_match_candidates,
    normalize_series,
)

st.set_page_config(page_title="Validador de Seriales (DI)", page_icon="✅", layout="centered")

st.title("Validador de Seriales — Declaración de Importación")
st.caption("Sube tu Excel con los seriales esperados y el PDF de la DI. La app compara y genera un reporte de encontrados / faltantes / posibles coincidencias.")

with st.expander("Configuración (opcional)", expanded=False):
    regex_pattern = st.text_input(
        "Patrón (regex) para detectar seriales en el documento",
        value=r"[A-Za-z0-9\-_/\.]{6,}",
        help="Usa una expresión regular que capture tus seriales. Por defecto: secuencias alfanuméricas de ≥6 caracteres (incluye - _ / .)."
    )
    do_upper = st.checkbox("Forzar MAYÚSCULAS", value=True)
    strip_spaces = st.checkbox("Quitar espacios internos", value=True)
    strip_dashes = st.checkbox("Quitar guiones", value=False, help="Úsalo si en tu Excel los seriales no tienen guiones pero en el PDF sí (o viceversa).")
    strip_dots = st.checkbox("Quitar puntos", value=False)
    strip_slashes = st.checkbox("Quitar / y \\", value=False)
    min_len = st.number_input("Longitud mínima del serial (post-normalización)", min_value=1, value=6, step=1)
    enable_fuzzy = st.checkbox("Habilitar coincidencias aproximadas (fuzzy)", value=True)
    max_distance = st.slider("Distancia máxima (Levenshtein)", min_value=1, max_value=5, value=1)
    fuzzy_top_k = st.slider("Máximos candidatos por faltante", min_value=1, max_value=10, value=3)

st.subheader("1) Sube los archivos")
xlsx_file = st.file_uploader("Excel con seriales esperados (XLSX)", type=["xlsx"])
pdf_file = st.file_uploader("Declaración de Importación (PDF)", type=["pdf"])

expected_col = st.text_input("Nombre de la columna en Excel con los seriales", value="serial")

run_btn = st.button("Validar ahora", type="primary", use_container_width=True)

if run_btn:
    if not xlsx_file or not pdf_file:
        st.error("Por favor, sube **ambos** archivos (Excel y PDF).")
        st.stop()

    # Cargar Excel
    try:
        df_expected = pd.read_excel(xlsx_file)
    except Exception as e:
        st.error(f"No se pudo leer el Excel: {e}")
        st.stop()

    if expected_col not in df_expected.columns:
        st.error(f"No encuentro la columna '{expected_col}' en tu Excel. Columnas disponibles: {list(df_expected.columns)}")
        st.stop()

    # Normalizar lista oficial
    expected_raw = df_expected[expected_col].astype(str).fillna("")
    expected_norm = normalize_series(
        expected_raw,
        do_upper=do_upper,
        strip_spaces=strip_spaces,
        strip_dashes=strip_dashes,
        strip_dots=strip_dots,
        strip_slashes=strip_slashes,
        min_len=min_len,
    )
    expected_set = set([x for x in expected_norm if x])

    # Extraer texto del PDF
    with st.spinner("Extrayendo texto del PDF..."):
        try:
            pdf_text = extract_text_from_pdf(pdf_file)
        except Exception as e:
            st.error(f"No se pudo extraer texto del PDF: {e}")
            st.stop()

    # Extraer tokens candidatos por regex
    candidates = extract_tokens_by_regex(pdf_text, regex_pattern)
    candidates_norm = [
        normalize_token(
            c,
            do_upper=do_upper,
            strip_spaces=strip_spaces,
            strip_dashes=strip_dashes,
            strip_dots=strip_dots,
            strip_slashes=strip_slashes,
        )
        for c in candidates
    ]
    candidates_norm = [c for c in candidates_norm if len(c) >= min_len]
    found_set = set(candidates_norm)

    # Coincidencias exactas
    encontrados = sorted(expected_set.intersection(found_set))
    faltantes = sorted(expected_set.difference(found_set))

    # Fuzzy matching para faltantes
    posibles = []
    if enable_fuzzy and faltantes and found_set:
        with st.spinner("Buscando coincidencias aproximadas..."):
            for miss in faltantes:
                cands = fuzzy_match_candidates(miss, list(found_set), max_distance=max_distance, top_k=fuzzy_top_k)
                for c, dist in cands:
                    posibles.append({"serial_faltante": miss, "posible_en_documento": c, "distancia": dist})

    # Extras en documento (no esperados)
    extras_doc = sorted(found_set.difference(expected_set))

    # Mostrar resultados
    st.subheader("Resultados")
    c1, c2, c3 = st.columns(3)
    c1.metric("Encontrados", len(encontrados))
    c2.metric("Faltantes", len(faltantes))
    c3.metric("Extras en documento", len(extras_doc))

    df_encontrados = pd.DataFrame({"serial": encontrados})
    df_faltantes = pd.DataFrame({"serial": faltantes})
    df_extras = pd.DataFrame({"serial": extras_doc})
    df_posibles = pd.DataFrame(posibles) if posibles else pd.DataFrame(columns=["serial_faltante","posible_en_documento","distancia"])

    st.write("**Encontrados (exactos):**")
    st.dataframe(df_encontrados, use_container_width=True, hide_index=True)

    st.write("**Faltantes:**")
    st.dataframe(df_faltantes, use_container_width=True, hide_index=True)

    if enable_fuzzy:
        st.write("**Posibles coincidencias (aproximadas):**")
        st.dataframe(df_posibles, use_container_width=True, hide_index=True)

    st.write("**Extras detectados en el documento (no estaban en Excel):**")
    st.dataframe(df_extras, use_container_width=True, hide_index=True)

    # Descargar reporte combinado
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_encontrados.to_excel(writer, index=False, sheet_name="encontrados")
        df_faltantes.to_excel(writer, index=False, sheet_name="faltantes")
        df_posibles.to_excel(writer, index=False, sheet_name="posibles_fuzzy")
        df_extras.to_excel(writer, index=False, sheet_name="extras_documento")

    st.download_button(
        "Descargar reporte (XLSX)",
        data=output.getvalue(),
        file_name="reporte_validacion_seriales.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    with st.expander("Detalle técnico", expanded=False):
        st.code(f"Patrón usado: {regex_pattern}\nNormalización: upper={do_upper}, spaces={strip_spaces}, dashes={strip_dashes}, dots={strip_dots}, slashes={strip_slashes}\nMin_len={min_len}\nFuzzy={enable_fuzzy}, max_distance={max_distance}, top_k={fuzzy_top_k}")
        st.text(f"Tokens candidatos (sin normalizar): {len(candidates)}\nTokens en documento (normalizados): {len(found_set)}")
        
st.markdown("---")
st.caption("Sugerencia: ajusta el patrón y la normalización para que coincidan con tu formato de seriales. Para OCR de PDFs escaneados, instala Tesseract y usa una herramienta externa para convertir a PDF con texto antes de validar.")
