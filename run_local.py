from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run_seed() -> None:
    seed_path = ROOT / "seed_db.py"
    subprocess.run([sys.executable, str(seed_path)], cwd=ROOT, check=True)


def ensure_dependencies() -> None:
    requirements = ROOT / "requirements.txt"
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements)], cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inicializador local do Controller Arena.")
    parser.add_argument("--install", action="store_true", help="Instala/atualiza as dependencias antes de subir.")
    parser.add_argument("--seed", action="store_true", help="Recria a base de dados com dados de exemplo antes de subir.")
    parser.add_argument("--host", default="127.0.0.1", help="Host do servidor Flask.")
    parser.add_argument("--port", type=int, default=5000, help="Porta do servidor Flask.")
    parser.add_argument("--no-debug", action="store_true", help="Desliga o modo debug.")
    args = parser.parse_args()

    if args.install:
        ensure_dependencies()

    if args.seed:
        run_seed()

    os.environ.setdefault("FLASK_ENV", "development")

    from app import create_app

    app = create_app()
    app.run(debug=not args.no_debug, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
