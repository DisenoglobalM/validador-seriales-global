VALIDADOR DE SERIALES — (2 columnas) Declaración de Importación

Novedad: permite seleccionar 2 columnas de seriales (ej. "SERIAL FISICO INTERNO" y "SERIAL FISICO EXTERNO") y las combina en un solo conjunto de "esperados".

Uso en Streamlit Cloud:
- Subir estos archivos a un repo en GitHub.
- Deploy con "Main file path" = app.py

Uso local:
pip install -r requirements.txt
streamlit run app.py

Notas:
- Si el PDF es escaneado, hacer OCR previamente o desplegar en Cloud Run con Tesseract.
- Ajusta el patrón regex y las opciones de normalización según tu formato de seriales.
