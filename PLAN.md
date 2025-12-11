# Pixoo Manager - Plano de Implementação

> **Para Claude Code:** Este documento contém o plano completo para implementar o Pixoo Manager. Leia-o inteiramente antes de começar. Execute as fases em ordem, marcando cada item como concluído.

## Contexto do Projeto

**Objetivo:** Criar uma aplicação Mac desktop para gerenciar conteúdo no display LED Divoom Pixoo 64.

**Stack técnica:**
- Backend: FastAPI + Uvicorn
- Frontend: Jinja2 + Alpine.js + Pico.css
- Processamento: Pillow, MoviePy, yt-dlp
- Empacotamento: PyInstaller

**Padrão de referência:** O projeto PDFTools em `/Users/dpalis/Coding/PDFTools/` serve como modelo para a arquitetura. Consulte-o para entender os padrões de código.

---

## Estrutura Final do Projeto

```
Pixoo 64/                            # RAIZ DO PROJETO
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI app + auto-open browser
│   ├── config.py                    # Constantes e configurações
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── connection.py            # /api/discover, /api/connect, /api/status
│   │   ├── gif_upload.py            # /api/gif/upload, /api/gif/send
│   │   ├── media_convert.py         # /api/media/upload, /api/media/convert
│   │   └── youtube.py               # /api/youtube/info, /api/youtube/download
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pixoo_connection.py      # Descoberta de rede + estado de conexão
│   │   ├── pixoo_upload.py          # Upload de GIF via HTTP API do Pixoo
│   │   ├── gif_converter.py         # Conversão de imagens/GIFs para 64x64
│   │   ├── video_processor.py       # Vídeo para GIF com MoviePy
│   │   ├── youtube_downloader.py    # Download de YouTube com yt-dlp
│   │   ├── file_utils.py            # Gerenciamento de arquivos temporários
│   │   └── exceptions.py            # Exceções customizadas
│   │
│   ├── static/
│   │   ├── css/
│   │   │   └── styles.css           # Estilos customizados
│   │   ├── js/
│   │   │   └── app.js               # Funções JavaScript compartilhadas
│   │   └── vendor/
│   │       ├── alpine.min.js        # Alpine.js (copiar do PDFTools)
│   │       └── pico.min.css         # Pico.css (copiar do PDFTools)
│   │
│   └── templates/
│       ├── base.html                # Layout base com tabs e indicador de conexão
│       ├── gif.html                 # Tab 1: Upload de GIF pronto
│       ├── media.html               # Tab 2: Foto/Vídeo para Pixoo
│       └── youtube.html             # Tab 3: YouTube para Pixoo
│
├── bin/
│   └── ffmpeg                       # Binário FFmpeg estático para Mac (baixar)
│
├── build/
│   └── pixoo_manager.spec           # Configuração do PyInstaller
│
├── Originais/                       # [EXISTENTE] GIFs de exemplo
├── Processados/                     # [EXISTENTE] Saída de conversões
├── Temp/                            # [EXISTENTE] Arquivos temporários
├── venv/                            # [EXISTENTE] Ambiente virtual Python
│
├── PIXOO64_SPECS.md                 # [EXISTENTE] Especificações do hardware
├── PLAN.md                          # Este arquivo
├── requirements.txt                 # Dependências Python (atualizar)
└── README.md                        # Documentação do usuário
```

---

## Arquivos Existentes - Ações Necessárias

| Arquivo | Ação | Detalhes |
|---------|------|----------|
| `convert_to_pixoo.py` | **EXTRAIR E DELETAR** | Extrair funções úteis para `app/services/gif_converter.py`, depois deletar |
| `upload_to_pixoo.py` | **DELETAR** | Lógica será reescrita em `app/services/pixoo_upload.py` |
| `PROJECT_STATE.md` | **DELETAR** | Obsoleto |
| `PIXOO64_SPECS.md` | **MANTER** | Referência técnica do hardware |
| `Originais/` | **MANTER** | Útil para testes |
| `Processados/` | **MANTER** | Útil para testes |
| `Temp/` | **MANTER** | Usar como pasta temporária do app |
| `venv/` | **MANTER** | Ambiente virtual já configurado |

---

## Funcionalidades Detalhadas

### Header Global: Conexão com Pixoo

**UI:**
- Indicador visual de status (bolinha verde/vermelha)
- Texto: "Desconectado" / "Conectado a 192.168.x.x"
- Botão "Conectar" (quando desconectado)
- Botão "Desconectar" (quando conectado)

**Fluxo de conexão:**
1. Usuário clica "Conectar"
2. Sistema tenta descoberta automática via mDNS/scan
3. Se encontrar, conecta automaticamente
4. Se não encontrar, mostra campo para IP manual
5. Testa conexão com comando `Channel/GetIndex`
6. Atualiza status na UI

**API Endpoints:**
- `POST /api/discover` → Busca dispositivos na rede, retorna lista de IPs
- `POST /api/connect` → Body: `{ip: "192.168.1.x"}`, testa e conecta
- `POST /api/disconnect` → Desconecta
- `GET /api/status` → Retorna `{connected: bool, ip: string|null}`

---

### Tab 1: Upload GIF

**UI:**
- Zona de drag-drop para arquivos GIF
- Preview do GIF (escalado 4x com nearest-neighbor para visualização)
- Informações: frames, dimensões, tamanho
- Botão "Enviar para Pixoo" (desabilitado se não conectado)

**Fluxo:**
1. Usuário arrasta/seleciona arquivo GIF
2. Sistema verifica se é 64x64
   - Se sim: mostra preview direto
   - Se não: converte automaticamente e mostra preview
3. Usuário clica "Enviar"
4. Sistema faz upload frame-by-frame para o Pixoo
5. Mostra mensagem de sucesso/erro

**API Endpoints:**
- `POST /api/gif/upload` → Recebe arquivo, converte se necessário, retorna preview + metadata
- `POST /api/gif/send` → Envia GIF atual para o Pixoo conectado

---

### Tab 2: Foto/Vídeo

**UI para Imagem:**
- Zona de drag-drop (aceita PNG, JPG, GIF)
- Preview da imagem original
- Preview do resultado 64x64
- Botão "Enviar para Pixoo"

**UI para Vídeo:**
- Zona de drag-drop (aceita MP4, MOV, WebM)
- Player HTML5 para preview do vídeo
- Timeline com dois handles (início/fim)
- Campos de input para tempo manual (formato: MM:SS.ms)
- Indicador de duração selecionada
- Limite máximo: 10 segundos (mostrar aviso se exceder)
- Barra de progresso durante conversão
- Preview do GIF resultante
- Botão "Enviar para Pixoo"

**Fluxo Imagem:**
1. Upload da imagem
2. Conversão automática para 64x64 (single frame GIF)
3. Preview e envio

**Fluxo Vídeo:**
1. Upload do vídeo
2. Sistema retorna duração para configurar timeline
3. Usuário ajusta início/fim (max 10s)
4. Clica "Converter"
5. Sistema processa com MoviePy (mostra progresso via SSE)
6. Mostra preview do GIF
7. Usuário envia para Pixoo

**API Endpoints:**
- `POST /api/media/upload` → Recebe arquivo, retorna tipo e metadados
- `GET /api/media/info/{id}` → Retorna info do vídeo (duração, fps, dimensões)
- `POST /api/media/convert` → Body: `{start, end}`, retorna SSE com progresso
- `POST /api/media/send` → Envia resultado para Pixoo

---

### Tab 3: YouTube

**UI:**
- Campo de texto para URL do YouTube
- Botão "Buscar"
- Área de info (após buscar): thumbnail, título, duração total
- Timeline idêntica ao Tab 2 (início/fim)
- Barra de progresso (download + conversão)
- Preview do GIF resultante
- Botão "Enviar para Pixoo"

**Fluxo:**
1. Usuário cola URL e clica "Buscar"
2. Sistema usa yt-dlp para obter metadados (sem baixar)
3. Mostra info e habilita timeline
4. Usuário seleciona trecho (max 10s)
5. Clica "Baixar e Converter"
6. Sistema baixa apenas o trecho selecionado (`--download-sections`)
7. Converte para GIF 64x64
8. Mostra preview
9. Usuário envia para Pixoo

**API Endpoints:**
- `POST /api/youtube/info` → Body: `{url}`, retorna metadados
- `POST /api/youtube/download` → Body: `{url, start, end}`, retorna SSE com progresso
- `POST /api/youtube/send` → Envia resultado para Pixoo

---

## Código Existente a Reaproveitar

### De `convert_to_pixoo.py` (extrair para `gif_converter.py`):

```python
# Funções a MANTER e adaptar:
- load_gif_frames(gif_path)           # Carrega frames de GIF
- adaptive_downscale(image, size)     # Redimensiona preservando qualidade
- smart_crop(image, target_size)      # Crop inteligente mantendo aspecto
- majority_color_block_sampling()     # Amostragem por cor majoritária
- detect_edges()                      # Detecção de bordas (Sobel)
- remove_dark_halos()                 # Remove artefatos de anti-aliasing
- enhance_for_led_display()           # Otimiza para LED (contraste, saturação)
- darken_background()                 # Escurece fundo
- focus_on_center()                   # Efeito vinheta
- quantize_colors()                   # Reduz paleta de cores

# Função principal a REFATORAR:
- convert_gif() → convert_to_pixoo_format(input_path, options) -> (output_path, metadata)
```

### De `upload_to_pixoo.py` (reescrever em `pixoo_upload.py`):

```python
# Lógica a REIMPLEMENTAR:
- Conexão HTTP com Pixoo em http://{ip}:80/post
- Comando Channel/GetIndex para teste de conexão
- Comando Draw/ResetHttpGifId para limpar buffer
- Comando Draw/SendHttpGif para enviar frames
- Conversão de frame para base64 (64*64*3 bytes RGB)
- Limite de 40 frames por upload (segurança)
```

### Do PDFTools (copiar padrões):

```
/Users/dpalis/Coding/PDFTools/
├── app/main.py                  # Padrão FastAPI + lifespan + browser open
├── app/config.py                # Padrão de configuração
├── app/templates/base.html      # Padrão de layout com tabs
├── app/templates/extract.html   # Padrão Alpine.js component
├── app/static/css/styles.css    # Padrão de estilos
├── app/static/vendor/           # Bibliotecas JS/CSS para copiar
└── app/services/file_utils.py   # Padrão de manipulação de arquivos
```

---

## Fases de Implementação

### Fase 1: Setup e Reorganização

**Objetivo:** Criar estrutura de pastas e preparar ambiente.

- [ ] 1.1 Criar estrutura de diretórios:
  ```
  mkdir -p app/routers app/services app/static/css app/static/js app/static/vendor app/templates bin build
  ```

- [ ] 1.2 Copiar vendor files do PDFTools:
  ```
  cp /Users/dpalis/Coding/PDFTools/app/static/vendor/* app/static/vendor/
  ```

- [ ] 1.3 Criar `app/__init__.py` (arquivo vazio)

- [ ] 1.4 Criar `app/config.py`:
  ```python
  from pathlib import Path

  HOST = "127.0.0.1"
  PORT = 8000

  PIXOO_SIZE = 64
  MAX_UPLOAD_FRAMES = 40      # Limite seguro para Pixoo
  MAX_CONVERT_FRAMES = 92     # Limite de conversão
  MAX_VIDEO_DURATION = 10.0   # Segundos
  MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

  BASE_DIR = Path(__file__).parent.parent
  STATIC_DIR = Path(__file__).parent / "static"
  TEMPLATES_DIR = Path(__file__).parent / "templates"
  TEMP_DIR = BASE_DIR / "Temp"
  ```

- [ ] 1.5 Atualizar `requirements.txt`:
  ```
  # Web
  fastapi>=0.109.0
  uvicorn>=0.27.0
  python-multipart>=0.0.6
  jinja2>=3.1.0
  aiofiles>=23.2.0
  sse-starlette>=1.8.0

  # Imagem
  Pillow>=10.0.0
  imageio>=2.31.0
  numpy>=1.24.0

  # Vídeo
  moviepy>=1.0.3

  # YouTube
  yt-dlp>=2024.1.0

  # Rede
  zeroconf>=0.131.0
  requests>=2.31.0

  # Build
  pyinstaller>=6.0.0
  ```

- [ ] 1.6 Instalar dependências: `pip install -r requirements.txt`

- [ ] 1.7 Extrair funções de `convert_to_pixoo.py` para `app/services/gif_converter.py`

- [ ] 1.8 Deletar arquivos obsoletos:
  ```
  rm convert_to_pixoo.py upload_to_pixoo.py PROJECT_STATE.md
  ```

- [ ] 1.9 Criar `app/services/exceptions.py`:
  ```python
  class PixooError(Exception):
      """Base exception for Pixoo errors."""
      pass

  class ConnectionError(PixooError):
      """Failed to connect to Pixoo."""
      pass

  class ConversionError(PixooError):
      """Failed to convert media."""
      pass

  class UploadError(PixooError):
      """Failed to upload to Pixoo."""
      pass
  ```

- [ ] 1.10 Criar `app/services/file_utils.py` (adaptar do PDFTools)

- [ ] 1.11 Criar `app/main.py` (adaptar do PDFTools)

- [ ] 1.12 Criar `app/templates/base.html` com estrutura de 3 tabs

- [ ] 1.13 Criar `app/static/css/styles.css` (adaptar do PDFTools + novos estilos)

- [ ] 1.14 Testar servidor básico: `python -m app.main`

---

### Fase 2: Serviço de Conexão

**Objetivo:** Implementar descoberta e conexão com Pixoo.

- [ ] 2.1 Criar `app/services/pixoo_connection.py`:
  - Classe singleton `PixooConnection`
  - Método `discover()` usando zeroconf
  - Método `scan_network()` como fallback (scan IP range)
  - Método `connect(ip)` com teste de conexão
  - Método `disconnect()`
  - Método `send_command(command_dict)`
  - Property `is_connected`
  - Property `current_ip`

- [ ] 2.2 Criar `app/routers/__init__.py`

- [ ] 2.3 Criar `app/routers/connection.py`:
  - `POST /api/discover`
  - `POST /api/connect`
  - `POST /api/disconnect`
  - `GET /api/status`

- [ ] 2.4 Registrar router em `main.py`

- [ ] 2.5 Atualizar `base.html` com UI de conexão (Alpine.js component no header)

- [ ] 2.6 Testar conexão (mock ou dispositivo real se disponível)

---

### Fase 3: Tab Upload GIF

**Objetivo:** Implementar upload e envio de GIFs prontos.

- [ ] 3.1 Finalizar `app/services/gif_converter.py`:
  - `is_pixoo_ready(path)` → verifica se já é 64x64
  - `convert_to_pixoo_format(path, options)` → converte para 64x64
  - `create_preview(path, scale)` → gera preview escalado

- [ ] 3.2 Criar `app/services/pixoo_upload.py`:
  - `frame_to_base64(frame)` → converte frame PIL para base64
  - `upload_gif(path, speed, progress_callback)` → envia para Pixoo

- [ ] 3.3 Criar `app/routers/gif_upload.py`:
  - `POST /api/gif/upload`
  - `POST /api/gif/send`
  - `GET /api/gif/preview/{id}`

- [ ] 3.4 Registrar router em `main.py`

- [ ] 3.5 Criar `app/templates/gif.html`:
  - Zona de drag-drop
  - Preview do GIF
  - Info (frames, tamanho)
  - Botão enviar

- [ ] 3.6 Adicionar rota GET `/gif` em `main.py`

- [ ] 3.7 Testar upload e conversão de GIFs

---

### Fase 4: Tab Foto/Vídeo

**Objetivo:** Implementar conversão de fotos e vídeos.

- [ ] 4.1 Criar `app/services/video_processor.py`:
  - `get_video_info(path)` → duração, fps, dimensões
  - `extract_frame(path, time)` → extrai frame em timestamp
  - `video_to_gif(path, start, end, options, progress_callback)`
  - `image_to_gif(path, options)` → imagem estática para GIF

- [ ] 4.2 Criar `app/routers/media_convert.py`:
  - `POST /api/media/upload`
  - `GET /api/media/info/{id}`
  - `POST /api/media/frame` → extrai frame para preview
  - `POST /api/media/convert` → com SSE para progresso
  - `POST /api/media/send`

- [ ] 4.3 Registrar router em `main.py`

- [ ] 4.4 Criar `app/templates/media.html`:
  - Zona de upload
  - Área de preview (imagem ou vídeo)
  - Timeline com dual slider (para vídeo)
  - Inputs de tempo manual
  - Progress bar
  - Preview do resultado
  - Botão enviar

- [ ] 4.5 Criar `app/static/js/app.js` com funções compartilhadas:
  - `formatTime(seconds)`
  - `formatFileSize(bytes)`
  - Componente timeline reutilizável

- [ ] 4.6 Adicionar rota GET `/media` em `main.py`

- [ ] 4.7 Testar com imagens e vídeos

---

### Fase 5: Tab YouTube

**Objetivo:** Implementar download e conversão de vídeos do YouTube.

- [ ] 5.1 Criar `app/services/youtube_downloader.py`:
  - `get_video_info(url)` → título, duração, thumbnail
  - `download_range(url, start, end, output_path, progress_callback)`
  - Tratamento de erros (URL inválida, vídeo privado, etc.)

- [ ] 5.2 Criar `app/routers/youtube.py`:
  - `POST /api/youtube/info`
  - `POST /api/youtube/download` → com SSE para progresso
  - `POST /api/youtube/send`

- [ ] 5.3 Registrar router em `main.py`

- [ ] 5.4 Criar `app/templates/youtube.html`:
  - Campo de URL
  - Botão buscar
  - Info display (thumbnail, título, duração)
  - Timeline (reutilizar padrão do media.html)
  - Progress bar
  - Preview do resultado
  - Botão enviar

- [ ] 5.5 Adicionar rota GET `/youtube` em `main.py`

- [ ] 5.6 Testar com URLs reais do YouTube

---

### Fase 6: Empacotamento

**Objetivo:** Criar .app distribuível para Mac.

- [ ] 6.1 Baixar FFmpeg estático para Mac:
  - Intel: https://evermeet.cx/ffmpeg/
  - Colocar em `bin/ffmpeg`

- [ ] 6.2 Criar `build/pixoo_manager.spec` para PyInstaller

- [ ] 6.3 Atualizar código para detectar FFmpeg bundled:
  ```python
  import sys
  if getattr(sys, 'frozen', False):
      FFMPEG_PATH = Path(sys._MEIPASS) / 'bin' / 'ffmpeg'
  else:
      FFMPEG_PATH = Path(__file__).parent.parent / 'bin' / 'ffmpeg'
  ```

- [ ] 6.4 Build do .app:
  ```
  pyinstaller build/pixoo_manager.spec
  ```

- [ ] 6.5 Testar .app em Mac limpo (sem Python)

- [ ] 6.6 Criar `README.md` com instruções de uso

---

## Decisões Técnicas

| Aspecto | Decisão | Justificativa |
|---------|---------|---------------|
| Estado de conexão | Singleton em memória | Simples, sem necessidade de persistência |
| Progress updates | SSE (Server-Sent Events) | Mais simples que WebSocket para one-way |
| Processamento vídeo | MoviePy | API Pythonica, gera GIF nativamente |
| Download YouTube | yt-dlp | Fork ativo do youtube-dl, melhor suporte |
| Empacotamento | PyInstaller --onedir | Inclui todas dependências, funciona em qualquer Mac |
| CSS Framework | Pico.css | Leve, semântico, mesmo do PDFTools |
| JS Framework | Alpine.js | Reativo sem build step, mesmo do PDFTools |

---

## Limites e Validações

| Limite | Valor | Onde validar |
|--------|-------|--------------|
| Tamanho máximo arquivo | 500MB | `file_utils.py` |
| Frames máximo upload | 40 | `pixoo_upload.py` |
| Frames máximo conversão | 92 | `gif_converter.py` |
| Duração máxima vídeo | 10s | `video_processor.py`, `youtube_downloader.py` |
| Dimensão Pixoo | 64x64 | `config.py` |

---

## Testes Manuais Sugeridos

1. **Conexão:**
   - [ ] Descoberta automática funciona
   - [ ] IP manual funciona
   - [ ] Desconexão funciona
   - [ ] Status atualiza corretamente

2. **Upload GIF:**
   - [ ] GIF 64x64 envia direto
   - [ ] GIF maior é convertido automaticamente
   - [ ] Preview mostra corretamente
   - [ ] Envio para Pixoo funciona

3. **Foto/Vídeo:**
   - [ ] Upload de PNG funciona
   - [ ] Upload de JPG funciona
   - [ ] Upload de MP4 funciona
   - [ ] Timeline permite selecionar trecho
   - [ ] Conversão mostra progresso
   - [ ] Preview do resultado funciona
   - [ ] Envio para Pixoo funciona

4. **YouTube:**
   - [ ] URL válida retorna info
   - [ ] URL inválida mostra erro
   - [ ] Download de trecho funciona
   - [ ] Progresso é mostrado
   - [ ] Conversão funciona
   - [ ] Envio para Pixoo funciona

5. **App empacotado:**
   - [ ] .app abre com duplo clique
   - [ ] Navegador abre automaticamente
   - [ ] Todas funcionalidades funcionam
   - [ ] Funciona em Mac sem Python instalado

---

## Referências

- **PDFTools (padrão de código):** `/Users/dpalis/Coding/PDFTools/`
- **Specs do Pixoo 64:** `/Users/dpalis/Coding/Pixoo 64/PIXOO64_SPECS.md`
- **API do Pixoo:** `http://{ip}:80/post` com comandos JSON
- **Documentação yt-dlp:** https://github.com/yt-dlp/yt-dlp
- **Documentação MoviePy:** https://zulko.github.io/moviepy/
- **Documentação Alpine.js:** https://alpinejs.dev/
- **Documentação Pico.css:** https://picocss.com/
