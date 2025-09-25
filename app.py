# app.py — Validador de Seriales (DI) — 2 columnas
import io
import pandas as pd
import streamlit as st

from serial_utils import (
    extract_text_from_pdf,
    extract_tokens_by_regex,
    normalize_token,
    normalize_series,
    fuzzy_match_candidates,
)

# -----------------------
# Configuración de página
# -----------------------
st.set_page_config(
    page_title="Validador de Seriales — Declaración de Importación",
    page_icon="✅",
    layout="centered",
)

st.title("Validador de Seriales — Declaración de Importación")
st.caption(
    "Sube el **CSV** con los seriales esperados (dos columnas: Interno y Externo) "
    "y la **Declaración** (PDF con texto o TXT)."
)

with st.expander("Configuración (opcional)", expanded=False):
    st.write(
        "Ajusta el patrón y la normalización si tus seriales tienen un formato especial."
    )

# -----------------------
# Parámetros de entrada
# -----------------------
st.subheader("1) Sube los archivos")

col1_name = st.text_input("Nombre de la columna #1 (Interno)", value="SERIAL FISICO INTERNO")
col2_name = st.text_input("Nombre de la columna #2 (Externo)", value="SERIAL FISICO EXTERNO")

# Aceptamos solo CSV para evitar dependencias (openpyxl)
csv_file = st.file_uploader(
    "CSV con seriales esperados (dos columnas: Interno y Externo)",
    type=["csv"],
    help="Guarda tu Excel como CSV (UTF-8).",
)

doc_file = st.file_uploader(
    "Declaración de Importación (PDF con texto o TXT)",
    type=["pdf", "txt"],
)

# Regex de detección en el PDF/TXT
pattern = st.text_input(
    "Patrón (regex) para extraer seriales del documento",
    value=r"[A-Za-z0-9\-_/\.]{6,}",
    help="Si no sabes, deja el valor por defecto.",
)

# Normalización fuerte para comparar
norm_opts = dict(
    do_upper=True,
    strip_spaces=True,
    strip_dashes=True,
    strip_dots=True,
    strip_slashes=True,
)

run_btn = st.button("Validar ahora", type="primary", use_container_width=True)


def read_expected_csv(file: io.BytesIO, col1: str, col2: str) -> pd.DataFrame:
    """Lee CSV esperado, valida columnas y devuelve df con ambas columnas."""
    try:
        df = pd.read_csv(file, encoding="utf-8-sig")
    except Exception as e:
        st.error(f"No se pudo leer el CSV: {e}")
        st.stop()

    cols_lower = {c.lower(): c for c in df.columns}

    def resolve(name: str):
        if name in df.columns:
            return name
        return cols_lower.get(name.lower())

    c1 = resolve(col1)
    c2 = resolve(col2)

    missing = []
    if not c1:
        missing.append(col1)
    if not c2:
        missing.append(col2)

    if missing:
        st.error(
            f"No encuentro estas columnas: {missing}. "
            f"Columnas disponibles: {list(df.columns)}"
        )
        st.stop()

    return df[[c1, c2]].copy()


def get_raw_text_from_doc(uploaded):
    """Devuelve el texto del documento (PDF/TXT)."""
    name = (uploaded.name or "").lower()
    if name.endswith(".txt"):
        try:
            return uploaded.read().decode("utf-8-sig", errors="ignore")
        except Exception as e:
            st.error(f"No pude leer el TXT: {e}")
            st.stop()
    else:
        try:
            return extract_text_from_pdf(uploaded)
        except Exception as e:
            st.error(
                "No se pudo extraer texto del PDF.\n\n"
                f"Detalle técnico: {e}\n\n"
                "Si el PDF es escaneado (imágenes) realiza OCR (convierte a PDF con texto) o "
                "sube un .TXT con el contenido."
            )
            st.stop()


if run_btn:
    # Validaciones básicas de archivos
    if not csv_file or not doc_file:
        st.error("Por favor, sube **ambos** archivos (CSV y PDF/TXT).")
        st.stop()

    # 1) Lee CSV de 'esperados'
    df_exp = read_expected_csv(csv_file, col1_name, col2_name)

    # 2) Normaliza y combina los seriales esperados (interno + externo)
    s1 = normalize_series(df_exp.iloc[:, 0], **norm_opts)
    s2 = normalize_series(df_exp.iloc[:, 1], **norm_opts)
    expected = pd.concat([s1, s2], ignore_index=True)
    expected = expected[expected.astype(bool)]  # quita vacíos
    expected_set = set(expected.tolist())

    st.success(
        f"Leídos **{len(expected_set)}** seriales 'esperados' de {col1_name} + {col2_name}."
    )

    # 3) Obtiene texto del documento y extrae tokens por regex
    raw_text = get_raw_text_from_doc(doc_file)
    tokens = extract_tokens_by_regex(raw_text, pattern)
    tokens_norm = [normalize_token(t, **norm_opts) for t in tokens if t.strip()]
    found_set = set(t for t in tokens_norm if t)

    st.info(f"En el documento se detectaron **{len(found_set)}** tokens únicos.")

    # 4) Comparación
    missing = sorted(expected_set - found_set)
    extras = sorted(found_set - expected_set)

    colA, colB = st.columns(2)
    with colA:
        st.metric("Faltantes", len(missing))
    with colB:
        st.metric("Sobrantes en documento", len(extras))

    # 5) Muestra tablas y descarga
    if missing:
        st.subheader("Faltantes (no aparecieron en la Declaración)")
        df_missing = pd.DataFrame({"serial": missing})

        # Sugerencias fuzzy para cada faltante (opcional, top-3 candidatos)
        sugg_rows = []
        for s in missing[:200]:  # limite para no demorar mucho si hay demasiados
            cands = fuzzy_match_candidates(s, found_set, max_distance=1, top_k=3)
            if cands:
                txt = "; ".join([f"{c} (dist={d})" for c, d in cands])
                sugg_rows.append({"serial": s, "sugerencias": txt})
            else:
                sugg_rows.append({"serial": s, "sugerencias": ""})
        df_sugg = pd.DataFrame(sugg_rows)

        st.dataframe(df_sugg, use_container_width=True, height=300)

        csv_bytes = df_missing.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Descargar faltantes (CSV)",
            data=csv_bytes,
            file_name="faltantes.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.success("✅ No hay faltantes.")

    if extras:
        st.subheader("Sobrantes (aparecen en la Declaración pero no en el CSV)")
        df_extras = pd.DataFrame({"serial": extras})
        st.dataframe(df_extras, use_container_width=True, height=240)

        csv_bytes = df_extras.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ Descargar sobrantes (CSV)",
            data=csv_bytes,
            file_name="sobrantes.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.success("✅ No hay sobrantes.")
