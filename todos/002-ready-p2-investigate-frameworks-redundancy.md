---
id: "002"
status: resolved
priority: p2
title: "Investigar se frameworks com libexpat é redundante"
files:
  - setup.py:30-32
---

# Investigar se `frameworks` com libexpat é redundante

## Resultado: NÃO É REDUNDANTE

Testado empiricamente em 2026-02-07:

1. Removida a diretiva `frameworks` do setup.py
2. Build com `MACOSX_DEPLOYMENT_TARGET=12.0`
3. `libexpat.1.dylib` **NÃO apareceu** em `Contents/Frameworks/`

A `libexpat` é caso especial: `pyexpat.so` referencia `/usr/lib/libexpat.1.dylib` (path de sistema). O py2app classifica paths `/usr/lib/` como sistema e não copia. As outras dylibs (libcrypto, libssl, etc.) são do Homebrew (`/opt/homebrew/`) e por isso o py2app copia automaticamente.

**Conclusão:** a diretiva `frameworks` com libexpat é necessária e deve ser mantida.
