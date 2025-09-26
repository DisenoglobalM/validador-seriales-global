import streamlit as st
import pandas as pd

from serial_utils import (
    extract_text_from_pdf,
    normalize_series,        # aplica normalización de tokens (mayúsculas, sin espacios, etc.)
    normalize_token,         # para listas sueltas
    extract_tokens_by_regex, # aplica regex sobre texto
)

st.set_page_config(
    page_title="Validador de Seriales (DI) — 2 columnas",
    page_icon="✅",
    layout="centered",
)

st.info("✅ La app cargó correctamente. Sube Excel/CSV + PDF o TXT para continuar.")

# -------------------------
# Entrada de archivos
# -------------------------
c1, c2 = st.columns(2, gap="large")

with c1:
    xlsx_file = st.file_uploader(
        "Excel con seriales esperados (XLSX o CSV)",
        type=["xlsx", "csv"],
        help="Debes subir el Excel/CSV con las dos columnas de seriales."
    )

with c2:
    pdf_or_txt_file = st.file_uploader(
        "Declaración de Importación (PDF con texto) o TXT",
        type=["pdf", "txt"],
        help="Si el PDF está escaneado, conviértelo a TXT (OCR) y súbelo aquí."
    )

col1 = st.text_input("Nombre de la columna #1 (Interno)", "SERIAL FISICO INTERNO")
col2 = st.text_input("Nombre de la columna #2 (Externo)", "SERIAL FISICO EXTERNO")

# Patrón regex para extraer seriales del PDF/TXT
pattern = st.text_input(
    "Patrón (regex) para extraer seriales del PDF/TXT",
    r"[A-Za-z0-9\-_\/\.\|]{6,}",
    help="Ajusta si tus seriales tienen otro formato. Mínimo 6 caracteres por defecto."
)

run_btn = st.button("Validar ahora", type="primary", use_container_width=True)

# -------------------------
# Acción principal
# -------------------------
if run_btn:
    # Validación de presencia de archivos
    if not xlsx_file or not pdf_or_txt_file:
        st.error("Por favor, sube **ambos** archivos: Excel/CSV y PDF/TXT.")
        st.stop()

    # -------------------------
    # 1) Cargar Excel/CSV
    # -------------------------
    try:
        if xlsx_file.name.lower().endswith(".csv"):
            df = pd.read_csv(xlsx_file)
        else:
            # Si usas openpyxl y no está, el requirements debe incluirlo.
            df = pd.read_excel(xlsx_file, engine="openpyxl")
    except Exception as e:
        st.error(f"No se pudo leer el Excel/CSV: {e}")
        st.stop()

    # Resolver columnas por nombre (case-insensitive)
    cols_lower = {c.lower(): c for c in df.columns}

    def resolve(name: str):
        return cols_lower.get(name.lower())

    c1_res = resolve(col1)
    c2_res = resolve(col2)

    with st.expander("Ver columnas detectadas (depuración)"):
        st.write("Columnas:")
        st.write(list(df.columns))
        st.write("Vista previa:")
        st.dataframe(df.head(3), use_container_width=True)

    if not c1_res or not c2_res:
        st.error(
            f"No encuentro estas columnas: {repr([col1, col2])}. "
            f"Columnas disponibles: {list(df.columns)}"
        )
        st.stop()

    # ------ Seriales esperados (normalizados) ------
    # Evitamos reindexar sobre índices duplicados: reset_index(drop=True)
    serie1 = df[c1_res].astype(str).reset_index(drop=True)
    serie2 = df[c2_res].astype(str).reset_index(drop=True)

    # Concatenar ambas series (mismo largo o distinto, sin mezclar índices)
    esperados = pd.concat([serie1, serie2], ignore_index=True)

    # Normalizar, quitar vacíos y dejar únicos
    esperados_norm = normalize_series(esperados, do_upper=True)
    esperados_norm = esperados_norm[esperados_norm.str.len() > 0].unique().tolist()

    st.success(
        f"Leídos {len(esperados_norm)} seriales 'esperados' de {c1_res} + {c2_res}."
    )

    # -------------------------
    # 2) Extraer texto del PDF/TXT
    # -------------------------
    raw_text = ""

    if pdf_or_txt_file.name.lower().endswith(".txt"):
        # TXT: lo leemos directo
        try:
            raw_text = pdf_or_txt_file.read().decode("utf-8", errors="ignore")
        except Exception as e:
            st.error(f"No se pudo leer el TXT: {e}")
            st.stop()
    else:
        # PDF: extraemos con pdfplumber (ya envuelto en serial_utils)
        try:
            raw_text = extract_text_from_pdf(pdf_or_txt_file)
        except Exception as e:
            st.error(
                "No se pudo extraer texto del PDF. "
                "Si es un PDF escaneado, realiza OCR y súbelo como TXT. "
                f"Detalle técnico: {e}"
            )
            st.stop()

    with st.expander("Info de depuración del texto extraído"):
        st.write(f"Longitud del texto extraído: {len(raw_text)} caracteres")

    if not raw_text or not raw_text.strip():
        st.error(
            "El PDF/TXT no contiene texto legible. "
            "Si es un PDF escaneado (sólo imágenes), realiza OCR antes de subirlo."
        )
        st.stop()

    # -------------------------
    # 3) Extraer tokens del texto usando el regex
    # -------------------------
    try:
        tokens = extract_tokens_by_regex(raw_text, pattern)
    except Exception as e:
        st.error(f"El patrón regex no es válido: {e}")
        st.stop()

    # Normalizamos los tokens encontrados para comparar en el mismo formato
    tokens_norm = [normalize_token(t) for t in tokens]

    # -------------------------
    # 4) Comparar esperados vs. encontrados
    # -------------------------
    faltantes = [s for s in esperados_norm if s not in tokens_norm]

    if faltantes:
        st.error(
            f"No se encontraron {len(faltantes)} seriales en el documento. "
            f"Ejemplos: {faltantes[:10]}"
        )
    else:
        st.success("✅ Todos los seriales esperados están en la Declaración de Importación / TXT.")
