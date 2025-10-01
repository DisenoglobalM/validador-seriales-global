import streamlit as st
import pandas as pd
from serial_utils import (
    extract_text_from_pdf,     # puedes dejarlo si lo usas en otro lado
    extract_text_from_file,    # <-- NUEVO
    normalize_series,
    extract_tokens_by_regex,
    fuzzy_match_candidates,
)

st.set_page_config(
    page_title="Validador de Seriales (DI) — 2 columnas",
    page_icon="✅",
    layout="centered"
)

st.info("✅ La app cargó correctamente. Sube Excel/CSV + PDF o TXT para continuar.")

# ---- Inputs ----
xlsx_file = st.file_uploader("Excel con seriales esperados (XLSX o CSV)", type=["xlsx", "csv"])
pdf_file = st.file_uploader("Declaración de Importación (PDF con texto) o TXT", type=["pdf", "txt"])
col1 = st.text_input("Nombre de la columna #1 (Interno)", "SERIAL FISICO INTERNO")
col2 = st.text_input("Nombre de la columna #2 (Externo)", "SERIAL FISICO EXTERNO")
pattern = st.text_input("Patrón (regex) para extraer seriales del PDF/TXT", r"[A-Za-z0-9\-_\/\.]{6,}")

run_btn = st.button("Validar ahora", type="primary", use_container_width=True)

if run_btn:
    if not xlsx_file or not pdf_file:
        st.error("Por favor, sube **ambos** archivos (Excel/CSV y PDF/TXT).")
        st.stop()

    # ---- 1) Cargar Excel o CSV ----
    try:
        if xlsx_file.name.endswith(".csv"):
            df = pd.read_csv(xlsx_file, sep=";")
        else:
            df = pd.read_excel(xlsx_file, engine="openpyxl")
    except Exception as e:
        st.error(f"No se pudo leer el archivo: {e}")
        st.stop()

    # ---- 2) Resolver columnas solicitadas ----
    cols_lower = {c.lower().strip(): c for c in df.columns}
    c1_res = cols_lower.get(col1.lower().strip())
    c2_res = cols_lower.get(col2.lower().strip())

    if not c1_res or not c2_res:
        st.error(f"No encuentro estas columnas: {[col1, col2]}. "
                 f"Columnas disponibles: {list(df.columns)}")
        st.stop()

   # ---- 3) Seriales esperados (normalizados) ----
# serie1 y serie2 ya deben existir como df[c1_res] y df[c2_res]
serie1 = df[c1_res].astype(str).reset_index(drop=True)
serie2 = df[c2_res].astype(str).reset_index(drop=True)

# Une ambas columnas una debajo de la otra
esperados = pd.concat([serie1, serie2], ignore_index=True)

# Normaliza + quita vacíos/nulos + deja únicos (conserva el orden)
esperados_norm = (
    normalize_series(
        esperados,
        do_upper=True,        # MAYÚSCULAS
        strip_spaces=True,    # sin espacios
        strip_dashes=True,    # sin guiones
        strip_dots=True,      # sin puntos
        strip_slashes=True    # sin / y \
    )
    .loc[lambda s: s.str.len() > 0]  # quita vacíos
    .drop_duplicates()
    .tolist()
)

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

   # --------------------------
# Normalizador "duro": deja solo A-Z y 0-9
# --------------------------
def _norm_str(s: str) -> str:
    if s is None:
        return ""
    s = str(s).upper()
    # Nos quedamos solo con alfanuméricos (quitamos TODO lo demás)
    return "".join(ch for ch in s if ch.isalnum())

# Normaliza esperados (2 columnas combinadas) a un set para comparación rápida
esperados_norm = {_norm_str(x) for x in esperados if _norm_str(x)}
# Filtro por longitud razonable (evita ruido), ajusta si necesitas
esperados_norm = {x for x in esperados_norm if 6 <= len(x) <= 30}

# --------------------------
# Tokenizador del texto extraído (sin regex)
# Convierte todo a alfanumérico separando por "no alfanuméricos"
# --------------------------
def _tokenize_alnum(text: str, min_len=3, max_len=40):
    # Reemplazamos cualquier no-alfanumérico por espacio,
    # luego cortamos por espacios y filtramos por longitud.
    buf = []
    for ch in text:
        if ch.isalnum():
            buf.append(ch.upper())
        else:
            buf.append(" ")
    clean = "".join(buf)
    tokens = [t for t in clean.split() if min_len <= len(t) <= max_len]
    return tokens

# Obtener tokens "normalizados" del texto del PDF/TXT
tokens = _tokenize_alnum(raw_text, min_len=3, max_len=40)
encontrados_norm = set(tokens)

# --------------------------
# Comparación
# --------------------------
faltantes = sorted(esperados_norm - encontrados_norm)

# Debug opcional
with st.expander("Depuración de coincidencias"):
    st.write(f"Tokens extraídos (únicos): {len(encontrados_norm)}")
    st.write("Ejemplos de tokens:", list(encontrados_norm)[:50])
    st.write("Ejemplos de esperados:", list(esperados_norm)[:50])

if faltantes:
    st.error(
        f"No se encontraron {len(faltantes)} seriales en el PDF/TXT. "
        f"Ejemplo: {faltantes[:10]}"
    )
else:
    st.success("✅ Todos los seriales esperados aparecen en el archivo PDF/TXT.")
