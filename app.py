import streamlit as st
import pandas as pd
# --- Ensure openpyxl is available at runtime ---
try:
    import openpyxl  # noqa: F401
except Exception:
    import sys, subprocess
    # Instala en caliente si no está (una sola vez por contenedor)
    subprocess.run([sys.executable, "-m", "pip", "install", "openpyxl==3.1.5"], check=True)
    import openpyxl  # reintenta
# ------------------------------------------------
from serial_utils import (
    extract_text_from_pdf,
    normalize_token,
    extract_tokens_by_regex,
    fuzzy_match_candidates,
)


st.set_page_config(page_title="Validador de Seriales (DI) — 2 columnas", page_icon="✅", layout="centered")
st.info("✅ La app cargó correctamente. Sube Excel + PDF para continuar.")


st.title("Validador de Seriales — Declaración de Importación (2 columnas)")
st.caption("Sube tu Excel con dos columnas de seriales (Interno y Externo) y el PDF de la DI. Compara y genera un reporte unificado.")

with st.expander("Configuración (opcional)", expanded=False):
    regex_pattern = st.text_input(
        "Patrón (regex) para detectar seriales en el documento",
        value=r"[A-Za-z0-9\-_/\.]{6,}",
        help="Expresión regular para encontrar seriales dentro del PDF."
    )
    do_upper = st.checkbox("Forzar MAYÚSCULAS", value=True)
    strip_spaces = st.checkbox("Quitar espacios internos", value=True)
    strip_dashes = st.checkbox("Quitar guiones", value=False)
    strip_dots = st.checkbox("Quitar puntos", value=False)
    strip_slashes = st.checkbox("Quitar / y \\", value=False)
    min_len = st.number_input("Longitud mínima del serial (post-normalización)", min_value=1, value=6, step=1)
    enable_fuzzy = st.checkbox("Habilitar coincidencias aproximadas (fuzzy)", value=True)
    max_distance = st.slider("Distancia máxima (Levenshtein)", min_value=1, max_value=5, value=1)
    fuzzy_top_k = st.slider("Máximos candidatos por faltante", min_value=1, max_value=10, value=3)

st.subheader("1) Sube los archivos")
xlsx_file = st.file_uploader("Excel con seriales esperados (XLSX)", type=["xlsx"])
pdf_file = st.file_uploader("Declaración de Importación (PDF)", type=["pdf"])

default_col1 = "SERIAL FISICO INTERNO"
default_col2 = "SERIAL FISICO EXTERNO"

sheet_name = None
excel_preview = None
columns_available = []

if xlsx_file:
    try:
        xls = pd.ExcelFile(xlsx_file)
        # Elegir hoja: si existe una llamada 'FISICOS  INTERNO Y EXTERNO' usarla; si no, la primera
        options = xls.sheet_names
        preselect = None
        for opt in options:
            if "FISICOS" in opt.upper():
                preselect = opt
                break
        sheet_name = st.selectbox("Hoja del Excel", options, index=options.index(preselect) if preselect in options else 0)
        excel_preview = pd.read_excel(xlsx_file, sheet_name=sheet_name)
        columns_available = list(excel_preview.columns)
        with st.expander("Vista previa de columnas detectadas", expanded=False):
            st.write(columns_available)
            st.dataframe(excel_preview.head(), use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"No pude leer el Excel: {e}")

col1 = st.text_input("Nombre de la columna #1 (Interno)", value=default_col1)
col2 = st.text_input("Nombre de la columna #2 (Externo)", value=default_col2)

run_btn = st.button("Validar ahora", type="primary", use_container_width=True)

if run_btn:
    if not xlsx_file or not pdf_file:
        st.error("Por favor, sube **ambos** archivos (Excel y PDF).")
        st.stop()

    # Cargar Excel
    try:
       df = pd.read_excel(
    xlsx_file,
    sheet_name=sheet_name if sheet_name else 0,
    engine="openpyxl"
)
    except Exception as e:
        st.error(f"No se pudo leer el Excel: {e}")
        st.stop()

    # Verificar columnas
    cols_lower = {c.lower(): c for c in df.columns}
    def resolve(name):
        if name in df.columns:
            return name
        # buscar case-insensitive
        return cols_lower.get(name.lower())

    c1 = resolve(col1)
    c2 = resolve(col2)

    missing = []
    if not c1: missing.append(col1)
    if not c2: missing.append(col2)
    if missing:
        st.error(f"No encuentro estas columnas: {missing}. Columnas disponibles: {list(df.columns)}")
        st.stop()

    # Unir las dos columnas en una sola lista de esperados
    expected_raw = pd.concat([df[c1].astype(str), df[c2].astype(str)], ignore_index=True).fillna("")
    expected_norm = normalize_series(
        expected_raw,
        do_upper=do_upper,
        strip_spaces=strip_spaces,
        strip_dashes=strip_dashes,
        strip_dots=strip_dots,
        strip_slashes=strip_slashes,
    )
    expected_norm = expected_norm[expected_norm.str.len() >= min_len]
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

    # Comparaciones
    encontrados = sorted(expected_set.intersection(found_set))
    faltantes = sorted(expected_set.difference(found_set))

    # Fuzzy matching
    posibles = []
    if enable_fuzzy and faltantes and found_set:
        with st.spinner("Buscando coincidencias aproximadas..."):
            for miss in faltantes:
                cands = fuzzy_match_candidates(miss, list(found_set), max_distance=max_distance, top_k=fuzzy_top_k)
                for c, dist in cands:
                    posibles.append({"serial_faltante": miss, "posible_en_documento": c, "distancia": dist})

    # Extras en documento
    extras_doc = sorted(found_set.difference(expected_set))

    # Mostrar resultados
    st.subheader("Resultados")
    c1m, c2m, c3m = st.columns(3)
    c1m.metric("Encontrados", len(encontrados))
    c2m.metric("Faltantes", len(faltantes))
    c3m.metric("Extras en documento", len(extras_doc))

    df_encontrados = pd.DataFrame({"serial": encontrados})
    df_faltantes = pd.DataFrame({"serial": faltantes})
    df_extras = pd.DataFrame({"serial": extras_doc})
    df_posibles = pd.DataFrame(posibles) if posibles else pd.DataFrame(columns=["serial_faltante","posible_en_documento","distancia"])

    st.write("**Encontrados (exactos):**")
    st.dataframe(df_encontrados, use_container_width=True, hide_index=True)

    st.write("**Faltantes (de ambas columnas):**")
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
        st.text(f"Columnas usadas: {c1} + {c2}\nTokens candidatos (sin normalizar): {len(candidates)}\nTokens en documento (normalizados): {len(found_set)}")

st.markdown("---")
st.caption("Si tu PDF es escaneado, realiza OCR antes o despliega esta app en Cloud Run con Tesseract para OCR automático.")
