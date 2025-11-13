import streamlit as st
import pandas as pd
import re
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

# <<< añadido: checkbox de diagnóstico avanzado
modo_diagnostico = st.checkbox("Modo diagnóstico avanzado (opcional)")

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

    import re

def _fix_line_wraps(text: str) -> str:
    s = text

    # 1) Si alguna vez el PDF insertó guion + salto, también lo reparamos
    #    (no hace daño aunque tus PDFs no lo usen)
    s = re.sub(r'-\s*\n\s*', '', s)

    # 2) Repara "cortes de renglón" SIN guion dentro de palabras alfanuméricas.
    #    Solo unimos si hay secuencias alfanuméricas de al menos 4 caracteres
    #    a ambos lados del salto, para no pegar frases normales.
    #    Lo hacemos en bucle por si un mismo serial quedó partido varias veces.
    while True:
        new_s = re.sub(
            r'([A-Za-z0-9]{4,})\s*\n\s*([A-Za-z0-9]{4,})',
            r'\1\2',
            s
        )
        if new_s == s:
            break
        s = new_s

    return s

# --- justo después de extraer el texto ---
raw_text = extract_text_from_file(pdf_file)  # o tu función actual
raw_text = _fix_line_wraps(raw_text)         # <-- FIX

if not raw_text.strip():
    st.error("⚠️ El archivo no contiene texto legible. Si es PDF escaneado, aplica OCR antes de subirlo.")
    st.stop()

# ---- 5) Buscar seriales en el texto ----
tokens = extract_tokens_by_regex(raw_text, pattern)
tokens_norm = [normalize_series(pd.Series([t])).iloc[0] for t in tokens]

faltantes = [s for s in esperados_norm if s not in tokens_norm]

# <<< añadido: modo diagnóstico avanzado (solo informativo)
if run_btn and modo_diagnostico:
    st.subheader("🔎 Diagnóstico avanzado")

    with st.expander("📄 Seriales extraídos del PDF/TXT (vista previa)"):
        st.write(f"Se extrajeron {len(tokens_norm)} tokens normalizados.")
        st.dataframe(tokens_norm[:200])

    pdf_duplicados = pd.Series(tokens_norm)
    dups = pdf_duplicados[pdf_duplicados.duplicated()].unique()

    with st.expander("♻ Seriales duplicados en el PDF"):
        if len(dups) > 0:
            st.warning(f"Se encontraron {len(dups)} duplicados en el PDF.")
            st.write(dups)
        else:
            st.info("No se encontraron duplicados en el PDF.")

    extras_pdf = [t for t in tokens_norm if t not in esperados_norm]
    with st.expander("🧩 Seriales en el PDF que NO están en el Excel"):
        if extras_pdf:
            st.warning(f"{len(extras_pdf)} seriales aparecen en el PDF pero no están en tu Excel.")
            st.write(extras_pdf[:50])
        else:
            st.success("No hay seriales extra en el PDF.")

# ---- 6) Resultado final ----
if faltantes:
    st.error(
        f"No se encontraron {len(faltantes)} seriales en el PDF/TXT. "
        f"Ejemplo: {faltantes[:10]}"
    )

    # Exportar faltantes a CSV
    import io
    buf = io.StringIO()
    pd.Series(faltantes, name="serial_faltante").to_csv(buf, index=False)
    st.download_button(
        label="⬇️ Descargar seriales faltantes en CSV",
        data=buf.getvalue(),
        file_name="faltantes.csv",
        mime="text/csv"
    )
else:
    st.success("✅ Todos los seriales esperados están en la Declaración de Importación.")
