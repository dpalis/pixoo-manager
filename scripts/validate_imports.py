#!/usr/bin/env python3
"""
Valida que todos os imports de terceiros usados em app/ estão cobertos no setup.py.

Uso: python scripts/validate_imports.py
Exit code 0 = tudo coberto, 1 = faltando pacotes.

Rode antes de `python setup.py py2app` para prevenir crashes por ModuleNotFoundError.
"""

import ast
import sys
from pathlib import Path

# Diretório raiz do projeto
PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "app"
SETUP_PY = PROJECT_ROOT / "setup.py"

# Módulos da stdlib do Python 3.10+ (subset relevante)
# Não precisa ser exaustivo — só precisa cobrir o que aparece no código
STDLIB_MODULES = {
    "abc", "asyncio", "base64", "builtins", "collections", "concurrent",
    "contextlib", "copy", "csv", "ctypes", "dataclasses", "datetime",
    "decimal", "difflib", "email", "enum", "errno", "fnmatch", "functools",
    "gc", "getpass", "glob", "grp", "gzip", "hashlib", "hmac", "html",
    "http", "importlib", "inspect", "io", "ipaddress", "itertools", "json",
    "logging", "lzma", "math", "mimetypes", "multiprocessing", "operator",
    "os", "pathlib", "pickle", "pkgutil", "platform", "plistlib",
    "posixpath", "pprint", "queue", "random", "re", "secrets", "select",
    "selectors", "shlex", "shutil", "signal", "socket", "sqlite3", "ssl",
    "string", "struct", "subprocess", "sys", "sysconfig", "tempfile",
    "textwrap", "threading", "time", "timeit", "token", "tokenize",
    "traceback", "types", "typing", "unicodedata", "unittest", "urllib",
    "uuid", "warnings", "weakref", "webbrowser", "xml", "zipfile",
    "zipimport",
}

# Mapeamento: nome do import → nome do pacote no setup.py
# Necessário porque pip name != import name em vários casos
IMPORT_TO_PACKAGE = {
    "PIL": "PIL",
    "pydantic_core": "pydantic_core",
    "imageio_ffmpeg": "imageio_ffmpeg",
    "sse_starlette": "sse_starlette",
    "charset_normalizer": "charset_normalizer",
    "annotated_types": "annotated_types",
    "typing_extensions": "typing_extensions",
}


def extract_imports_from_file(filepath: Path) -> set[str]:
    """Extrai nomes de módulos de terceiros de um arquivo Python."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"  WARN: Não foi possível parsear {filepath}: {e}")
        return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level = alias.name.split(".")[0]
                imports.add(top_level)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top_level = node.module.split(".")[0]
                imports.add(top_level)

    return imports


def extract_setup_packages(setup_path: Path) -> set[str]:
    """Extrai lista de packages e includes do setup.py via AST."""
    source = setup_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(setup_path))

    packages = set()

    for node in ast.walk(tree):
        # Procura atribuições como "packages": [...] e "includes": [...]
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value in ("packages", "includes"):
                    if isinstance(value, ast.List):
                        for elt in value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                # Pegar top-level do nome do pacote
                                top_level = elt.value.split(".")[0]
                                packages.add(top_level)

    return packages


def main():
    print(f"Escaneando imports em {APP_DIR}/...")
    print(f"Lendo packages de {SETUP_PY}...")
    print()

    # 1. Coletar todos os imports de terceiros em app/
    all_imports = set()
    py_files = sorted(APP_DIR.rglob("*.py"))

    for filepath in py_files:
        file_imports = extract_imports_from_file(filepath)
        for imp in file_imports:
            # Filtrar: stdlib, imports internos (app.*), e __future__
            if imp in STDLIB_MODULES:
                continue
            if imp == "app" or imp == "__future__":
                continue
            all_imports.add(imp)

    # 2. Ler packages do setup.py
    setup_packages = extract_setup_packages(SETUP_PY)

    # 3. Mapear imports para nomes esperados no setup.py
    mapped_imports = set()
    for imp in all_imports:
        mapped = IMPORT_TO_PACKAGE.get(imp, imp)
        mapped_imports.add(mapped)

    # 4. Comparar
    missing = mapped_imports - setup_packages
    extra = setup_packages - mapped_imports - {"app"}  # 'app' é interno

    print(f"Imports de terceiros encontrados: {len(all_imports)}")
    print(f"Packages no setup.py: {len(setup_packages)}")
    print()

    if missing:
        print("FALTANDO no setup.py (causam crash no bundle):")
        for pkg in sorted(missing):
            # Encontrar qual arquivo importa esse pacote
            sources = []
            for filepath in py_files:
                file_imports = extract_imports_from_file(filepath)
                original_name = pkg
                # Reverter mapeamento para encontrar o import original
                for orig, mapped in IMPORT_TO_PACKAGE.items():
                    if mapped == pkg:
                        original_name = orig
                        break
                if original_name in file_imports or pkg in file_imports:
                    sources.append(str(filepath.relative_to(PROJECT_ROOT)))
            print(f"  - {pkg} (usado em: {', '.join(sources[:3])})")
        print()

    if extra:
        print("Extras no setup.py (não usados diretamente, podem ser dependências transitivas):")
        for pkg in sorted(extra):
            print(f"  - {pkg}")
        print()

    if missing:
        print("FALHOU: Adicione os pacotes faltantes ao setup.py antes de buildar.")
        return 1
    else:
        print("OK: Todos os imports estão cobertos no setup.py.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
