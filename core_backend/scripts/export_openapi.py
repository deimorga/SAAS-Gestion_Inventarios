#!/usr/bin/env python3
"""
Exporta el esquema OpenAPI de la aplicación como JSON estático.

Uso:
    python scripts/export_openapi.py [output_path]

    output_path: ruta de salida (default: doc/api/openapi.json relativo al repo)

Ejemplos:
    python scripts/export_openapi.py
    python scripts/export_openapi.py /tmp/openapi.json
"""
import json
import sys
from pathlib import Path

# Agregar el directorio core_backend al PYTHONPATH para importar la app
_script_dir = Path(__file__).resolve().parent
_core_dir = _script_dir.parent
sys.path.insert(0, str(_core_dir))

# Silenciar el loop de expiración de reservas durante la exportación
import os
os.environ.setdefault("APP_ENV", "export")

from app.main import app  # noqa: E402

schema = app.openapi()

default_output = _core_dir.parent / "doc" / "api" / "openapi.json"
output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_output

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"OpenAPI schema exportado → {output_path}")
print(f"  Versión : {schema.get('info', {}).get('version', 'N/A')}")
print(f"  Endpoints: {len(schema.get('paths', {}))}")
