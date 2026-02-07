---
id: "002"
status: ready
priority: p2
title: "Investigar se frameworks com libexpat é redundante"
files:
  - setup.py:30-32
---

# Investigar se `frameworks` com libexpat é redundante

## Problema

O agente de arquitetura descobriu que py2app já auto-bundla outras dylibs do Homebrew (libcrypto, libssl, liblzma, libmpdec, libsqlite3, libzstd) em `Contents/Frameworks/` sem precisar da diretiva `frameworks`.

A correção real pode ter sido apenas o `MACOSX_DEPLOYMENT_TARGET=12.0`. A diretiva `frameworks` com libexpat pode ser redundante.

## Como testar

1. Remover a diretiva `frameworks` do setup.py
2. Rebuildar com `MACOSX_DEPLOYMENT_TARGET=12.0`
3. Verificar se `libexpat.1.dylib` aparece em `Contents/Frameworks/` mesmo sem a diretiva
4. Se aparecer — remover a diretiva (menos config manual, menos dependência de `brew install expat`)
5. Se não aparecer — manter a diretiva (libexpat é caso especial)

## Impacto

Se redundante, elimina: dependência de `brew install expat`, todo #001 (path hardcoded), e todo #004 (comentário).
