#!/usr/bin/env python3
"""Organizador de pastas com suporte a IA (OpenAI) e fallback local."""

import argparse
import json
import os
import shutil
import textwrap
import urllib.request


DEFAULT_CATEGORIES = [
    "Imagens",
    "Videos",
    "Documentos",
    "Audio",
    "Compactados",
    "Codigo",
    "Outros",
]

EXTENSION_RULES = {
    "Imagens": {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"},
    "Videos": {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm"},
    "Documentos": {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".txt",
        ".md",
        ".rtf",
    },
    "Audio": {".mp3", ".wav", ".aac", ".flac", ".ogg"},
    "Compactados": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Codigo": {
        ".py",
        ".js",
        ".ts",
        ".java",
        ".c",
        ".cpp",
        ".cs",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".html",
        ".css",
        ".json",
        ".yml",
        ".yaml",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Organiza arquivos em subpastas usando IA (OpenAI) ou regras locais.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Exemplos:
              python organizador_ai.py ~/Downloads
              python organizador_ai.py ~/Downloads --apply
              OPENAI_API_KEY=... python organizador_ai.py ~/Downloads --apply
            """
        ),
    )
    parser.add_argument("path", help="Pasta a ser organizada")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica as movimentações (por padrão é dry-run)",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="Modelo OpenAI (default: gpt-4o-mini)",
    )
    parser.add_argument(
        "--categories",
        default=",".join(DEFAULT_CATEGORIES),
        help="Categorias separadas por vírgula",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=200,
        help="Limite de arquivos analisados por execução",
    )
    return parser.parse_args()


def list_files(base_path: str, max_files: int) -> list[str]:
    entries = []
    for name in os.listdir(base_path):
        full_path = os.path.join(base_path, name)
        if os.path.isfile(full_path):
            entries.append(name)
        if len(entries) >= max_files:
            break
    return entries


def categorize_local(filename: str, categories: list[str]) -> str:
    _, ext = os.path.splitext(filename.lower())
    for category, extensions in EXTENSION_RULES.items():
        if ext in extensions and category in categories:
            return category
    return "Outros" if "Outros" in categories else categories[-1]


def call_openai(model: str, api_key: str, filename: str, categories: list[str]) -> str:
    prompt = (
        "Você é um assistente que organiza arquivos em pastas. "
        "Responda apenas com o nome exato da categoria mais adequada.\n\n"
        f"Categorias disponíveis: {', '.join(categories)}\n"
        f"Arquivo: {filename}\n"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Classifique arquivos em categorias."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 20,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    content = result["choices"][0]["message"]["content"].strip()
    return content if content in categories else categorize_local(filename, categories)


def build_plan(
    base_path: str, files: list[str], categories: list[str], use_ai: bool, model: str
) -> dict[str, list[str]]:
    plan: dict[str, list[str]] = {category: [] for category in categories}
    api_key = os.environ.get("OPENAI_API_KEY", "")

    for filename in files:
        category = categorize_local(filename, categories)
        if use_ai and api_key:
            try:
                category = call_openai(model, api_key, filename, categories)
            except Exception:
                category = categorize_local(filename, categories)
        plan.setdefault(category, []).append(filename)
    return plan


def apply_plan(base_path: str, plan: dict[str, list[str]]) -> None:
    for category, files in plan.items():
        if not files:
            continue
        target_dir = os.path.join(base_path, category)
        os.makedirs(target_dir, exist_ok=True)
        for filename in files:
            src = os.path.join(base_path, filename)
            dst = os.path.join(target_dir, filename)
            if os.path.exists(dst):
                continue
            shutil.move(src, dst)


def print_plan(base_path: str, plan: dict[str, list[str]]) -> None:
    print(f"Plano para: {base_path}")
    for category, files in plan.items():
        if not files:
            continue
        print(f"\n📁 {category} ({len(files)} arquivo(s))")
        for filename in files:
            print(f"  - {filename}")


def main() -> None:
    args = parse_args()
    base_path = os.path.abspath(args.path)
    if not os.path.isdir(base_path):
        raise SystemExit("Caminho inválido ou não é uma pasta.")

    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    if not categories:
        raise SystemExit("Você precisa informar pelo menos uma categoria.")

    files = list_files(base_path, args.max_files)
    if not files:
        print("Nenhum arquivo para organizar.")
        return

    use_ai = bool(os.environ.get("OPENAI_API_KEY"))
    plan = build_plan(base_path, files, categories, use_ai, args.model)
    print_plan(base_path, plan)

    if args.apply:
        apply_plan(base_path, plan)
        print("\n✅ Arquivos movidos!")
    else:
        print("\nℹ️ Dry-run: use --apply para mover os arquivos.")


if __name__ == "__main__":
    main()
