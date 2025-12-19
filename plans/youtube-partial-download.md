# YouTube Partial Download Optimization

**Issue:** #91
**Type:** Performance
**Date:** 2025-12-18

## Overview

Otimizar o download de trechos do YouTube para baixar apenas o segmento solicitado ao invés do vídeo completo.

**Situação Atual:** Download de 10s de um vídeo de 10min baixa o vídeo inteiro (~50MB) e depois corta com MoviePy.

**Meta:** Download de 10s de um vídeo de 10min deve levar < 15 segundos.

## Solução Proposta

Abordagem híbrida com 3 métodos em cascata:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Download Request                                 │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Método 1: FFmpeg External Downloader                                 │
│ - Mais rápido (baixa apenas o trecho)                               │
│ - Usa: external_downloader='ffmpeg' + ffmpeg_i args                 │
└─────────────────────────────────────────────────────────────────────┘
                              │
                    [Falhou?] │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Método 2: download_ranges API                                        │
│ - Usa: download_range_func(None, [(start, end)])                    │
│ - Workaround HLS: format_sort=['proto:https']                       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                    [Falhou?] │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Método 3: Full Download + MoviePy Trim (Atual)                       │
│ - Mais lento, mas confiável                                         │
│ - Fallback final                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

## Descobertas da Pesquisa

### Método 1: FFmpeg External Downloader

**Sintaxe correta encontrada:**
```python
ffmpeg_args = {"ffmpeg_i": ["-ss", str(start), "-to", str(end)]}

ydl_opts = {
    "external_downloader": "ffmpeg",
    "external_downloader_args": ffmpeg_args,
    "format": "best[ext=mp4][height<=720]/best[ext=mp4]/best",
}
```

**Importante:** O parâmetro `ffmpeg_i` aplica argumentos ANTES do `-i` do FFmpeg, permitindo trimming durante download.

### Método 2: download_ranges API

**Sintaxe correta encontrada:**
```python
from yt_dlp.utils import download_range_func

ydl_opts = {
    'download_ranges': download_range_func(None, [(start, end)]),
    'format_sort': ['proto:https'],  # Fix para bug de arquivo vazio com HLS
    'force_keyframes_at_cuts': True,
}
```

**Bugs conhecidos:**
- Arquivos vazios com formatos HLS (fix: `format_sort=['proto:https']`)
- API pode ser instável entre versões

### FFmpeg no Bundle

**Situação atual:**
- FFmpeg bundled em `bin/ffmpeg` (76MB, ARM64)
- `IMAGEIO_FFMPEG_EXE` configurado para MoviePy
- yt-dlp NÃO usa essa variável automaticamente

**Necessário:**
```python
ydl_opts = {
    'ffmpeg_location': str(FFMPEG_PATH),  # Explícito para yt-dlp
    'external_downloader': 'ffmpeg',
}
```

## Decisões de Implementação

### Exceções que Disparam Fallback

| Exceção | Ação |
|---------|------|
| `FileNotFoundError` (FFmpeg) | Fallback |
| `yt_dlp.DownloadError` | Fallback |
| `subprocess.SubprocessError` | Fallback |
| `OSError` (permissões) | Fallback |
| `httpx.NetworkError` / `requests.RequestException` | **Falha imediata** |
| `yt_dlp.utils.ExtractorError` (geo-block, age-restrict) | **Falha imediata** |

### Arquivos Temporários

```python
# Nomes únicos por método para evitar colisão
method1_output = TEMP_DIR / f"yt_{video_id}_{start}_{end}_m1.mp4"
method2_output = TEMP_DIR / f"yt_{video_id}_{start}_{end}_m2.mp4"
method3_full   = TEMP_DIR / f"yt_{video_id}_full.mp4"
method3_output = TEMP_DIR / f"yt_{video_id}_{start}_{end}.mp4"

# Cleanup: sempre em finally block de cada método
```

### Verificação de Sucesso

```python
def _verify_segment_download(path: Path, expected_duration: float) -> bool:
    """Verifica se download parcial funcionou."""
    if not path.exists() or path.stat().st_size == 0:
        return False

    # Verificar duração com MoviePy
    with VideoFileClip(str(path)) as clip:
        # Tolerância de 2 segundos para variação de keyframes
        return abs(clip.duration - expected_duration) < 2.0
```

### Progress Callback

```python
# Fases distintas para cada método
progress_callback("downloading_optimized", pct)   # Método 1/2
progress_callback("downloading_fallback", pct)    # Método 3
progress_callback("trimming", pct)                # MoviePy trim
```

## Implementação

### Arquivo: `app/services/youtube_downloader.py`

**Função modificada:** `_download_and_trim()`

```python
def _download_and_trim(
    video_id: str,
    start: float,
    end: float,
    progress_callback: Optional[callable] = None
) -> Path:
    """
    Baixa trecho de vídeo usando abordagem híbrida.

    Tenta em ordem:
    1. FFmpeg external downloader (mais rápido)
    2. download_ranges API (fallback)
    3. Download completo + MoviePy trim (fallback final)
    """
    segment_duration = end - start
    output_path = TEMP_DIR / f"yt_{video_id}_{start:.0f}_{end:.0f}.mp4"

    # Método 1: FFmpeg External Downloader
    try:
        result = _try_ffmpeg_download(video_id, start, end, progress_callback)
        if _verify_segment_download(result, segment_duration):
            return result
    except (FileNotFoundError, DownloadError, OSError) as e:
        logger.warning(f"Método 1 (FFmpeg) falhou: {e}")

    # Método 2: download_ranges API
    try:
        result = _try_download_ranges(video_id, start, end, progress_callback)
        if _verify_segment_download(result, segment_duration):
            return result
    except (DownloadError, ImportError) as e:
        logger.warning(f"Método 2 (download_ranges) falhou: {e}")

    # Método 3: Full download + MoviePy trim (fallback)
    return _download_full_and_trim(video_id, start, end, progress_callback)


def _try_ffmpeg_download(video_id: str, start: float, end: float, progress_callback) -> Path:
    """Método 1: Download parcial com FFmpeg external downloader."""
    output_path = TEMP_DIR / f"yt_{video_id}_{start:.0f}_{end:.0f}_m1.mp4"

    if not FFMPEG_PATH.exists():
        raise FileNotFoundError(f"FFmpeg não encontrado: {FFMPEG_PATH}")

    def progress_hook(d):
        if progress_callback and d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                progress_callback("downloading_optimized", (downloaded / total) * 100)

    ffmpeg_args = {"ffmpeg_i": ["-ss", str(start), "-to", str(end)]}

    ydl_opts = {
        "external_downloader": "ffmpeg",
        "external_downloader_args": ffmpeg_args,
        "ffmpeg_location": str(FFMPEG_PATH),
        "format": "best[ext=mp4][height<=720]/best[ext=mp4]/best",
        "outtmpl": str(output_path),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "progress_hooks": [progress_hook],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

    return output_path


def _try_download_ranges(video_id: str, start: float, end: float, progress_callback) -> Path:
    """Método 2: Download parcial com download_ranges API."""
    from yt_dlp.utils import download_range_func

    output_path = TEMP_DIR / f"yt_{video_id}_{start:.0f}_{end:.0f}_m2.mp4"

    def progress_hook(d):
        if progress_callback and d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                progress_callback("downloading_optimized", (downloaded / total) * 100)

    ydl_opts = {
        'format': 'best[ext=mp4][height<=720]/best[ext=mp4]/best',
        'format_sort': ['proto:https'],  # Workaround para HLS
        'download_ranges': download_range_func(None, [(start, end)]),
        'force_keyframes_at_cuts': True,
        'ffmpeg_location': str(FFMPEG_PATH),
        'outtmpl': str(output_path),
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'progress_hooks': [progress_hook],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

    return output_path


def _download_full_and_trim(video_id: str, start: float, end: float, progress_callback) -> Path:
    """Método 3: Download completo + trim com MoviePy (fallback)."""
    # Código atual existente em _download_and_trim()
    # Mantido como fallback final
    ...
```

### Arquivo: `app/config.py`

**Verificar:** `FFMPEG_PATH` já existe e funciona corretamente.

### Arquivo: `app/services/video_converter.py`

**Nenhuma mudança necessária** - já configura `IMAGEIO_FFMPEG_EXE`.

## Critérios de Aceite

- [ ] Download de trecho 10s de vídeo 10min em < 15 segundos (Método 1 ou 2)
- [ ] Fallback funciona quando Método 1/2 falham
- [ ] Funciona em desenvolvimento (`python main.py`)
- [ ] Funciona no bundle (`Pixoo.app`)
- [ ] Arquivos temporários são limpos após uso
- [ ] Progress callback atualiza UI corretamente
- [ ] Erros de rede/geo-block falham imediatamente (sem tentar fallbacks)
- [ ] Verificação de duração do segmento funciona

## Riscos

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| FFmpeg não funciona no bundle | Média | Alto | Testar bundle antes de release |
| download_ranges instável | Alta | Baixo | Fallback para Método 3 |
| Performance pior que atual | Baixa | Médio | Manter Método 3 como fallback |
| Formato de vídeo incompatível | Média | Baixo | format_sort + fallback |

## Testes Necessários

### Unitários
- [ ] `_try_ffmpeg_download()` com FFmpeg presente
- [ ] `_try_ffmpeg_download()` sem FFmpeg (deve raise FileNotFoundError)
- [ ] `_try_download_ranges()` com diferentes formatos
- [ ] `_verify_segment_download()` com arquivo válido/inválido
- [ ] Fallback chain completo

### Integração
- [ ] Download de vídeo regular (10s)
- [ ] Download de YouTube Shorts (30s)
- [ ] Download com conexão lenta (verificar timeout)
- [ ] Download no bundle .app

### Edge Cases
- [ ] Segmento no início do vídeo (0-10s)
- [ ] Segmento no fim do vídeo
- [ ] Segmento muito curto (<1s)
- [ ] Vídeo muito longo (>30min)

## Referências

- [yt-dlp download_ranges docs](https://github.com/yt-dlp/yt-dlp/issues/9328)
- [FFmpeg external_downloader gist](https://gist.github.com/space-pope/977b0d15cf01932332014194fc80c1f0)
- [Issue #91](https://github.com/dpalis/pixoo-manager/issues/91)
- Arquivo atual: `app/services/youtube_downloader.py:174-249`
