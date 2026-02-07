---
id: "005"
status: ready
priority: p3
title: "Adicionar verificação codesign do FFmpeg no build script"
files:
  - scripts/build_dmg.sh
---

# Adicionar verificação codesign do FFmpeg no build script

## Problema

O FFmpeg é baixado via `curl` sem verificação de integridade. O binário é assinado com Developer ID (Martin Riedl, KU3N25YGLU), mas o build script não verifica a assinatura.

## Solução

Adicionar verificação de code signing no `build_dmg.sh`, junto aos outros checks de dependência:

```bash
# Verificar assinatura do FFmpeg
if ! codesign -v bin/ffmpeg 2>/dev/null; then
    echo -e "${RED}Warning: FFmpeg binary is not properly signed${NC}"
    echo "Download a signed build from: https://ffmpeg.martin-riedl.de/"
fi
```

## Contexto

O app será usado por usuários externos. O FFmpeg bundado no DMG deve ser verificado no build para garantir que o binário distribuído é legítimo.
