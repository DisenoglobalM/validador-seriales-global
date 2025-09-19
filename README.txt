VALIDADOR DE SERIALES — Declaración de Importación (App sin código para el usuario)

Requisitos (una sola vez)
1) Instala Python 3.10 o superior desde https://www.python.org/downloads/
   - Durante la instalación, marca "Add Python to PATH".
2) Descomprime este ZIP en una carpeta sencilla (por ej. C:\validador_seriales)

Instalación
3) Abre una terminal en esa carpeta:
   - Windows: Shift+clic derecho dentro de la carpeta → "Abrir PowerShell aquí"
   - macOS: Terminal → cd /ruta/a/validador_seriales
4) Ejecuta:
   pip install -r requirements.txt

Uso
5) Ejecuta la app:
   streamlit run app.py

6) Se abrirá en tu navegador (normalmente http://localhost:8501).
7) Sube tu Excel con la columna "serial" (o cambia el nombre en la app).
8) Sube el PDF de la Declaración de Importación.
9) (Opcional) Ajusta el patrón (regex) y la normalización.
10) Pulsa "Validar ahora" y descarga el reporte XLSX.

Notas
- Si el PDF es escaneado y no se extrae texto, conviértelo antes con OCR (p.ej., Adobe, ABBYY o Tesseract vía herramientas GUI) y vuelve a intentar.
- La opción "coincidencias aproximadas" ayuda a detectar errores de digitación/OCR (distancia Levenshtein).
- No necesitas saber programar para usar la app, solo seguir los pasos una vez.

Soporte interno
- Puedes compartir la carpeta con el equipo de Importaciones. 
- Si desean, se puede empaquetar como ejecutable (PyInstaller), pero para iniciar es suficiente con `streamlit run`.
