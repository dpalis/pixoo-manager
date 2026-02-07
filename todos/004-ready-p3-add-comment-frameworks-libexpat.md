---
id: "004"
status: ready
priority: p3
title: "Adicionar comentário explicativo no frameworks do setup.py"
files:
  - setup.py:30-32
blocked_by:
  - "002"
---

# Adicionar comentário explicativo no `frameworks` do setup.py

## Problema

O plano (`docs/plans/2026-02-06-fix-build-macos-compatibility-plan.md`) tem explicação sobre por que libexpat precisa ser bundlada, mas o setup.py não tem nenhum comentário.

## Solução

```python
"frameworks": [
    # libexpat não existe no disco desde macOS 11+ (dyld shared cache).
    # py2app não consegue copiar do shared cache, então usamos a do Homebrew.
    # Pré-requisito: brew install expat
    "/opt/homebrew/opt/expat/lib/libexpat.1.dylib",
],
```

## Nota

Bloqueado por #002. Se a investigação concluir que a diretiva é redundante, este item é irrelevante — tudo será removido.
