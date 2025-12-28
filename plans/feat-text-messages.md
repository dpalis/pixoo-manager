# feat: Nova aba "Texto" - Mensagens scrolling no Pixoo 64

## Resumo

Implementar nova aba "Texto" no Pixoo Manager para enviar mensagens de texto scrolling para o display LED do Pixoo 64.

## Escopo (Opção B - Completa)

- [x] Campo de texto para mensagem
- [x] Seletor de cor (input color nativo)
- [x] Velocidade do scroll (slider)
- [x] Seletor de fonte (dropdown com fontes seguras)
- [x] Posição Y ajustável (slider)
- [x] Preview canvas animado simulando scroll
- [x] Botões: Limpar Textos e Enviar

---

## API do Pixoo

### SendHttpText
```json
{
  "Command": "Draw/SendHttpText",
  "TextId": 1,
  "x": 0,
  "y": 28,
  "dir": 0,
  "font": 0,
  "TextWidth": 64,
  "TextString": "Hello World!",
  "speed": 100,
  "color": "#FFFFFF",
  "align": 1
}
```

| Param | Tipo | Valor | Notas |
|-------|------|-------|-------|
| TextId | int | 1-20 | Auto-incrementa, cicla após 20 |
| x | int | 0 | Fixo (início da tela) |
| y | int | 0-56 | Posição vertical |
| dir | int | 0 | Fixo (scroll para esquerda) |
| font | int | 0-7 | Fontes seguras testadas |
| TextWidth | int | 64 | Fixo (largura total) |
| speed | int | 10-200 | ms entre frames (menor = mais rápido) |
| color | string | #RRGGBB | Hex com # |
| align | int | 1 | Fixo (esquerda) |

### ClearHttpText
```json
{"Command": "Draw/ClearHttpText"}
```

---

## Decisões Técnicas

| Decisão | Escolha | Justificativa |
|---------|---------|---------------|
| TextId | Backend gerencia | Evita dessincronia com device |
| Fontes | Whitelist 0-7 | Outras podem crashar device |
| Preview | Canvas 320x320 | 64x64 × 5x para visibilidade |
| Animação | requestAnimationFrame | 60fps suave |
| Debounce | 300ms no texto | Performance |
| Confirmação limpar | Não | Ação reversível (enviar novo texto) |

### Valores Default
- Texto: "" (vazio)
- Cor: #FFFFFF (branco)
- Velocidade: 100 (meio-termo)
- Fonte: 0 (default)
- Y: 28 (centro vertical)

---

## Arquivos a Criar

### 1. `app/services/text_sender.py`
```python
# Serviço para envio de texto ao Pixoo
# - send_text(text, color, speed, font, y) -> dict
# - clear_text() -> dict
# - TextId gerenciado internamente (1-20, cicla)
```

### 2. `app/routers/text_display.py`
```python
# Router /api/text
# - POST /send - Envia texto
# - POST /clear - Limpa textos
# Pydantic models: TextRequest, TextResponse
```

---

## Arquivos a Modificar

### 3. `app/main.py`
- Importar e registrar router: `app.include_router(text_display.router)`
- Adicionar rota de página: `@app.get("/text")`

### 4. `app/templates/base.html`
- Adicionar link da aba "Texto" na navegação (após YouTube)
- Adicionar bloco de conteúdo `{% if active_tab == 'text' %}`

### 5. `app/static/js/app.js`
- Adicionar componente `textDisplay()` com Alpine.js
- Estado: text, color, speed, font, yPosition, sending, canvasCtx
- Métodos: sendText(), clearText(), initCanvas(), animatePreview()

### 6. `app/static/css/styles.css`
- Estilos para `.text-controls`, `.text-preview`, `.font-select`

---

## Implementação Fase a Fase

### Fase 1: Backend (Service + Router)

**1.1 Criar `app/services/text_sender.py`**
```python
class TextSender:
    _text_id: int = 0

    def send_text(self, text: str, color: str, speed: int, font: int, y: int) -> dict:
        self._text_id = (self._text_id % 20) + 1
        command = {
            "Command": "Draw/SendHttpText",
            "TextId": self._text_id,
            "x": 0,
            "y": y,
            "dir": 0,
            "font": font,
            "TextWidth": 64,
            "TextString": text,
            "speed": speed,
            "color": color,
            "align": 1
        }
        return get_pixoo_connection().send_command(command)

    def clear_text(self) -> dict:
        self._text_id = 0
        return get_pixoo_connection().send_command({"Command": "Draw/ClearHttpText"})

text_sender = TextSender()
```

**1.2 Criar `app/routers/text_display.py`**
```python
router = APIRouter(prefix="/api/text", tags=["text"])

class TextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    speed: int = Field(default=100, ge=10, le=200)
    font: int = Field(default=0, ge=0, le=7)
    y: int = Field(default=28, ge=0, le=56)

@router.post("/send")
async def send_text(request: TextRequest):
    # Validar conexão, enviar, retornar resultado

@router.post("/clear")
async def clear_text():
    # Limpar textos do device
```

**1.3 Modificar `app/main.py`**
- Adicionar import e include_router
- Adicionar rota `/text` renderizando base.html com active_tab="text"

---

### Fase 2: Frontend (Template + Alpine.js)

**2.1 Modificar `app/templates/base.html`**

Navegação (após linha ~65):
```html
<a href="/text" class="{% if active_tab == 'text' %}active{% endif %}">Texto</a>
```

Conteúdo (após bloco YouTube, ~linha 463):
```html
{% if active_tab == 'text' %}
<div x-data="textDisplay()" x-init="init()">
    <!-- Campo de texto -->
    <div class="form-group">
        <label>Mensagem</label>
        <input type="text" x-model.debounce.300ms="text" placeholder="Digite seu recado..." maxlength="500">
        <small x-text="`${text.length}/500 caracteres`"></small>
    </div>

    <!-- Controles inline: Cor + Fonte -->
    <div class="text-controls">
        <div>
            <label>Cor</label>
            <input type="color" x-model="color">
        </div>
        <div>
            <label>Fonte</label>
            <select x-model="font">
                <option value="0">Padrão</option>
                <option value="2">Compacta</option>
                <option value="4">Larga</option>
                <option value="8">Pequena</option>
            </select>
        </div>
    </div>

    <!-- Velocidade -->
    <div class="form-group">
        <label>Velocidade: <span x-text="speed + 'ms'"></span></label>
        <input type="range" x-model="speed" min="10" max="200" step="10">
        <small>Lento ← → Rápido</small>
    </div>

    <!-- Posição Y -->
    <div class="form-group">
        <label>Posição Vertical: <span x-text="y"></span></label>
        <input type="range" x-model="y" min="0" max="56" step="1">
    </div>

    <!-- Preview Canvas -->
    <div class="preview-container">
        <canvas x-ref="previewCanvas" width="320" height="320"></canvas>
    </div>

    <!-- Ações -->
    <div class="actions">
        <button @click="clearText()" class="secondary" :disabled="!$store.connection.connected">
            Limpar Textos
        </button>
        <button @click="sendText()" :disabled="!canSend">
            <span x-show="!sending">Enviar</span>
            <span x-show="sending">Enviando...</span>
        </button>
    </div>

    <!-- Mensagem -->
    <div x-show="message" :class="'message ' + messageType" x-text="message"></div>
</div>
{% endif %}
```

**2.2 Modificar `app/static/js/app.js`**

Adicionar componente:
```javascript
function textDisplay() {
    return {
        text: '',
        color: '#FFFFFF',
        speed: 100,
        font: 0,
        y: 28,
        sending: false,
        message: '',
        messageType: '',
        animationId: null,
        scrollX: 320,

        get canSend() {
            return this.text.trim() && Alpine.store('connection').connected && !this.sending;
        },

        init() {
            this.$nextTick(() => this.initCanvas());
            this.$watch('text', () => this.resetScroll());
            this.$watch('color', () => {});
            this.$watch('speed', () => {});
            this.$watch('y', () => {});
        },

        initCanvas() {
            const canvas = this.$refs.previewCanvas;
            if (!canvas) return;
            this.ctx = canvas.getContext('2d');
            this.animate();
        },

        resetScroll() {
            this.scrollX = 320;
        },

        animate() {
            if (!this.ctx) return;
            const ctx = this.ctx;

            // Limpar
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, 320, 320);

            // Grid 64x64 (opcional)
            ctx.strokeStyle = '#222';
            for (let i = 0; i <= 64; i++) {
                ctx.beginPath();
                ctx.moveTo(i * 5, 0);
                ctx.lineTo(i * 5, 320);
                ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(0, i * 5);
                ctx.lineTo(320, i * 5);
                ctx.stroke();
            }

            // Texto
            if (this.text) {
                ctx.fillStyle = this.color;
                ctx.font = '40px monospace';
                ctx.textBaseline = 'top';
                ctx.fillText(this.text, this.scrollX, this.y * 5);

                // Scroll
                const textWidth = ctx.measureText(this.text).width;
                this.scrollX -= (210 - this.speed) / 50;
                if (this.scrollX < -textWidth) {
                    this.scrollX = 320;
                }
            }

            this.animationId = requestAnimationFrame(() => this.animate());
        },

        async sendText() {
            if (!this.canSend) return;
            this.sending = true;
            this.clearMessage();

            try {
                const response = await fetch('/api/text/send', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        text: this.text,
                        color: this.color,
                        speed: this.speed,
                        font: parseInt(this.font),
                        y: parseInt(this.y)
                    })
                });

                const data = await response.json();
                if (response.ok) {
                    this.showMessage('Texto enviado!', 'success');
                } else {
                    this.showMessage(data.detail || 'Erro ao enviar', 'error');
                }
            } catch (e) {
                this.showMessage('Erro de conexão', 'error');
            } finally {
                this.sending = false;
            }
        },

        async clearText() {
            try {
                const response = await fetch('/api/text/clear', {method: 'POST'});
                if (response.ok) {
                    this.showMessage('Textos limpos!', 'success');
                }
            } catch (e) {
                this.showMessage('Erro ao limpar', 'error');
            }
        },

        showMessage(msg, type) {
            this.message = msg;
            this.messageType = type;
            setTimeout(() => this.clearMessage(), 3000);
        },

        clearMessage() {
            this.message = '';
            this.messageType = '';
        }
    };
}
```

---

### Fase 3: CSS

**3.1 Adicionar em `app/static/css/styles.css`**
```css
/* Text Controls */
.text-controls {
    display: flex;
    gap: 1rem;
    margin-bottom: 1rem;
}

.text-controls > div {
    flex: 1;
}

.text-controls input[type="color"] {
    width: 100%;
    height: 40px;
    padding: 0;
    border: none;
    cursor: pointer;
}

.text-controls select {
    width: 100%;
}
```

---

## Checklist de Implementação

### Backend
- [ ] Criar `app/services/text_sender.py`
- [ ] Criar `app/routers/text_display.py`
- [ ] Registrar router em `app/main.py`
- [ ] Adicionar rota `/text` em `app/main.py`

### Frontend
- [ ] Adicionar link da aba em `base.html`
- [ ] Adicionar bloco de conteúdo da aba em `base.html`
- [ ] Adicionar componente `textDisplay()` em `app.js`
- [ ] Adicionar CSS em `styles.css`

### Testes
- [ ] Testar envio de texto simples
- [ ] Testar cores diferentes
- [ ] Testar velocidades extremas (10, 200)
- [ ] Testar fontes 0-7
- [ ] Testar posições Y (0, 28, 56)
- [ ] Testar limpar textos
- [ ] Testar sem conexão (botões desabilitados)
- [ ] Testar texto longo (500 chars)

---

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Fonte crashar device | Média | Alto | Whitelist fontes 0-7 apenas |
| Preview não match device | Alta | Baixo | Disclaimer no UI |
| TextId overflow | Baixa | Médio | Ciclar 1-20 automaticamente |
| Texto longo truncado | Média | Baixo | Limite 500 chars + contador |

---

## Referências

- [Divoom API Docs](http://doc.divoom-gz.com/web/#/12)
- [SomethingWithComputers/pixoo](https://github.com/SomethingWithComputers/pixoo)
- [tidyhf/Pixoo64-Advanced-Tools](https://github.com/tidyhf/Pixoo64-Advanced-Tools)
- `app/services/pixoo_connection.py:230` - método send_command()
- `app/routers/gif_upload.py` - padrão de router existente
- `app/static/js/app.js` - padrão de componentes Alpine.js
