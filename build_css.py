from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TAILWIND_DIR = ROOT / "build" / "tailwind"
OUTPUT_DIR = ROOT / "app" / "static" / "css"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGETS = [
    ("app.css", "app.js"),
    ("public.css", "public.js"),
    ("login.css", "login.js"),
]


def ensure_deps() -> None:
    node_modules = TAILWIND_DIR / "node_modules" / ".bin"
    if not (node_modules / "tailwindcss.cmd").exists() and not (node_modules / "tailwindcss").exists():
        print("Instalando dependencias de build (tailwindcss + plugins)...")
        subprocess.run(["npm", "install", "--no-audit", "--no-fund"], cwd=TAILWIND_DIR, check=True)


def build() -> int:
    ensure_deps()
    tailwind_bin = (
        TAILWIND_DIR / "node_modules" / ".bin" / "tailwindcss.cmd"
        if sys.platform == "win32"
        else TAILWIND_DIR / "node_modules" / ".bin" / "tailwindcss"
    )
    for out_name, config_name in TARGETS:
        config = TAILWIND_DIR / config_name
        output = OUTPUT_DIR / out_name
        cmd = [
            str(tailwind_bin),
            "-i",
            str(TAILWIND_DIR / "input.css"),
            "-o",
            str(output),
            "-c",
            str(config),
            "--minify",
        ]
        print(f"Building {out_name} ...")
        result = subprocess.run(cmd, cwd=TAILWIND_DIR)
        if result.returncode != 0:
            print(f"Failed to build {out_name}", file=sys.stderr)
            return result.returncode
    print("CSS built successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())