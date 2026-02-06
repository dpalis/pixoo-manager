---
status: resolved
priority: p2
issue_id: "001"
tags: [code-review, architecture, duplication]
dependencies: []
---

# Centralizar configuracao de ffmpeg em um unico lugar

## Problem Statement

A logica de configurar environment variables para ffmpeg esta espalhada em 3 arquivos, cada um setando um subconjunto diferente de variaveis. Quando alguem mudar a estrutura do ffmpeg bundled, vai precisar atualizar 3 arquivos e provavelmente vai esquecer um deles.

## Findings

Cobertura inconsistente por arquivo:

| Local | IMAGEIO_FFMPEG_EXE | FFMPEG_BINARY | PATH |
|---|---|---|---|
| `launcher.py:78-87` | Sim | Sim | Sim |
| `app/services/video_converter.py:26-27` | Sim | Nao | Nao |
| `app/services/youtube_downloader.py:18-22` | Nao | Nao | Sim |

- O `launcher.py` cobre tudo, mas so roda no caso bundled (py2app)
- Em desenvolvimento (sem launcher), `video_converter.py` seta `IMAGEIO_FFMPEG_EXE` mas nao `FFMPEG_BINARY`
- `youtube_downloader.py` adiciona ao PATH mas nao seta env vars do imageio
- Violacao direta do principio "mesmo conhecimento espalhado em varios lugares" do CLAUDE.md

## Proposed Solutions

### Option 1: Centralizar em app/config.py

**Approach:** Criar funcao `configure_ffmpeg_env()` em `app/config.py` que seta todas as env vars. Chamar uma unica vez no startup (em `run_app()` ou no import de config). Remover configuracao duplicada de `video_converter.py` e `youtube_downloader.py`.

**Pros:**
- Single source of truth
- Todas as env vars sempre configuradas consistentemente
- Mais facil de manter

**Cons:**
- Precisa garantir que `config.py` e importado antes dos services
- `launcher.py` ainda precisaria de copia propria (roda antes do app/)

**Effort:** 30 min

**Risk:** Low

---

### Option 2: Manter launcher.py + remover dos services

**Approach:** Confiar que `launcher.py` ja configura tudo no caso bundled. Para desenvolvimento, adicionar a configuracao no `run_app()` (que sempre executa). Remover dos services individuais.

**Pros:**
- Minimo de mudancas
- Dois pontos claros: launcher (bundled) e run_app (dev)

**Cons:**
- Ainda ha duplicacao entre launcher e run_app, mas intencional e documentada

**Effort:** 20 min

**Risk:** Low

## Recommended Action

## Technical Details

**Affected files:**
- `launcher.py:78-87` - setup_frozen_env()
- `app/services/video_converter.py:26-27` - IMAGEIO_FFMPEG_EXE
- `app/services/youtube_downloader.py:18-22` - PATH manipulation
- `app/config.py:103` - FFMPEG_PATH

**Related components:**
- MoviePy (usa IMAGEIO_FFMPEG_EXE)
- imageio-ffmpeg (usa IMAGEIO_FFMPEG_EXE)
- yt-dlp (usa PATH e ffmpeg_location)

## Resources

- **PR:** #156
- **Review agents:** pattern-recognition-specialist, architecture-strategist, security-sentinel

## Acceptance Criteria

- [ ] ffmpeg env vars configuradas em no maximo 2 lugares (launcher + app)
- [ ] Todas as 3 env vars (IMAGEIO_FFMPEG_EXE, FFMPEG_BINARY, PATH) cobertas em ambos
- [ ] video_converter.py e youtube_downloader.py nao configuram ffmpeg diretamente
- [ ] App funciona em desenvolvimento (sem launcher)
- [ ] App funciona empacotado (com launcher)

## Work Log

### 2026-02-06 - Identificado na review do PR #156

**By:** Claude Code

**Actions:**
- Identificada duplicacao em 3 arquivos com cobertura inconsistente
- Consenso entre pattern-recognition-specialist, architecture-strategist e security-sentinel
- Nao corrigido neste PR porque video_converter.py e youtube_downloader.py estao fora do escopo

**Learnings:**
- launcher.py nao pode importar app/config.py (roda antes do app/)
- A duplicacao no launcher e intencional e necessaria
- A duplicacao nos services e desnecessaria se o startup configurar tudo
