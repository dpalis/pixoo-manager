---
title: "fix: Build compatibility for older macOS versions"
type: fix
date: 2026-02-06
---

# fix: Build compatibility for older macOS versions

## Overview

App buildada no macOS 26 (Tahoe) crasha em versoes anteriores com `ImportError: Symbol not found: _XML_SetReparseDeferralEnabled` no `pyexpat.so`. Alem disso, o FFmpeg bundado e x86_64 (Intel) e o `LSMinimumSystemVersion` esta inconsistente com o README.

## Problema

Tres problemas inter-relacionados no pipeline de build:

1. **`MACOSX_DEPLOYMENT_TARGET` nao definido** — py2app usa o macOS da maquina de build como padrao. Binarios compilados linkam contra APIs do macOS 26 que nao existem em versoes anteriores.

2. **`libexpat` nao bundada** — py2app exclui automaticamente dylibs de `/usr/lib/` e `/System/` (filtro `not_system_filter` em `py2app/filters.py:77-81`). O app depende da `libexpat` do sistema do usuario, que pode ter versao diferente.

3. **`LSMinimumSystemVersion: "10.15"`** — Plist declara Catalina como minimo, README diz macOS 12+ Apple Silicon. Inconsistencia que permite o macOS abrir o app em versoes onde ele vai crashar.

4. **FFmpeg x86_64** — Binario bundado e Intel, roda via Rosetta 2. Performance reduzida e risco futuro de incompatibilidade.

## Solucao Proposta

### 1. Definir `MACOSX_DEPLOYMENT_TARGET=12.0` no build script

**Arquivo:** `scripts/build_dmg.sh`
**Onde:** Antes da chamada `python3 setup.py py2app` (linha ~77)

```bash
export MACOSX_DEPLOYMENT_TARGET="12.0"
```

Por que no shell e nao no setup.py: e uma variavel de ambiente padrao do toolchain Apple (clang/ld). Definir no shell e mais explicito e nao esconde config de build dentro do setup.py.

### 2. Bundlar `libexpat` via opcao `frameworks` do py2app

**Arquivo:** `setup.py`
**Onde:** Adicionar `frameworks` ao dict `OPTIONS` (apos linha ~29)

```python
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "resources/Pixoo.icns",
    "frameworks": [
        # libexpat do sistema nao existe no disco desde macOS 11+ (dyld shared cache)
        # Usar versao do Homebrew: brew install expat
        "/opt/homebrew/opt/expat/lib/libexpat.1.dylib",
    ],
    # ... resto
}
```

**Pre-requisito de build:** `brew install expat`

**Por que Homebrew e nao sistema:** Desde macOS Big Sur, dylibs de `/usr/lib/` nao existem mais como arquivos no disco — vivem no dyld shared cache. O py2app nao consegue copiar o que nao existe fisicamente. A versao do Homebrew (compatibility version 13.0.0) e backward-compatible com o que o Python espera (7.0.0).

### 3. Corrigir `LSMinimumSystemVersion` para `"12.0"`

**Arquivo:** `setup.py`, linha 36
**Mudanca:** `"10.15"` -> `"12.0"`

Alinha plist com README e com a realidade (Apple Silicon = macOS 11+, mas macOS 12 e mais seguro como baseline).

### 4. Substituir FFmpeg x86_64 por arm64

**Fonte:** [Martin Riedl's FFmpeg Build Server](https://ffmpeg.martin-riedl.de/)
- Builds arm64 nativas, estaticas, assinadas e notarizadas
- URL estavel: `https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffmpeg.zip`

**Passos:**
1. Baixar binario arm64
2. Verificar arquitetura: `file bin/ffmpeg` deve mostrar `arm64`
3. Verificar que e estatico: `otool -L bin/ffmpeg` deve mostrar apenas `/usr/lib/libSystem.B.dylib`
4. Substituir `bin/ffmpeg` existente

**Arquivo afetado:** `bin/ffmpeg` (gitignored, nao versionado)
**Documentacao:** Atualizar `README.md` secao de FFmpeg com nova fonte de download.

## Arquivos Afetados

| Arquivo | Mudanca |
|---------|---------|
| `scripts/build_dmg.sh` | Adicionar `export MACOSX_DEPLOYMENT_TARGET="12.0"` |
| `setup.py` | Adicionar `frameworks` com libexpat, corrigir `LSMinimumSystemVersion` |
| `bin/ffmpeg` | Substituir binario x86_64 por arm64 |
| `README.md` | Atualizar instrucoes de download do FFmpeg |

## Acceptance Criteria

- [x] `MACOSX_DEPLOYMENT_TARGET=12.0` definido em `build_dmg.sh`
- [x] `libexpat.1.dylib` presente em `Contents/Frameworks/` do `.app` apos build
- [x] `LSMinimumSystemVersion` = `"12.0"` no Info.plist gerado
- [x] `bin/ffmpeg` e arm64: `file bin/ffmpeg` mostra `arm64`
- [ ] Build completo (`scripts/build_dmg.sh`) executa sem erros — .app OK, DMG falha por permissao AppleScript ao Finder (pre-existente)
- [ ] App abre e funciona normalmente apos as mudancas

## Riscos

| Risco | Mitigacao |
|-------|-----------|
| Homebrew expat nao instalado na maquina de build | Adicionar check no build_dmg.sh |
| FFmpeg arm64 tem comportamento diferente do x86_64 | Testar conversao de video/GIF antes de release |
| Outras dylibs com mesmo problema (alem da libexpat) | Testar app em macOS 12-15 se possivel |

## Notas

- Apos resolver, documentar em `docs/solutions/deployment/` usando `/compound-knowledge`
- Pre-requisito novo de build: `brew install expat`
