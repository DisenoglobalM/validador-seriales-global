import io
import streamlit as st
import pandas as pd

from serial_utils import (
    extract_text_from_pdf,
    normalize_series,
    extract_tokens_by_regex,
)

# ---------------------------
# Config
# ---------------------------
st.set_page_config(
    page_title="Validador de Seriales DI (2 columnas)",
    page_icon="✅",
    layout="centered",
)
st.info("✅ La app cargó correctamente. Sube Excel/CSV + PDF o TXT para continuar.")

# ---------------------------
# Utilidades de lectura
# ---------------------------
def _read_table(file) -> pd.DataFrame:
    """
    Lee XLSX o CSV y devuelve un DataFrame:
    - CSV: auto-detecta separador (coma, punto y coma, tab). Reintenta con ; si hiciera falta.
    - XLSX: intenta pandas.read_excel; si falla por falta de openpyxl, pide subir CSV.
    Limpia espacios de encabezados (strip).
    """
    name = (file.name or "").lower()

    if name.endswith(".csv"):
        # Intento 1: auto separador + utf-8
        try:
            file.seek(0)
            df = pd.read_csv(file, sep=None, engine="python")  # sniffer: , ; \t
        except UnicodeDecodeError:
            # Intento 2: latin-1
            file.seek(0)
            df = pd.read_csv(file, sep=None, engine="python", encoding="latin-1")

        # Si vino todo en 1 columna con ; en el nombre, reintenta con ';'
        if len(df.columns) == 1 and ";" in df.columns[0]:
            try:
                file.seek(0)
                df = pd.read_csv(file, sep=";", engine="python")
            except UnicodeDecodeError:
                file.seek(0)
                df = pd.read_csv(file, sep=";", engine="python", encoding="latin-1")

        df.rename(columns=lambda c: str(c).strip(), inplace=True)
        return df

    # XLSX
    try:
        file.seek(0)
        df = pd.read_excel(file)
        df.rename(columns=lambda c: str(c).strip(), inplace=True)
        return df
    except ImportError:
        st.error(
            "No puedo leer XLSX porque falta el motor 'openpyxl'. "
            "Exporta el Excel a **CSV** y súbelo de nuevo."
        )
        st.stop()
    except Exception as e:
        st.error(f"No se pudo leer el Excel: {e}")
        st.stop()


def _read_text_input(file) -> str:
    """
    Lee un PDF o un TXT:
    - TXT: lee texto directamente (utf-8/latin-1).
    - PDF: usa serial_utils.extract_text_from_pdf()
    """
    name = (file.name or "").lower()

    if name.endswith(".txt"):
        # TXT directo
        file.seek(0)
        raw = file.read()
        if isinstance(raw, bytes):
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("latin-1", errors="ignore")
        return str(raw)

    # PDF con texto
    file.seek(0)
    return extract_text_from_pdf(file)


# ---------------------------
# UI
# ---------------------------
left, right = st.columns(2, gap="large")

with left:
    xlsx_file = st.file_uploader(
        "Excel con seriales esperados (XLSX o CSV)",
        type=["xlsx", "csv"]
    )
    if xlsx_file is not None:
        st.caption(f"📄 {xlsx_file.name}")

with right:
    pdf_or_txt = st.file_uploader(
        "Declaración de Importación (PDF con texto) o TXT exportado del PDF",
        type=["pdf", "txt"]
    )
    if pdf_or_txt is not None:
        st.caption(f"📄 {pdf_or_txt.name}")

col1_name = st.text_input("Nombre de la columna #1 (Interno)", "SERIAL FISICO INTERNO")
col2_name = st.text_input("Nombre de la columna #2 (Externo)", "SERIAL FISICO EXTERNO")

pattern = st.text_input(
    "Patrón (regex) para extraer seriales del PDF/TXT",
    r"[A-Za-z0-9\-\_/\.]{6,}",  # seguro y flexible
    help="Ajusta si lo necesitas; por defecto: letras/números y - _ / . de longitud mínima 6"
)

run = st.button("Validar ahora", type="primary", use_container_width=True)

# ---------------------------
# Lógica principal
# ---------------------------
if run:
    # Validaciones iniciales
    if not xlsx_file or not pdf_or_txt:
        st.error("Por favor, sube **ambos** archivos: Excel/CSV y PDF/TXT.")
        st.stop()

    # ---- Excel/CSV
    df = _read_table(xlsx_file)
    st.expander("Ver columnas detectadas (depuración)", expanded=False).write(
        {"Columnas": list(df.columns), "Vista previa": df.head(3)}
    )

    # Resolver columnas informadas por el usuario (case-insensitive, strip)
    cols_lower = {str(c).strip().lower(): c for c in df.columns}
    c1 = cols_lower.get(col1_name.strip().lower())
    c2 = cols_lower.get(col2_name.strip().lower())
    if not c1 or not c2:
        st.error(
            f"No encuentro estas columnas: { [col1_name, col2_name] }. "
            f"Columnas disponibles: {list(df.columns)}"
        )
        st.stop()

  # ------ Seriales esperados (normalizados) ------
# No escribimos en df; usamos una serie temporal.
serie1 = df[c1].astype(str).reset_index(drop=True)
serie2 = df[c2].astype(str).reset_index(drop=True)

esperados = pd.concat([serie1, serie2], ignore_index=True)

# Normaliza, quita nulos / vacíos y deja únicos
esperados_norm = normalize_series(esperados, do_upper=True)
esperados_norm = esperados_norm[esperados_norm.str.len() > 0].unique().tolist()

st.success(f"Leídos {len(esperados_norm)} seriales 'esperados' de {c1} + {c2}.")

    # ---- Tokens encontrados en el PDF/TXT
    tokens = extract_tokens_by_regex(raw_text, pattern)
    # normaliza cada token
    tokens_norm = normalize_series(pd.Series(tokens), do_upper=True).tolist()

    # ---- Comparación
    faltantes = [s for s in esperados_norm if s not in set(tokens_norm)]

    if faltantes:
        st.error(f"❌ No se encontraron {len(faltantes)} seriales. Ejemplo: {faltantes[:10]}")
        with st.expander("Ver lista completa de faltantes"):
            st.write(faltantes)
    else:
        st.success("✅ Todos los seriales esperados están en la Declaración de Importación / TXT.")
