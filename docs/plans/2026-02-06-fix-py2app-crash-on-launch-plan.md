---
title: "fix: py2app crash on launch for external users"
type: fix
date: 2026-02-06
branch: fix/crash-v1.4
---

# fix: py2app crash on launch for external users

## Overview

O app Pixoo Manager empacotado via py2app crasheia ao abrir, exibindo o diálogo genérico de erro do macOS ("Pixoo quit unexpectedly"). A investigação identificou **9 causas raiz** — desde pacotes faltando no bundle até ausência total de error handling para o usuário final.

Este plano cobre: correção das dependências, wrapper de erro com diálogo nativo, e ferramentas de validação para prevenir regressões.

## Problem Statement

Quando um **usuário externo** (sem Python/pip instalado) abre o `Pixoo.app`:

1. py2app executa `app/main.py` como script
2. Imports no topo do arquivo tentam carregar módulos que **não estão no bundle**
3. Python levanta `ImportError` / `ModuleNotFoundError`
4. py2app exibe diálogo genérico sem informação útil
5. Usuário não consegue usar o app nem reportar o erro

**Impacto:** 100% dos usuários externos são afetados — o app simplesmente não abre.

## Root Cause Analysis

### Causa 1: Pacotes faltando no `setup.py` `packages`

**Arquivos afetados e chain de importação até o crash:**

| Pacote | Arquivo que importa | Chain até main.py | Tipo |
|--------|---------------------|-------------------|------|
| `requests` | `services/pixoo_connection.py:20` | main → connection router → service | module-level |
| `httpx` | `routers/youtube.py:14` | main → youtube router | module-level |
| `packaging` | `services/updater.py:19` | main → system router → service | module-level |
| `multipart` | dependência de FastAPI para `UploadFile` | main → FastAPI init | runtime |

Todos são imports de **nível de módulo** — crasheiam antes de chegar ao `if __name__ == "__main__"`.

### Causa 2: Hidden imports do uvicorn não detectados pelo py2app

Uvicorn carrega módulos internos via `importlib` (imports dinâmicos). O analisador estático do py2app não os detecta:

```
uvicorn.lifespan.on
uvicorn.lifespan.off
uvicorn.protocols.http.h11_impl
uvicorn.protocols.http.httptools_impl
uvicorn.protocols.websockets.auto
uvicorn.loops.auto
uvicorn.logging
```

**Referência:** [pyinstaller-fastapi hidden imports](https://github.com/iancleary/pyinstaller-fastapi), [uvicorn discussion #1820](https://github.com/encode/uvicorn/discussions/1820)

### Causa 3: `LSUIElement: True` ausente no plist

O app usa `rumps` para menu bar (`menubar.py`). Sem `LSUIElement: True`:
- App aparece no Dock (comportamento incorreto para menu bar app)
- macOS pode não inicializar corretamente o NSApplication como "agent app"

**Referência:** [rumps issue #4](https://github.com/jaredks/rumps/issues/4)

### Causa 4: `IMAGEIO_FFMPEG_EXE` não é setado cedo o suficiente

Em `services/video_converter.py:26-27`, a env var é setada no topo do módulo — mas depois do import de moviepy (linha 15). O timing funciona por acaso (moviepy lê a env var lazily), mas é frágil.

Além disso, `bin/ffmpeg` não existe no repositório (está no `.gitignore`). O `DATA_FILES` no setup.py referencia `("bin", ["bin/ffmpeg"])` — o **build falha** se o arquivo não existir.

**Referência:** [py2app issue #469](https://github.com/ronaldoussoren/py2app/issues/469), [moviepy issue #1158](https://github.com/Zulko/moviepy/issues/1158)

### Causa 5: Sem error handling no startup

O bloco `if __name__ == "__main__"` em `main.py:273` não tem try/except global. Pior: crashes nos imports do topo do arquivo (linhas 8-39) acontecem **antes** de qualquer código de tratamento ser alcançado.

### Causa 6: Sem validação de build

Não existe script para verificar se o `.app` construído funciona antes de distribuir.

### Causa 7: Dependências transitivas potencialmente ausentes

Pacotes como `requests` puxam `certifi`, `urllib3`, `idna`. O `pydantic` v2 usa `annotated_types`, `pydantic_core`. Se py2app não resolver essas transitivas automaticamente (e frequentemente não resolve para C extensions), o app crasheia.

### Causa 8: `moviepy>=1.0.3` no requirements, mas codebase usa API v2

O código usa `VideoFileClip.subclipped()` e `.cropped()` — métodos do moviepy 2.x. O requirement permite moviepy 1.x, que usa `subclip()` e `crop()`. Se py2app resolver moviepy 1.x, o app crasheia ao processar vídeo.

### Causa 9: Permissão de execução do ffmpeg no bundle

py2app copia DATA_FILES para `Contents/Resources/`. Binários podem perder o bit `+x`. Sem permissão de execução, conversão de vídeo falha silenciosamente.

## Technical Approach

### Decisão arquitetural: Entry point separado (launcher.py)

O wrapper de erro **não pode** ficar no `main.py`, porque imports no topo do arquivo crasheiam antes de qualquer try/except no `__main__`.

**Solução:** Criar `launcher.py` como entry point do py2app, que faz:

```python
# launcher.py (pseudocódigo)
try:
    from app.main import ...  # Aqui é onde os ImportErrors acontecem
    # ... run app ...
except Exception as e:
    # Log crash + mostra diálogo nativo via osascript
```

**Por que `osascript`:** É a única forma de mostrar um diálogo nativo que funciona sem **nenhuma** dependência Python. Se o crash for no import de `rumps` ou `tkinter` (excluído), `osascript` ainda funciona — é binário do macOS.

### Implementation Phases

---

#### Phase 1: Corrigir `setup.py` (P0 — sem isso o app não abre)

**Arquivo:** `setup.py`

**1.1 Adicionar pacotes faltantes ao `packages`:**

```python
"packages": [
    # --- Já existentes (manter) ---
    "uvicorn", "fastapi", "starlette", "PIL", "moviepy", "yt_dlp",
    "zeroconf", "rumps", "anyio", "jinja2", "pydantic", "scipy",
    "charset_normalizer", "imageio", "numpy", "aiofiles", "httptools",
    "app",
    # --- Novos (adicionar) ---
    "requests",           # pixoo_connection.py — HTTP com Pixoo
    "httpx",              # youtube.py router — HTTP async
    "packaging",          # updater.py — comparação de versões
    "multipart",          # FastAPI UploadFile dependency
    "pydantic_core",      # pydantic v2 C extension
    "certifi",            # requests SSL certificates
    "h11",                # uvicorn HTTP transport
    "imageio_ffmpeg",     # moviepy ffmpeg discovery
    "annotated_types",    # pydantic v2 dependency
    "typing_extensions",  # pydantic/fastapi dependency
    "sniffio",            # anyio dependency
    "idna",               # requests dependency
    "urllib3",            # requests dependency
],
```

**1.2 Adicionar hidden imports do uvicorn:**

```python
"includes": [
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.loops.auto",
    "uvicorn.logging",
],
```

**1.3 Adicionar `LSUIElement: True` ao plist:**

```python
"plist": {
    # ... existentes ...
    "LSUIElement": True,  # Menu bar app — sem ícone no Dock
},
```

**1.4 Tornar `bin/ffmpeg` condicional no DATA_FILES:**

O `bin/ffmpeg` não existe no repositório. O build falha se o arquivo não existir. Tornar condicional:

```python
import os

DATA_FILES = [
    ("", ["resources/Pixoo.icns"]),
    ("templates", ["app/templates/base.html"]),
    ("static", ["app/static/favicon.ico"]),
    ("static/css", ["app/static/css/styles.css"]),
    ("static/js", ["app/static/js/app.js"]),
    ("static/vendor", [
        "app/static/vendor/alpine.min.js",
        "app/static/vendor/pico.min.css",
        "app/static/vendor/cropper.min.js",
        "app/static/vendor/cropper.min.css",
    ]),
]

# Incluir ffmpeg apenas se existir (download separado)
if os.path.exists("bin/ffmpeg"):
    DATA_FILES.append(("bin", ["bin/ffmpeg"]))
```

**1.5 Atualizar `requirements.txt`:**

Alterar `moviepy>=1.0.3` para `moviepy>=2.0.0` (codebase usa API v2: `.subclipped()`, `.cropped()`).

---

#### Phase 2: Criar `launcher.py` como entry point (P1 — protege o usuário)

**Novo arquivo:** `launcher.py` (raiz do projeto)

Responsabilidades:
1. Envolver **todo** o startup em try/except
2. Em caso de erro, gravar crash log em `~/.pixoo_manager/crash.log`
3. Exibir diálogo nativo macOS via `osascript` (zero dependências Python)
4. Incluir no crash log: versão do app, versão macOS, arquitetura, traceback completo

**Estrutura do launcher.py:**

```python
"""
Launcher para Pixoo Manager empacotado com py2app.

Este é o entry point do .app. Envolve todo o startup em error handling
para que crashes mostrem um diálogo útil em vez do genérico do macOS.
"""
import os
import sys
import traceback
import subprocess
import platform
from pathlib import Path
from datetime import datetime


def show_error_dialog(title: str, message: str):
    """Mostra diálogo nativo macOS via osascript (zero dependências Python)."""
    # Truncar mensagem para evitar problemas com osascript
    short_msg = message[:500] + "..." if len(message) > 500 else message
    # Escapar aspas para AppleScript
    short_msg = short_msg.replace('"', '\\"').replace("'", "\\'")
    script = f'display dialog "{short_msg}" with title "{title}" buttons {{"OK"}} default button "OK" with icon stop'
    try:
        subprocess.run(["osascript", "-e", script], timeout=30)
    except Exception:
        pass  # Se até osascript falhar, nada mais a fazer


def write_crash_log(error: Exception) -> Path:
    """Grava crash log em ~/.pixoo_manager/crash.log."""
    log_dir = Path.home() / ".pixoo_manager"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "crash.log"

    try:
        version = "unknown"
        try:
            from app.__version__ import __version__
            version = __version__
        except Exception:
            pass

        content = (
            f"=== Pixoo Manager Crash Report ===\n"
            f"Date: {datetime.now().isoformat()}\n"
            f"App Version: {version}\n"
            f"Python: {sys.version}\n"
            f"macOS: {platform.mac_ver()[0]}\n"
            f"Architecture: {platform.machine()}\n"
            f"Frozen: {getattr(sys, 'frozen', False)}\n"
            f"Executable: {sys.executable}\n"
            f"\n--- Traceback ---\n"
            f"{traceback.format_exc()}\n"
            f"\n--- sys.path ---\n"
            f"{chr(10).join(sys.path)}\n"
        )
        log_file.write_text(content, encoding="utf-8")
        return log_file
    except Exception:
        return log_file


def main():
    """Entry point principal — toda exceção é capturada."""
    try:
        # Setar IMAGEIO_FFMPEG_EXE ANTES de qualquer import de moviepy/imageio
        # Em app frozen, o ffmpeg está em Contents/Resources/bin/ffmpeg
        frozen = getattr(sys, 'frozen', False)
        if frozen == 'macosx_app':
            resources_dir = Path(sys.executable).parent.parent / "Resources"
            ffmpeg_path = resources_dir / "bin" / "ffmpeg"
            if ffmpeg_path.exists():
                os.environ["IMAGEIO_FFMPEG_EXE"] = str(ffmpeg_path)
                os.environ["FFMPEG_BINARY"] = str(ffmpeg_path)
                # Adicionar ao PATH também (para yt-dlp)
                ffmpeg_dir = str(ffmpeg_path.parent)
                current_path = os.environ.get("PATH", "")
                if ffmpeg_dir not in current_path:
                    os.environ["PATH"] = f"{ffmpeg_dir}:{current_path}"

        # Agora sim, importar e rodar o app
        from app.main import (
            app, HOST, PORT, HEADLESS, _run_server, _wait_for_server,
            setup_logging, run_menu_bar_if_available
        )

        # Delegar para a lógica existente do main.py
        run_app()

    except Exception as e:
        log_file = write_crash_log(e)
        error_type = type(e).__name__
        error_msg = str(e)

        dialog_msg = (
            f"O Pixoo Manager encontrou um erro ao iniciar.\n\n"
            f"Erro: {error_type}: {error_msg}\n\n"
            f"Um log detalhado foi salvo em:\n"
            f"{log_file}\n\n"
            f"Envie este arquivo ao desenvolvedor para diagnóstico."
        )
        show_error_dialog("Pixoo Manager - Erro ao iniciar", dialog_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Atualizar `setup.py`:**

```python
APP = ["launcher.py"]  # Em vez de "app/main.py"
```

**Refatorar `app/main.py`:**

Extrair a lógica do `if __name__ == "__main__"` para uma função `run_app()` importável pelo launcher. O `__main__` block continua funcionando para desenvolvimento (`python -m app.main`), mas o launcher é o entry point do `.app`.

> **NOTA PARA O EXECUTOR:** O `launcher.py` acima é um **esboço estrutural**. A implementação final deve:
> - Importar apenas stdlib no topo (os, sys, traceback, subprocess, platform, pathlib, datetime)
> - Fazer todos os imports do app DENTRO do try/except
> - Manter o `app/main.py` funcionando para dev (`python -m app.main`)
> - A função que o launcher importa do main.py precisa ser definida — sugiro extrair o bloco `__main__` em uma função `run_app()`

---

#### Phase 3: Setar ffmpeg env vars no ponto correto (P0)

**Contexto:** Hoje o setup de env vars está em `services/video_converter.py:26-27` e `services/youtube_downloader.py:18-22`. Com o launcher, isso move para **antes** de qualquer import do app.

**Ação 1:** O `launcher.py` (Phase 2) já seta `IMAGEIO_FFMPEG_EXE`, `FFMPEG_BINARY` e `PATH` antes do import de `app.main`. Isso resolve o timing.

**Ação 2:** Manter o setup existente em `video_converter.py` e `youtube_downloader.py` como **fallback** para modo desenvolvimento (quando não roda via launcher). Não precisa remover.

**Ação 3:** Adicionar post-build step para garantir permissão de execução:

```bash
# No script de build ou no build_dmg.sh
chmod +x dist/Pixoo.app/Contents/Resources/bin/ffmpeg 2>/dev/null || true
```

---

#### Phase 4: Script de validação de imports (P2 — previne regressões)

**Novo arquivo:** `scripts/validate_imports.py`

**O que faz:**
1. Escaneia recursivamente todos os `.py` em `app/` com AST parser
2. Extrai todos os imports de terceiros (excluindo stdlib e imports internos `app.*`)
3. Lê `setup.py` e extrai a lista de `packages` e `includes`
4. Compara: se algum import do código não está coberto, **falha com exit code 1**
5. Imprime relatório claro do que está faltando

**Quando rodar:** Antes de `python setup.py py2app`. Pode ser integrado no `build_dmg.sh`.

**Mapeamento de nomes:** O script precisa lidar com divergências nome-pip vs nome-import:
- `python-multipart` → `multipart`
- `Pillow` → `PIL`
- `sse-starlette` → `sse_starlette`
- `imageio-ffmpeg` → `imageio_ffmpeg`

---

#### Phase 5: Smoke test pós-build (P2 — valida artefato final)

**Novo arquivo:** `scripts/smoke_test.sh`

**O que faz:**

```bash
#!/bin/bash
# Smoke test para o .app bundled
# IMPORTANTE: Usa o executável do BUNDLE, não o Python do sistema

APP="dist/Pixoo.app/Contents/MacOS/Pixoo"
TIMEOUT=15
PORT=8000

# 1. Verifica que o bundle existe
test -f "$APP" || { echo "FAIL: Bundle not found at $APP"; exit 1; }

# 2. Verifica que ffmpeg bundled é executável (se existir)
FFMPEG="dist/Pixoo.app/Contents/Resources/bin/ffmpeg"
if [ -f "$FFMPEG" ] && [ ! -x "$FFMPEG" ]; then
    echo "FAIL: ffmpeg exists but is not executable"
    exit 1
fi

# 3. Lança o app em background com env headless
PIXOO_HEADLESS=true "$APP" &
PID=$!
sleep $TIMEOUT

# 4. Verifica que o servidor responde
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/" 2>/dev/null)
kill $PID 2>/dev/null
wait $PID 2>/dev/null

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
    echo "PASS: Server responded with HTTP $HTTP_CODE"
else
    echo "FAIL: Expected HTTP 200 or 302, got $HTTP_CODE"
    # Mostrar crash log se existir
    CRASH_LOG="$HOME/.pixoo_manager/crash.log"
    if [ -f "$CRASH_LOG" ]; then
        echo "--- Crash Log ---"
        cat "$CRASH_LOG"
    fi
    exit 1
fi

# 5. Verifica referências a libs externas ao bundle
echo "Checking for external library references..."
LEAKS=$(find dist/Pixoo.app -name "*.so" -o -name "*.dylib" 2>/dev/null | \
    xargs otool -L 2>/dev/null | \
    grep -v "@executable_path" | grep -v "@rpath" | \
    grep -v "@loader_path" | grep -v "/usr/lib" | \
    grep -v "/System" | grep -v ":" | grep -v "^$")

if [ -n "$LEAKS" ]; then
    echo "WARNING: External library references found (may cause crash on other machines):"
    echo "$LEAKS"
fi

echo "Smoke test passed."
```

**CRÍTICO:** O teste usa `PIXOO_HEADLESS=true` para não abrir browser/menubar. O modo headless já existe no `main.py` (variável `HEADLESS`, linha 43).

---

## Acceptance Criteria

### Functional Requirements

- [ ] App `.app` abre sem crash em máquina sem Python instalado
- [ ] Menu bar aparece (ícone no topo da tela, sem ícone no Dock)
- [ ] Browser abre automaticamente em `http://127.0.0.1:8000`
- [ ] Todas as tabs funcionam (Mídia, YouTube, Texto, Galeria)
- [x] Se o app crashear, diálogo nativo mostra erro legível
- [x] Crash log é gravado em `~/.pixoo_manager/crash.log` com traceback + info do sistema
- [x] Script `validate_imports.py` detecta pacotes faltantes no setup.py
- [ ] Script `smoke_test.sh` passa após build bem-sucedido

### Non-Functional Requirements

- [x] Zero dependências Python no error handling (usa apenas osascript + stdlib)
- [x] Crash log inclui: versão do app, versão macOS, arquitetura, traceback, sys.path
- [x] Smoke test usa o executável do bundle (não o Python do sistema)
- [x] `app/main.py` continua funcionando para dev (`python -m app.main`)

### Quality Gates

- [ ] `python setup.py py2app` compila sem erros
- [ ] `scripts/validate_imports.py` passa (exit code 0)
- [ ] `scripts/smoke_test.sh` passa (HTTP 200 ou 302)
- [ ] Teste manual: abrir `.app` via Finder em máquina de build

## Risk Analysis & Mitigation

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Dependência transitiva não coberta | Média | Crash no startup | Script de validação + teste em máquina limpa |
| ffmpeg perde permissão +x no bundle | Alta | Vídeo não converte | Post-build `chmod +x` no build_dmg.sh |
| `osascript` bloqueado em macOS futuro | Baixa | Diálogo não aparece | Fallback: gravar log em `~/Desktop/` |
| Porta 8000 ocupada (instância duplicada) | Média | App "abre" mas mostra página errada | Fora de escopo — bug pré-existente, documentar |
| moviepy 1.x instalado apesar do requirement | Baixa | Crash em conversão de vídeo | Pin `moviepy>=2.0.0` no requirements.txt |
| Arquitetura arm64/x86_64 mismatch no ffmpeg | Média | ffmpeg não executa | Documentar no README que o build é arch-specific |

## Fora de Escopo (conscientemente excluído)

- **Code signing e notarization** — problema separado, não causa o crash atual
- **Porta 8000 ocupada** — bug pré-existente, merece issue própria
- **CI/CD automatizado** — smoke test é manual por enquanto
- **Suporte a macOS 10.15 (Catalina)** — Python 3.10+ e numpy/scipy podem não suportar; considerar atualizar `LSMinimumSystemVersion` em issue separada
- **Universal binary (arm64 + x86_64)** — requer build separado por arquitetura

## Files Changed (referência rápida)

| Arquivo | Ação | Phase |
|---------|------|-------|
| `setup.py` | Editar — packages, includes, plist, DATA_FILES, APP entry point | 1 |
| `requirements.txt` | Editar — moviepy>=2.0.0 | 1 |
| `launcher.py` | **Criar** — entry point com error handling | 2 |
| `app/main.py` | Editar — extrair lógica __main__ para função importável | 2 |
| `scripts/build_dmg.sh` | Editar — adicionar chmod +x do ffmpeg | 3 |
| `scripts/validate_imports.py` | **Criar** — validação de imports vs setup.py | 4 |
| `scripts/smoke_test.sh` | **Criar** — teste pós-build | 5 |

## References & Research

### Issues do py2app (problemas conhecidos)
- [py2app #469 — Bundling ffmpeg binary](https://github.com/ronaldoussoren/py2app/issues/469)
- [py2app #478 — App only works on build machine](https://github.com/ronaldoussoren/py2app/issues/478)
- [py2app #472 — @rpath and libffi](https://github.com/ronaldoussoren/py2app/issues/472)
- [py2app #511 — Carbon library error on Sonoma](https://github.com/ronaldoussoren/py2app/issues/511)
- [py2app #261 — applicationDidFinishLaunching not invoked](https://github.com/ronaldoussoren/py2app/issues/261)

### Issues de dependências específicas
- [moviepy #1158 — ffmpeg not found in frozen app](https://github.com/Zulko/moviepy/issues/1158)
- [moviepy #906 — ModuleNotFound imageio_ffmpeg](https://github.com/Zulko/moviepy/issues/906)
- [imageio #766 — imageio_ffmpeg in frozen apps](https://github.com/imageio/imageio/issues/766)
- [pydantic #6557 — pydantic_core not found in bundle](https://github.com/pydantic/pydantic/issues/6557)
- [Pillow #4001 — py2app bundling Mach-O header](https://github.com/python-pillow/Pillow/issues/4001)
- [rumps #4 — launch failure with py2app](https://github.com/jaredks/rumps/issues/4)
- [PyInstaller #1917 — LSUIElement bug](https://github.com/pyinstaller/pyinstaller/issues/1917) (por que NÃO usar PyInstaller)

### Documentação oficial
- [py2app debugging guide](https://py2app.readthedocs.io/en/latest/debugging.html)
- [py2app options](https://py2app.readthedocs.io/en/latest/options.html)
- [py2app environment](https://py2app.readthedocs.io/en/latest/environment.html)
- [imageio freezing guide](https://imageio.readthedocs.io/en/stable/user_guide/freezing.html)

### Referências de implementação
- [pyinstaller-fastapi — hidden imports list](https://github.com/iancleary/pyinstaller-fastapi)
- [uvicorn discussion #1820 — frozen app workers](https://github.com/encode/uvicorn/discussions/1820)
- [Python macOS app signing guide](https://haim.dev/posts/2020-08-08-python-macos-app/)
