# Slider de Precisão com Sensibilidade por Velocidade

**Issue:** A definir
**Data:** 2025-12-18

## Objetivo

Substituir os sliders nativos HTML por um componente customizado que oferece controle preciso para vídeos de qualquer duração, priorizando a experiência em vídeos de até 1 hora.

## Mudanças

### 1. Formato de Tempo
- **Antes:** MM:SS.ms (ex: "00:10.50")
- **Depois:** MM:SS (ex: "00:10")

### 2. Handles do Slider
- **Antes:** Bolinhas (círculos) nativas do browser
- **Depois:** Barras verticais customizadas

### 3. Sensibilidade
- **Antes:** Linear 1:1 (cada pixel = mesma quantidade de tempo)
- **Depois:** Baseada em velocidade do mouse

## Especificação Técnica

### Componente: `PrecisionSlider`

```
┌────────────────────────────────────────────────────────────┐
│ ┃                                                        ┃ │
│ ┃  ══════════════════════════════════════════════════   ┃ │
│ ┃                                                        ┃ │
└────────────────────────────────────────────────────────────┘
  ↑                        ↑                                ↑
handle               track (região                      handle
start               selecionada destacada)               end
```

### Curva de Sensibilidade (Parâmetros Ajustáveis)

```javascript
// CONFIGURAÇÃO - ajustar após testes
const SENSITIVITY_CONFIG = {
    // Thresholds de velocidade (pixels por frame ~16ms)
    thresholds: [2, 5, 15],

    // Multiplicadores correspondentes
    multipliers: [0.05, 0.2, 0.5, 1.0],

    // Labels para debug (opcional)
    labels: ['ultra-fino', 'fino', 'moderado', 'rápido']
};

function getSensitivity(velocity) {
    const { thresholds, multipliers } = SENSITIVITY_CONFIG;

    if (velocity < thresholds[0]) return multipliers[0];
    if (velocity < thresholds[1]) return multipliers[1];
    if (velocity < thresholds[2]) return multipliers[2];
    return multipliers[3];
}
```

### Comportamento Esperado

**Vídeo de 10 minutos (600s) - slider 400px:**
| Movimento | Velocidade | Sensibilidade | Ajuste |
|-----------|------------|---------------|--------|
| Muito lento | 1px | 0.05x | ~0.075s |
| Lento | 3px | 0.2x | ~0.9s |
| Normal | 10px | 0.5x | ~7.5s |
| Rápido | 20px | 1.0x | ~30s |

**Vídeo de 1 hora (3600s) - slider 400px:**
| Movimento | Velocidade | Sensibilidade | Ajuste |
|-----------|------------|---------------|--------|
| Muito lento | 1px | 0.05x | ~0.45s |
| Lento | 3px | 0.2x | ~5.4s |
| Normal | 10px | 0.5x | ~45s |
| Rápido | 20px | 1.0x | ~3min |

## Arquivos a Modificar

### 1. `app/static/js/app.js`

**Remover:**
- Referências a `step="0.1"`
- Formato `.toFixed(2)` em `formatTime()`

**Adicionar:**
- Classe `PrecisionSlider` com drag customizado
- Função `getSensitivity(velocity)`
- Tracking de velocidade do mouse

**Modificar:**
- `timeManagementMixin` - usar novo slider
- `formatTime()` - retornar MM:SS sem decimais
- `parseTimeStr()` - aceitar apenas MM:SS

### 2. `app/templates/base.html`

**Remover:**
- `<input type="range">` para start/end time
- `step="0.1"` dos sliders

**Adicionar:**
- Container para slider customizado
- Estrutura HTML para handles (barras verticais)

**Modificar:**
- Placeholders de "00:00.00" para "00:00"

### 3. `app/static/css/styles.css`

**Adicionar:**
- Estilos para `.precision-slider`
- Estilos para handles (barras verticais)
- Highlight da região selecionada
- Cursor apropriado durante drag

## Estrutura HTML do Slider

```html
<div class="precision-slider"
     x-data="precisionSlider()"
     @mousedown="startDrag($event)"
     @mousemove="onDrag($event)"
     @mouseup="endDrag()"
     @mouseleave="endDrag()">

    <!-- Track de fundo -->
    <div class="slider-track"></div>

    <!-- Região selecionada (entre os handles) -->
    <div class="slider-selection"
         :style="`left: ${startPercent}%; width: ${selectionWidth}%`">
    </div>

    <!-- Handle de início (barra vertical) -->
    <div class="slider-handle slider-handle-start"
         :style="`left: ${startPercent}%`"
         @mousedown.stop="startDrag($event, 'start')">
    </div>

    <!-- Handle de fim (barra vertical) -->
    <div class="slider-handle slider-handle-end"
         :style="`left: ${endPercent}%`"
         @mousedown.stop="startDrag($event, 'end')">
    </div>
</div>
```

## Estilos CSS

```css
.precision-slider {
    position: relative;
    height: 40px;
    background: var(--bg-dark);
    border-radius: 4px;
    cursor: pointer;
    user-select: none;
}

.slider-track {
    position: absolute;
    top: 50%;
    left: 0;
    right: 0;
    height: 4px;
    background: var(--border-color);
    transform: translateY(-50%);
    border-radius: 2px;
}

.slider-selection {
    position: absolute;
    top: 50%;
    height: 4px;
    background: var(--pixoo-cyan);
    transform: translateY(-50%);
    border-radius: 2px;
}

.slider-handle {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 12px;
    background: var(--pixoo-green);
    border-radius: 3px;
    cursor: ew-resize;
    transform: translateX(-50%);

    /* Visual grip lines */
    &::after {
        content: '';
        position: absolute;
        top: 25%;
        bottom: 25%;
        left: 50%;
        width: 2px;
        background: rgba(255,255,255,0.5);
        transform: translateX(-50%);
    }
}

.slider-handle-start {
    background: var(--pixoo-green);
}

.slider-handle-end {
    background: var(--pixoo-red);
}

.slider-handle:hover {
    filter: brightness(1.2);
}

.slider-handle.dragging {
    filter: brightness(1.3);
}
```

## JavaScript: Componente Alpine.js

```javascript
function precisionSlider() {
    return {
        // Estado
        dragging: null, // 'start', 'end', ou null
        lastX: 0,
        lastTime: 0,

        // Configuração de sensibilidade
        sensitivityConfig: {
            thresholds: [2, 5, 15],
            multipliers: [0.05, 0.2, 0.5, 1.0]
        },

        // Computed
        get startPercent() {
            return (this.startTime / this.getMaxDuration()) * 100;
        },

        get endPercent() {
            return (this.endTime / this.getMaxDuration()) * 100;
        },

        get selectionWidth() {
            return this.endPercent - this.startPercent;
        },

        // Métodos
        startDrag(event, handle) {
            this.dragging = handle;
            this.lastX = event.clientX;
            this.lastTime = performance.now();

            // Adicionar listeners globais para drag fora do elemento
            document.addEventListener('mousemove', this.onDrag.bind(this));
            document.addEventListener('mouseup', this.endDrag.bind(this));
        },

        onDrag(event) {
            if (!this.dragging) return;

            const currentTime = performance.now();
            const deltaTime = currentTime - this.lastTime;
            const deltaX = event.clientX - this.lastX;

            // Calcular velocidade (pixels por 16ms frame)
            const velocity = Math.abs(deltaX) / (deltaTime / 16);

            // Obter sensibilidade baseada na velocidade
            const sensitivity = this.getSensitivity(velocity);

            // Calcular mudança de tempo
            const sliderWidth = this.$el.offsetWidth;
            const duration = this.getMaxDuration();
            const baseChange = (deltaX / sliderWidth) * duration;
            const adjustedChange = baseChange * sensitivity;

            // Aplicar mudança
            if (this.dragging === 'start') {
                this.startTime = Math.max(0, Math.min(
                    this.startTime + adjustedChange,
                    this.endTime - 1 // Mínimo 1 segundo de diferença
                ));
                this.startTimeStr = utils.formatTime(this.startTime);
                if (this.seekToTime) this.seekToTime(this.startTime);
            } else if (this.dragging === 'end') {
                this.endTime = Math.max(
                    this.startTime + 1,
                    Math.min(this.endTime + adjustedChange, duration)
                );
                this.endTimeStr = utils.formatTime(this.endTime);
                if (this.seekToTime) this.seekToTime(this.endTime);
            }

            // Atualizar tracking
            this.lastX = event.clientX;
            this.lastTime = currentTime;
        },

        endDrag() {
            this.dragging = null;
            document.removeEventListener('mousemove', this.onDrag);
            document.removeEventListener('mouseup', this.endDrag);
        },

        getSensitivity(velocity) {
            const { thresholds, multipliers } = this.sensitivityConfig;

            if (velocity < thresholds[0]) return multipliers[0];
            if (velocity < thresholds[1]) return multipliers[1];
            if (velocity < thresholds[2]) return multipliers[2];
            return multipliers[3];
        }
    };
}
```

## Plano de Testes

### Fase 1: Implementação Básica
- [ ] Criar componente PrecisionSlider
- [ ] Integrar com mediaUpload (tab Mídia)
- [ ] Integrar com youtubeDownload (tab YouTube)
- [ ] Remover decisegundos do formato de tempo

### Fase 2: Calibração
- [ ] Testar com vídeo de 30 segundos
- [ ] Testar com vídeo de 5 minutos
- [ ] Testar com vídeo de 30 minutos
- [ ] Testar com vídeo de 1 hora
- [ ] Ajustar thresholds e multipliers conforme feedback

### Fase 3: Refinamento
- [ ] Ajustar estilos visuais
- [ ] Garantir responsividade
- [ ] Testar em diferentes tamanhos de janela

## Parâmetros para Calibração

Estes valores devem ser ajustados com base nos testes:

```javascript
// VALORES INICIAIS (ponto de partida)
const SENSITIVITY_CONFIG = {
    thresholds: [2, 5, 15],      // velocidades em px/frame
    multipliers: [0.05, 0.2, 0.5, 1.0]
};

// Se muito sensível (pula demais no modo lento):
// - Diminuir multipliers[0] e multipliers[1]

// Se muito lento (demora para navegar):
// - Aumentar multipliers[2] e multipliers[3]

// Se transições bruscas:
// - Ajustar thresholds para espaçamento maior
```

## Critérios de Aceite

- [ ] Usuário consegue selecionar segundo exato em vídeo de 1 hora
- [ ] Navegação rápida funciona bem (ir do início ao meio do vídeo)
- [ ] Handles visuais são barras verticais (não bolinhas)
- [ ] Formato de tempo é MM:SS (sem decimais)
- [ ] Experiência é fluida e previsível
