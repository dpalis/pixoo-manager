# Pixoo Manager

## Contexto do Projeto

### Visão Geral

Aplicação Mac desktop para gerenciar conteúdo no display LED Divoom Pixoo 64. Permite upload de GIFs, conversão de fotos/vídeos, e download de trechos do YouTube - tudo convertido para 64x64 pixels e enviado para o dispositivo via WiFi.

### Requisitos Funcionais

- Descoberta automática do Pixoo 64 na rede local
- Upload de GIFs prontos (converte automaticamente se não for 64x64)
- Conversão de fotos (PNG, JPG) para GIF 64x64
- Conversão de vídeos (MP4, MOV, WebM) para GIF 64x64 com seleção de trecho
- Download de trechos do YouTube e conversão para GIF 64x64
- Preview de todos os conteúdos antes de enviar
- Envio para Pixoo 64 via HTTP API local

### Requisitos Não-Funcionais

- 100% offline após conexão com Pixoo (exceto YouTube)
- Limite de 40 frames por upload e conversão
- Limite de 5 segundos para vídeos (40 frames a 8 FPS)
- Interface simples com 3 tabs

---

## Princípios Universais

> Copie esta seção para TODO novo projeto

### 1. Simplicidade Apropriada
- Começar com solução mais simples que funciona
- Adicionar complexidade APENAS quando justificado
- Red flags: > 5 dias, "preparado para o futuro", < 200 linhas em múltiplos arquivos

**Aplicação no Pixoo Manager:** Estrutura similar ao PDFTools - routers, services, templates. Cada tab é independente.

### 2. Validação Explícita > Debugging Implícito
- Falhe rápido com mensagens claras
- Type hints + runtime validation
- ROI: 100x+ (previne debugging)

**Aplicação no Pixoo Manager:** Validar dimensões de GIF, duração de vídeo, conexão com Pixoo antes de processar.

### 3. UI Reduz Fricção Exponencialmente
- 1 clique > múltiplos passos
- Estado visível sem "verificar"
- ROI: 10x adoção

**Aplicação no Pixoo Manager:** Drag-drop para upload, preview automático, indicador de conexão sempre visível.

### 4. Documentação é Ativo que Aprecia
- README + decisões técnicas + CHANGELOG
- ROI aumenta com tempo

**Aplicação no Pixoo Manager:** PLAN.md detalhado, CLAUDE.md com decisões, README para usuário final.

### 5. Feedback Real > Especulação
- 1 usuário real > 100h planejamento
- Features emergem de dores reais

**Aplicação no Pixoo Manager:** Começar com as 3 tabs essenciais. Adicionar features conforme uso real.

### 6. Git Workflow = Liberdade Experimental
- Feature branches sempre
- Main sempre deployable

**Aplicação no Pixoo Manager:** Uma branch por fase: `feature/phase1-setup`, `feature/phase2-connection`, etc.

---

## Patterns Reutilizáveis

> Consulte quando enfrentar problemas similares

### Two-Phase Operations
**Uso:** Race conditions em read-modify-write
```python
# FASE 1: Read ALL first
# FASE 2: Write ALL after
```

**Aplicação no Pixoo Manager:** Upload de GIF - carregar todos os frames primeiro, depois enviar sequencialmente.

### Armazenamento Redundante
**Uso:** Dados críticos de usuário

**Aplicação no Pixoo Manager:** Não aplicável (sem persistência de dados).

### Performance - Otimize Caso Comum
```python
if current_state != desired_state:
    expensive_operation()
```

**Aplicação no Pixoo Manager:** Verificar se GIF já é 64x64 antes de converter. Verificar conexão antes de tentar upload.

### Modularização Emergente
- Threshold: 200 linhas ou responsabilidade clara
- Complexidade emerge de problemas REAIS

**Aplicação no Pixoo Manager:** Services separados por responsabilidade: gif_converter, video_processor, pixoo_connection.

### Estimativas com Usuário Real
- Multiplicar por 3x
- Feedback revela requisitos não previstos

---

## Decisões Técnicas

### Singleton para conexão Pixoo

**Abordagem escolhida:** Classe singleton `PixooConnection` em memória
**Alternativas descartadas:** Conexão por request, banco de dados
**Por quê:** Simples, não precisa persistir, estado compartilhado entre tabs

### SSE para progresso de conversão

**Abordagem escolhida:** Server-Sent Events (SSE)
**Alternativas descartadas:** WebSocket, polling
**Por quê:** SSE é mais simples para comunicação one-way (servidor → cliente). WebSocket seria overkill.

### MoviePy para processamento de vídeo

**Abordagem escolhida:** MoviePy
**Alternativas descartadas:** FFmpeg direto, OpenCV
**Por quê:** API Pythonica, gera GIF nativamente, menos código boilerplate

### yt-dlp para YouTube

**Abordagem escolhida:** yt-dlp
**Alternativas descartadas:** youtube-dl, pytube
**Por quê:** Fork mais ativo, melhor suporte a novos formatos, mais mantido

---

## Stack Técnica

### Backend
- **Python 3.10+**
- **FastAPI** - servidor web
- **Uvicorn** - servidor ASGI
- **Pillow** - processamento de imagem
- **MoviePy** - processamento de vídeo
- **yt-dlp** - download do YouTube
- **zeroconf** - descoberta de dispositivos na rede

### Frontend
- **Alpine.js** (~17KB) - interatividade/reatividade
- **Pico.css** (~10KB) - estilização
- **Jinja2** - templates HTML

### Dependências
```
fastapi>=0.109.0
uvicorn>=0.27.0
python-multipart>=0.0.6
jinja2>=3.1.0
aiofiles>=23.2.0
sse-starlette>=1.8.0
Pillow>=10.0.0
imageio>=2.31.0
numpy>=1.24.0
moviepy>=1.0.3
yt-dlp>=2024.1.0
zeroconf>=0.131.0
requests>=2.31.0
```

---

## Arquitetura

### Padrão: Layered (camadas)

```
[Frontend/UI] -> [API/Routers] -> [Services/Lógica] -> [Pixoo HTTP API / Filesystem]
```

### Comunicação
- **Interna:** Síncrona via HTTP (POST com FormData, resposta JSON)
- **Progresso:** SSE para operações longas (conversão de vídeo, download YouTube)
- **Pixoo:** HTTP POST para `http://{ip}:80/post` com comandos JSON

### Estado
- **Conexão Pixoo:** Singleton em memória
- **Arquivos temporários:** Criados durante processamento, limpos após uso

### Estrutura de Pastas
```
app/
├── main.py              # FastAPI app + lifespan + browser open
├── config.py            # Constantes (PIXOO_SIZE, MAX_FRAMES, etc.)
├── routers/             # Endpoints da API
│   ├── connection.py    # /api/discover, /api/connect, /api/status
│   ├── gif_upload.py    # /api/gif/upload, /api/gif/send
│   ├── media_convert.py # /api/media/upload, /api/media/convert
│   └── youtube.py       # /api/youtube/info, /api/youtube/download
├── services/            # Lógica de negócio
│   ├── pixoo_connection.py
│   ├── pixoo_upload.py
│   ├── gif_converter.py
│   ├── video_processor.py
│   ├── youtube_downloader.py
│   ├── file_utils.py
│   └── exceptions.py
├── static/              # CSS, JS, vendor libs
└── templates/           # HTML (base.html, gif.html, media.html, youtube.html)
```

---

## Limites do Hardware

| Limite | Valor | Validação |
|--------|-------|-----------|
| Dimensão do display | 64x64 pixels | Conversão automática |
| Frames máximo (upload) | 40 | pixoo_upload.py |
| Frames máximo (conversão) | 92 | gif_converter.py |
| Formato de dados | RGB (64*64*3 bytes) | frame_to_base64() |

---

## Git Workflow

- Feature branches sempre
- Prefixos: `feature/`, `fix/`, `docs/`, `refactor/`
- Main sempre funcional
- Merge após testar

### Branches planejadas

1. `feature/phase1-setup` - Estrutura inicial + services base
2. `feature/phase2-connection` - Conexão com Pixoo
3. `feature/phase3-gif-upload` - Tab de upload GIF
4. `feature/phase4-media` - Tab de foto/vídeo
5. `feature/phase5-youtube` - Tab do YouTube
6. `feature/phase6-packaging` - Empacotamento .app
7. `feature/phase7-tests` - Testes automatizados

---

## Riscos e Mitigações

| Risco | Mitigação |
|-------|-----------|
| Pixoo não encontrado na rede | Fallback para IP manual |
| GIF muito grande (muitos frames) | Limitar a 40 frames no upload |
| Vídeo muito longo | Limitar a 5 segundos |
| YouTube bloqueia download | yt-dlp atualizado, mensagem de erro clara |
| Conversão lenta | Progress bar via SSE |

---

## Checklist de Qualidade

Antes de considerar uma funcionalidade pronta:

- [ ] Validação de entrada funciona (tipos, tamanhos, formatos)
- [ ] Mensagens de erro são claras e úteis
- [ ] Arquivos temporários são limpos
- [ ] Preview mostra corretamente
- [ ] Botão "Enviar" só habilitado quando conectado
- [ ] UI dá feedback visual (loading, sucesso, erro)
