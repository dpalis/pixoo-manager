---
title: "feat: Rotação Automática de Imagens da Galeria"
type: feat
date: 2026-02-04
---

# Rotação Automática de Imagens da Galeria

## Overview

Implementar rotação automática de GIFs da galeria no Pixoo 64, permitindo que o usuário selecione imagens e configure um intervalo para troca automática. A rotação funciona no backend (continua mesmo com browser fechado) e persiste a última configuração para fácil retomada.

## Motivação

Usuários querem usar o Pixoo 64 como display decorativo que muda automaticamente entre várias imagens favoritas, sem intervenção manual.

## Solução Proposta

### Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │ galleryView()   │  │ rotationBanner  │                   │
│  │ + botão rotação │  │ + status header │                   │
│  └────────┬────────┘  └────────┬────────┘                   │
│           │ API calls          │ polling/status              │
└───────────┼────────────────────┼────────────────────────────┘
            │                    │
┌───────────┼────────────────────┼────────────────────────────┐
│           ▼                    ▼           BACKEND           │
│  ┌─────────────────────────────────────┐                    │
│  │         routers/rotation.py          │                    │
│  │  POST /start, /stop, /resume         │                    │
│  │  GET /status                         │                    │
│  └────────────────┬────────────────────┘                    │
│                   │                                          │
│  ┌────────────────▼────────────────────┐                    │
│  │    services/rotation_manager.py      │                    │
│  │    Singleton + asyncio loop          │                    │
│  │    + persistência JSON               │                    │
│  └────────────────┬────────────────────┘                    │
│                   │                                          │
│  ┌────────────────▼────────────────────┐                    │
│  │    services/pixoo_upload.py          │                    │
│  │    (existente - envia GIF)           │                    │
│  └─────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

## Implementação por Fases

### Fase 1: Backend - RotationManager

**Arquivo:** `app/services/rotation_manager.py`

```python
# Estrutura do RotationManager (Singleton)
class RotationManager:
    _instance = None
    _instance_lock = threading.Lock()

    # Estado
    _is_active: bool = False
    _selected_ids: List[str] = []
    _interval_minutes: int = 2
    _current_index: int = 0
    _shuffled_order: List[str] = []
    _rotation_task: Optional[asyncio.Task] = None
    _state_lock: threading.RLock

    # Métodos públicos
    def start(self, ids: List[str], interval: int) -> bool
    def stop(self) -> bool
    def resume(self) -> bool
    def get_status(self) -> RotationStatus

    # Métodos internos
    async def _rotation_loop(self)
    def _shuffle_order(self)
    def _save_config(self)
    def _load_config(self) -> Optional[RotationConfig]
    def _validate_ids(self, ids: List[str]) -> List[str]
```

**Schema do JSON** (`~/.pixoo_manager/rotation_config.json`):
```json
{
  "version": 1,
  "selected_ids": ["abc123", "def456", "ghi789"],
  "interval_minutes": 2,
  "updated_at": "2026-02-04T10:30:00Z"
}
```

**Acceptance Criteria - Fase 1:**
- [x] Singleton thread-safe com double-check locking (ref: `pixoo_connection.py:89-122`)
- [x] Loop asyncio que troca imagem a cada intervalo
- [x] Ordem aleatória (shuffle no início, re-shuffle ao completar ciclo)
- [x] Persistência com escrita atômica (ref: `gallery_manager.py:115-139`)
- [x] Validação de IDs (remove inexistentes da lista)
- [x] Tratamento de erro: pula imagem após 3 falhas de envio
- [x] Pausa automática se Pixoo desconectar

---

### Fase 2: Backend - API Endpoints

**Arquivo:** `app/routers/rotation.py`

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/rotation/start` | POST | Inicia rotação com IDs e intervalo |
| `/api/rotation/stop` | POST | Para rotação ativa |
| `/api/rotation/resume` | POST | Retoma última configuração salva |
| `/api/rotation/status` | GET | Retorna estado atual |

**Request/Response Models:**

```python
# POST /api/rotation/start
class StartRotationRequest(BaseModel):
    selected_ids: List[str] = Field(..., min_length=1)
    interval_minutes: Literal[1, 2, 5]

class RotationStatusResponse(BaseModel):
    is_active: bool
    is_paused: bool  # True se pausado por desconexão
    selected_count: int
    interval_minutes: int
    has_saved_config: bool  # Para mostrar botão "Retomar"
```

**Acceptance Criteria - Fase 2:**
- [x] Endpoint `/start` valida IDs existem na galeria
- [x] Endpoint `/start` com 1 ID envia direto (sem rotação) - *tratado no frontend*
- [x] Endpoint `/stop` salva config antes de parar
- [x] Endpoint `/resume` valida config existe e IDs válidos
- [x] Endpoint `/status` retorna `has_saved_config` para botão Retomar
- [x] Endpoints adicionais: `/add/{id}`, `/remove/{id}`, `/intervals`, `DELETE /config`

---

### Fase 3: Frontend - UI na Galeria

**Arquivo:** `app/static/js/app.js` - modificar `galleryView()`

**Novos estados:**
```javascript
// Adicionar ao galleryView()
rotationActive: false,
rotationPaused: false,
rotationCount: 0,
rotationInterval: 0,
hasSavedConfig: false,
rotationModalOpen: false,
selectedInterval: 2,
```

**Novos métodos:**
```javascript
async checkRotationStatus()  // Chamado no init()
async startRotation()        // Abre modal de config
async confirmStartRotation() // Inicia após escolher intervalo
async stopRotation()
async resumeRotation()
```

**Modificações no HTML** (`app/templates/base.html`):

1. **Header indicator** (após connection-status):
```html
<div class="rotation-indicator" x-show="rotationActive">
    <svg><!-- ícone animado --></svg>
    Rotação ativa
</div>
```

2. **Banner na galeria** (após gallery-controls):
```html
<!-- Rotação ativa -->
<div class="rotation-banner active" x-show="rotationActive">
    <span>Rotação ativa · X imagens · a cada Y min</span>
    <button @click="stopRotation()">Parar</button>
</div>

<!-- Retomar última -->
<div class="rotation-banner resume" x-show="!rotationActive && hasSavedConfig">
    <span>Última rotação: X imagens · Y min</span>
    <button @click="resumeRotation()">Retomar</button>
</div>
```

3. **Botão na selection bar** (ao lado de Deletar):
```html
<button class="btn-rotation" @click="startRotation()" :disabled="selectedCount === 0">
    Iniciar Rotação
</button>
```

4. **Modal de configuração**:
```html
<div class="rotation-modal" x-show="rotationModalOpen">
    <!-- Escolha de intervalo: 1, 2, 5 min -->
    <!-- Preview das imagens selecionadas -->
    <!-- Botões: Cancelar, Iniciar -->
</div>
```

**Acceptance Criteria - Fase 3:**
- [x] Indicador no header quando rotação ativa (animado)
- [x] Banner na galeria com info e botão Parar
- [x] Banner "Retomar" quando há config salva (com botão X para descartar)
- [x] Modal de configuração de intervalo
- [x] Botão "Iniciar Rotação" na selection bar
- [x] Badges nos itens que estão na rotação
- [x] Status sincronizado via `/api/rotation/status` no init
- [x] Estado global `rotationState` para sincronizar entre tabs

---

### Fase 4: Confirmação ao Enviar Durante Rotação

**Afeta:** Todas as tabs que enviam para Pixoo (Mídia, YouTube, Galeria)

**Lógica:**
```javascript
async sendToPixoo() {
    // Verificar se rotação está ativa
    const status = await fetch('/api/rotation/status').then(r => r.json());
    if (status.is_active) {
        this.showStopRotationConfirm = true;
        return;
    }
    // Envio normal...
}

async confirmSendAndStopRotation() {
    await fetch('/api/rotation/stop', {method: 'POST'});
    // Envio normal...
}
```

**Acceptance Criteria - Fase 4:**
- [x] Modal de confirmação aparece se tentar enviar durante rotação
- [x] "Cancelar" fecha modal, não envia
- [x] "Parar e Enviar" para rotação e envia o GIF
- [x] Funciona em: mediaUpload, youtubeDownload, galleryView

---

### Fase 5: Caso Especial - 1 Imagem

**Lógica no frontend:**
```javascript
async startRotation() {
    if (this.selectedCount === 1) {
        // Modal simplificado: "Enviar imagem única?"
        this.singleImageModalOpen = true;
        return;
    }
    // Modal normal de rotação
}
```

**Acceptance Criteria - Fase 5:**
- [x] 1 imagem selecionada mostra modal diferente
- [x] Texto: "A imagem será enviada uma vez"
- [x] Botão: "Enviar" (não "Iniciar")
- [x] Não salva config, não mostra indicadores de rotação

---

## Arquivos a Criar/Modificar

| Arquivo | Ação | Descrição |
|---------|------|-----------|
| `app/services/rotation_manager.py` | **Criar** | Singleton + loop + persistência |
| `app/routers/rotation.py` | **Criar** | Endpoints da API |
| `app/main.py` | Modificar | Registrar router, inicializar manager no lifespan |
| `app/config.py` | Modificar | Adicionar `ROTATION_CONFIG_FILE` |
| `app/static/js/app.js` | Modificar | Lógica de rotação no galleryView |
| `app/static/css/styles.css` | Modificar | Estilos dos novos componentes |
| `app/templates/base.html` | Modificar | Header indicator, banner, modais |

---

## Tratamento de Erros

| Cenário | Comportamento |
|---------|---------------|
| Falha no envio (3x) | Pula para próxima imagem, continua rotação |
| Pixoo desconecta | Pausa rotação, mostra status "pausada" |
| Pixoo reconecta | Retoma automaticamente |
| Item deletado durante rotação | Remove da lista, continua com restantes |
| Config corrompida | Ignora, permite criar nova |
| IDs inválidos na config | Remove inválidos, usa válidos restantes |

---

## Testes Manuais

- [ ] Iniciar rotação com 3 imagens, verificar troca a cada intervalo
- [ ] Parar rotação, verificar que para imediatamente
- [ ] Fechar browser, verificar rotação continua no Pixoo
- [ ] Reabrir browser, verificar indicadores sincronizados
- [ ] Fechar app, reabrir, verificar botão "Retomar" aparece
- [ ] Retomar rotação, verificar que funciona
- [ ] Enviar GIF durante rotação, verificar confirmação
- [ ] Selecionar 1 imagem, verificar modal simplificado
- [ ] Desconectar Pixoo durante rotação, verificar pausa
- [ ] Reconectar Pixoo, verificar retomada

---

## Referências do Codebase

| Padrão | Arquivo de Referência |
|--------|----------------------|
| Singleton thread-safe | `app/services/pixoo_connection.py:89-122` |
| Async background loop | `app/routers/heartbeat.py:71-88, 172-191` |
| Persistência JSON atômica | `app/services/gallery_manager.py:115-139` |
| Modal Alpine.js | `app/static/js/app.js:2639-2694` |
| Router pattern | `app/routers/gallery.py:1-33` |

---

## Mockups

Mockups aprovados em `mockups/`:
- `01-galeria-selecao.html` - Galeria com seleção + botão rotação
- `02-modal-configuracao.html` - Modal de configuração
- `03-galeria-rotacao-ativa.html` - Rotação ativa (banner, badges, header)
- `04-galeria-retomar.html` - Retomar última rotação
- `05-uma-imagem.html` - Caso especial 1 imagem
- `06-confirmacao-parar.html` - Confirmação ao enviar durante rotação
