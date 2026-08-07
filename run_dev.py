# Dev-Starter für die Browser-Vorschau: nutzt den zugewiesenen Port aus der
# Umgebungsvariable PORT (Fallback 8000). Der Vertrieb startet weiterhin start.bat.
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
