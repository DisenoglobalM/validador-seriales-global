import streamlit as st
import pandas as pd
from serial_utils import (
    extract_text_from_file,
    normalize_series,
    extract_tokens_by_regex,
)

# ---- Configuración de la página ----
st.set_page_config(
    page_title="Validador de Seriales (DI) — 2 columnas",
    page_icon="✅",
    layout="centered"
)

st.info("✅ La app cargó correctamente. Sube Excel/CSV + PDF o TXT para continuar.")

# ---- 1) Inputs ----
xlsx_file = st.file_uploader("Excel con seriales esperados (XLSX o CSV)", type=["xlsx", "csv"])
pdf_file = st.file_uploader("Declaración de Importación (PDF con texto) o TXT", type=["pdf", "txt"])

col1 = st.text_input("Nombre de la columna #1 (Interno)", "SERIAL FISICO INTERNO")
col2 = st.text_input("Nombre de la columna #2 (Externo)", "SERIAL FISICO EXTERNO")
pattern = st.text_input("Patrón (regex) para extraer seriales del PDF/TXT", r"[A-Za-z0-9\-_\/\.]{6,}")

run_btn = st.button("Validar ahora", type="primary", use_container_width=True)

# ---- 2) Ejecución ----
if run_btn:
    if not xlsx_file or not pdf_file:
        st.error("Por favor, sube **ambos** archivos (Excel/CSV y PDF/TXT).")
        st.stop()

    # ---- 3) Cargar Excel/CSV ----
    try:
        if xlsx_file.name.endswith(".csv"):
            df = pd.read_csv(xlsx_file, sep=None, engine="python")
        else:
            df = pd.read_excel(xlsx_file, engine="openpyxl")
    except Exception as e:
        st.error(f"No se pudo leer el Excel/CSV: {e}")
        st.stop()

    # Mostrar columnas detectadas
    with st.expander("Ver columnas detectadas (depuración)"):
        st.write("Columnas:", list(df.columns))
        st.dataframe(df.head())

    # Resolver columnas ignorando mayúsculas/minúsculas
    cols_lower = {c.lower(): c for c in df.columns}
    def resolve(name):
        return cols_lower.get(name.lower())

    c1_res, c2_res = resolve(col1), resolve(col2)
    if not c1_res or not c2_res:
        st.error(f"No encuentro estas columnas: {col1}, {col2}. Columnas disponibles: {list(df.columns)}")
        st.stop()

    # Seriales esperados
    serie1 = df[c1_res].astype(str).reset_index(drop=True)
    serie2 = df[c2_res].astype(str).reset_index(drop=True)
    esperados = pd.concat([serie1, serie2], ignore_index=True)

    esperados_norm = normalize_series(esperados, do_upper=True)
    esperados_norm = esperados_norm[esperados_norm.str.len() > 0].unique().tolist()

    st.success(f"Leídos {len(esperados_norm)} seriales 'esperados' de {c1_res} + {c2_res}.")

    # ---- 4) Cargar PDF/TXT ----
    try:
        raw_text = extract_text_from_file(pdf_file)
    except Exception as e:
        st.error(f"No se pudo extraer texto del archivo. Detalle: {e}")
        st.stop()

    if not raw_text.strip():
        st.error("⚠️ El archivo no contiene texto legible. Si es PDF escaneado, aplica OCR antes de subirlo.")
        st.stop()

    # ---- 5) Buscar seriales en el texto ----
    tokens = extract_tokens_by_regex(raw_text, pattern)
    tokens_norm = [normalize_series(pd.Series([t])).iloc[0] for t in tokens]

    faltantes = [s for s in esperados_norm if s not in tokens_norm]

   if faltantes:
    st.error(
        f"No se encontraron {len(faltantes)} seriales en el PDF/TXT. "
        f"Ejemplo: {faltantes[:10]}"
    )

    # --- Exportar faltantes a CSV ---
    import io
    buf = io.StringIO()
    pd.Series(faltantes, name="serial_faltante").to_csv(buf, index=False)
    st.download_button(
        label="📥 Descargar seriales faltantes en CSV",
        data=buf.getvalue(),
        file_name="seriales_faltantes.csv",
        mime="text/csv",
    )
else:
    st.success("✅ Todos los seriales esperados están en la Declaración de Importación.")
