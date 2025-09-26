import streamlit as st
import pandas as pd

from serial_utils import (
    extract_text_from_pdf,
    normalize_token,
    normalize_series,
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

st.title("Validador de Seriales — Declaración de Importación")
st.caption("Sube el Excel/CSV con los seriales esperados y la Declaración en PDF (con texto).")

st.info("✅ La app cargó correctamente. Sube **Excel/CSV + PDF** para continuar.")


# --------------------------------------------
# Lectura y normalización de tabla de esperados
# --------------------------------------------
def _read_expected_table(file, col_interno: str, col_externo: str) -> pd.DataFrame:
    """
    Lee el archivo de seriales (CSV o XLSX), limpia nombres de columnas y
    devuelve un DataFrame con las dos columnas seleccionadas.
    Reintenta con separadores comunes si la autodetección no funciona.
    """
    def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
        df.columns = (
            df.columns
            .astype(str)
            .str.replace("\ufeff", "", regex=False)  # BOM
            .str.strip()
            .str.replace(";", "", regex=False)      # ; pegados al nombre
        )
        return df

    try:
        if file.name.lower().endswith(".csv"):
            # 1) Autodetección
            df = pd.read_csv(file, sep=None, engine="python", encoding="utf-8-sig")
            if df.shape[1] == 1:
                # 2) Reintento con ;
                file.seek(0)
                df = pd.read_csv(file, sep=';', engine="python", encoding="utf-8-sig")
            if df.shape[1] == 1:
                # 3) Reintento con ,
                file.seek(0)
                df = pd.read_csv(file, sep=',', engine="python", encoding="utf-8-sig")
        else:
            # Requiere openpyxl si usas XLSX
            df = pd.read_excel(file, engine="openpyxl")
    except Exception as e:
        st.error(f"No se pudo leer el archivo de seriales: {e}")
        st.stop()

    # Limpia nombres de columna
    df = _clean_columns(df)

    with st.expander("Ver columnas detectadas (depuración)"):
        st.write("Columnas:", list(df.columns))
        st.write("Vista previa:", df.head(3))

    # Resolver nombres de columnas (case-insensitive)
    cols_lower = {c.lower(): c for c in df.columns}
    def resolve(name: str):
        return cols_lower.get(name.lower())

    c1 = resolve(col_interno)
    c2 = resolve(col_externo)
    if not c1 or not c2:
        st.error(
            f"No encuentro estas columnas: {[col_interno, col_externo]}. "
            f"Columnas disponibles: {list(df.columns)}"
        )
        st.stop()

    return df[[c1, c2]].copy()


# ---------------
# Interfaz (UI)
# ---------------
xlsx_file = st.file_uploader(
    "Excel con seriales esperados (XLSX o CSV)",
    type=["xlsx", "csv"],
    help="Si no quieres instalar openpyxl, guarda tu Excel como CSV (UTF-8).",
)

pdf_file = st.file_uploader("Declaración de Importación (PDF con texto)", type=["pdf"])

col1 = st.text_input("Nombre de la columna #1 (Interno)", "SERIAL FISICO INTERNO")
col2 = st.text_input("Nombre de la columna #2 (Externo)", "SERIAL FISICO EXTERNO")

pattern = st.text_input(
    "Patrón (regex) para extraer seriales del PDF",
    r"[A-Za-z0-9\-_/\.]{6,}",
    help="Ajusta el patrón si tus seriales cambian de formato.",
)

run_btn = st.button("Validar ahora", type="primary", use_container_width=True)


# -----------------
# Lógica principal
# -----------------
if run_btn:
    if not xlsx_file or not pdf_file:
        st.error("Por favor, sube **ambos** archivos (Excel/CSV y PDF).")
        st.stop()

    # 1) Lee Excel/CSV + limpia columnas
    df_cols = _read_expected_table(xlsx_file, col1, col2)

    # 2) Combina, normaliza y deja únicos
    all_serials = pd.concat([df_cols.iloc[:, 0], df_cols.iloc[:, 1]], ignore_index=True)
    all_serials = normalize_series(all_serials).astype(str)
    expected_set = set(x for x in all_serials.tolist() if x)

    st.success(f"Leídos **{len(expected_set)}** seriales 'esperados' de {col1} + {col2}.")

    # 3) Extrae texto del PDF (pdfplumber → fallback pdfminer)
    try:
        raw_text = extract_text_from_pdf(pdf_file)
        # Después de:
raw_text = extract_text_from_pdf(pdf_file)

# Añade (OJO a la indentación):
with st.expander("Ver muestra de texto extraído del PDF (depuración)"):
    st.write(f"Longitud del texto extraído: {len(raw_text)} caracteres")
    st.text(raw_text[:2000] or "[vacío]")

    except Exception as e:
        st.error(
            "No se pudo extraer texto del PDF. Verifica que no sea escaneado.\n\n"
            f"Detalle técnico: {e}"
        )
        st.stop()

    if not raw_text.strip():
        st.error(
            "El PDF parece no contener texto legible. "
            "Si es un PDF escaneado (solo imágenes), realiza OCR y vuelve a subirlo."
        )
        st.stop()

    # 4) Extrae tokens por regex y normaliza
    tokens = extract_tokens_by_regex(raw_text, pattern)
    found_set = set(
        normalize_token(
            t,
            do_upper=True,
            strip_spaces=True,
            strip_dashes=True,
            strip_dots=True,
            strip_slashes=True,
        )
        for t in tokens if isinstance(t, str) and t.strip()
    )

    st.info(f"En el documento se detectaron **{len(found_set)}** tokens únicos.")

    # 5) Comparación + métricas
    missing = sorted(expected_set - found_set)
    extras = sorted(found_set - expected_set)

    cA, cB = st.columns(2)
    cA.metric("Faltantes", len(missing))
    cB.metric("Sobrantes", len(extras))

    # 6) Tablas y descargas
    if missing:
        st.subheader("Faltantes (no aparecen en la Declaración)")
        rows = []
        pool = list(found_set)
        # Fuzzy sugerencias (limitado para no demorar si hay miles)
        for s in missing[:200]:
            cands = fuzzy_match_candidates(s, pool, max_distance=1, top_k=3)
            suger = "; ".join([f"{c} (dist={d})" for c, d in cands]) if cands else ""
            rows.append({"serial": s, "sugerencias": suger})
        df_missing = pd.DataFrame(rows)
        st.dataframe(df_missing, use_container_width=True, height=300)

        st.download_button(
            "⬇️ Descargar faltantes (CSV)",
            data=df_missing[["serial"]].to_csv(index=False).encode("utf-8-sig"),
            file_name="faltantes.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.success("✅ No hay faltantes.")

    if extras:
        st.subheader("Sobrantes (aparecen en el PDF pero no en el Excel/CSV)")
        df_extras = pd.DataFrame({"serial": extras})
        st.dataframe(df_extras, use_container_width=True, height=240)

        st.download_button(
            "⬇️ Descargar sobrantes (CSV)",
            data=df_extras.to_csv(index=False).encode("utf-8-sig"),
            file_name="sobrantes.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.success("✅ No hay sobrantes.")
