---
id: "001"
status: ready
priority: p2
title: "Caminho Homebrew hardcoded assume Apple Silicon"
files:
  - setup.py:31
  - scripts/build_dmg.sh:63
---

# Caminho Homebrew hardcoded assume Apple Silicon

## Problema

O caminho `/opt/homebrew/opt/expat/lib/libexpat.1.dylib` assume Apple Silicon. Em máquinas Intel, o Homebrew instala em `/usr/local/`.

## Arquivos

- `setup.py:31` — `frameworks` com path hardcoded
- `scripts/build_dmg.sh:63` — `EXPAT_LIB` com path hardcoded

## Solução

Detectar dinamicamente no build script e passar para setup.py:

```bash
EXPAT_LIB="$(brew --prefix expat)/lib/libexpat.1.dylib"
```

Ou manter hardcoded com comentário explícito que o projeto é Apple Silicon only (conforme README).
