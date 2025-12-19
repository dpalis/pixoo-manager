# Slider de Precisão v3 - Setas do Teclado

**Data:** 2025-12-18
**Status:** Plano simplificado após iterações

## Contexto

### Abordagens Anteriores (Descartadas)
- **v1**: Sensibilidade por velocidade → Handle descolava do cursor
- **v2**: Pointer Lock API → Complexidade desnecessária
- **v2.1**: Elástico com limite → Ainda complexo demais

### Nova Abordagem v3
- **Slider**: Mapeamento 1:1 simples (handle = cursor)
- **Setas do teclado**: Ajuste fino de precisão
- Padrão usado em editores profissionais (Premiere, DaVinci, Final Cut)

## Especificação

### Controles

| Controle | Ação | Incremento |
|----------|------|------------|
| **Mouse drag** | Navegação pelo slider | Proporcional à posição |
| **←** | Retroceder | -0.5 segundo |
| **→** | Avançar | +0.5 segundo |
| **Shift + ←** | Retroceder rápido | -5 segundos |
| **Shift + →** | Avançar rápido | +5 segundos |

### Fluxo de Uso

```
1. Usuário arrasta slider para região aproximada (~45:30)
2. Solta o mouse
3. Usa ← ou → para ajustar fino: 45:30 → 45:29.5 → 45:29 → 45:28.5
4. Ou Shift+← para pular: 45:30 → 45:25 → 45:20
5. Encontra o ponto exato desejado
```

### Qual Handle Recebe o Ajuste?

**Regra:** O último handle interagido (clicado/arrastado) recebe os ajustes das setas.

```javascript
// Estado
lastActiveHandle: 'start' | 'end' | null

// Ao clicar/arrastar um handle
lastActiveHandle = 'start' // ou 'end'

// Ao pressionar seta
if (lastActiveHandle === 'start') {
    adjustStartTime(delta);
} else if (lastActiveHandle === 'end') {
    adjustEndTime(delta);
}
```

**Feedback visual:** Handle ativo tem destaque (borda, brilho) para indicar qual receberá ajustes.

## Implementação

### Mudanças no Formato de Tempo

**Antes:** MM:SS (segundos inteiros)
**Depois:** MM:SS.s (com décimos para acomodar 0.5s)

Ou alternativamente: manter MM:SS no display mas internamente trabalhar com 0.5s.

**Decisão:** Manter MM:SS no display. Internamente o valor pode ser 45.5, mas exibe "00:45" ou "00:46" (arredondado).

### HTML - Slider (sem mudanças estruturais)

```html
<div class="precision-slider"
     x-data="precisionSlider()"
     @keydown.left.prevent="adjustTime(-0.5)"
     @keydown.right.prevent="adjustTime(0.5)"
     @keydown.left.shift.prevent="adjustTime(-5)"
     @keydown.right.shift.prevent="adjustTime(5)"
     tabindex="0">

    <!-- Track -->
    <div class="slider-track"></div>

    <!-- Região selecionada -->
    <div class="slider-selection"
         :style="`left: ${startPercent}%; width: ${selectionWidth}%`">
    </div>

    <!-- Handle início -->
    <div class="slider-handle slider-handle-start"
         :class="{ 'active': lastActiveHandle === 'start' }"
         :style="`left: ${startPercent}%`"
         @mousedown="startDrag($event, 'start')">
    </div>

    <!-- Handle fim -->
    <div class="slider-handle slider-handle-end"
         :class="{ 'active': lastActiveHandle === 'end' }"
         :style="`left: ${endPercent}%`"
         @mousedown="startDrag($event, 'end')">
    </div>
</div>
```

### CSS

```css
.precision-slider {
    position: relative;
    height: 40px;
    background: var(--bg-dark);
    border-radius: 4px;
    user-select: none;
    outline: none; /* Remove outline padrão do focus */
}

.precision-slider:focus-within {
    /* Indicador sutil de que pode usar teclado */
    box-shadow: 0 0 0 2px var(--pixoo-cyan-dim);
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
    top: 4px;
    bottom: 4px;
    width: 14px;
    border-radius: 3px;
    cursor: ew-resize;
    transform: translateX(-50%);
    transition: filter 0.1s, box-shadow 0.1s;

    /* Linhas de grip */
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 2px;
}

.slider-handle::before,
.slider-handle::after {
    content: '';
    width: 2px;
    height: 40%;
    background: rgba(255, 255, 255, 0.4);
    border-radius: 1px;
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

/* Handle ativo (receberá ajustes de seta) */
.slider-handle.active {
    box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.3);
    filter: brightness(1.1);
}
```

### JavaScript (Alpine.js)

```javascript
function precisionSlider() {
    return {
        // Estado
        dragging: null,
        lastActiveHandle: null, // 'start' | 'end'

        // Computed
        get startPercent() {
            const max = this.getMaxDuration();
            return max > 0 ? (this.startTime / max) * 100 : 0;
        },

        get endPercent() {
            const max = this.getMaxDuration();
            return max > 0 ? (this.endTime / max) * 100 : 0;
        },

        get selectionWidth() {
            return this.endPercent - this.startPercent;
        },

        // Iniciar drag
        startDrag(event, handle) {
            event.preventDefault();
            this.dragging = handle;
            this.lastActiveHandle = handle;

            // Focus no slider para receber eventos de teclado
            this.$el.focus();

            // Listeners globais
            const onMove = (e) => this.onDrag(e);
            const onUp = () => {
                this.dragging = null;
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
            };

            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        },

        // Durante drag - mapeamento 1:1 simples
        onDrag(event) {
            if (!this.dragging) return;

            const rect = this.$el.getBoundingClientRect();
            const x = event.clientX - rect.left;
            const percent = Math.max(0, Math.min(1, x / rect.width));
            const duration = this.getMaxDuration();
            const newTime = percent * duration;

            if (this.dragging === 'start') {
                // Não ultrapassar o handle de fim (mínimo 1s de diferença)
                this.startTime = Math.max(0, Math.min(newTime, this.endTime - 1));
                this.startTimeStr = utils.formatTime(this.startTime);
                if (this.seekToTime) this.seekToTime(this.startTime);
            } else {
                // Não ficar antes do handle de início
                this.endTime = Math.max(this.startTime + 1, Math.min(newTime, duration));
                this.endTimeStr = utils.formatTime(this.endTime);
                if (this.seekToTime) this.seekToTime(this.endTime);
            }
        },

        // Ajuste via setas do teclado
        adjustTime(delta) {
            if (!this.lastActiveHandle) {
                // Se nenhum handle foi selecionado, selecionar o de início
                this.lastActiveHandle = 'start';
            }

            const duration = this.getMaxDuration();

            if (this.lastActiveHandle === 'start') {
                const newTime = this.startTime + delta;
                // Limites: >= 0 e < endTime - 1
                this.startTime = Math.max(0, Math.min(newTime, this.endTime - 1));
                this.startTimeStr = utils.formatTime(this.startTime);
                if (this.seekToTime) this.seekToTime(this.startTime);
            } else {
                const newTime = this.endTime + delta;
                // Limites: > startTime + 1 e <= duration
                this.endTime = Math.max(this.startTime + 1, Math.min(newTime, duration));
                this.endTimeStr = utils.formatTime(this.endTime);
                if (this.seekToTime) this.seekToTime(this.endTime);
            }
        },

        // Atalho para os bindings de teclado
        handleKeydown(event) {
            const delta = event.shiftKey ? 5 : 0.5;

            if (event.key === 'ArrowLeft') {
                event.preventDefault();
                this.adjustTime(-delta);
            } else if (event.key === 'ArrowRight') {
                event.preventDefault();
                this.adjustTime(delta);
            }
        }
    };
}
```

## Integração com Componentes Existentes

### mediaUpload()

```javascript
// Adicionar ao componente existente
{
    ...precisionSlider(),  // Mixin ou copiar métodos

    // Manter métodos existentes
    seekToTime(time) {
        if (this.$refs.videoPlayer) {
            this.$refs.videoPlayer.currentTime = time;
        }
    },

    getMaxDuration() {
        return this.videoDuration || 0;
    }
}
```

### youtubeDownload()

```javascript
// Similar ao mediaUpload
{
    ...precisionSlider(),

    seekToTime(time) {
        if (this.player && this.player.seekTo) {
            this.player.seekTo(time, true);
        }
    },

    getMaxDuration() {
        return this.videoInfo?.duration || 0;
    }
}
```

## Arquivos a Modificar

### 1. `app/static/js/app.js`

- Adicionar lógica `precisionSlider()` ou integrar aos componentes existentes
- Adicionar método `adjustTime(delta)`
- Adicionar estado `lastActiveHandle`
- Modificar `formatTime()` para lidar com decimais internamente

### 2. `app/templates/base.html`

- Adicionar `tabindex="0"` ao container do slider
- Adicionar `@keydown` handlers
- Adicionar classe `.active` condicional nos handles
- Manter handles como barras verticais

### 3. `app/static/css/styles.css`

- Adicionar estilo `.slider-handle.active`
- Adicionar estilo `:focus-within` para o container

## Acessibilidade

- `tabindex="0"` permite foco via Tab
- Setas funcionam quando slider está focado
- Handle ativo tem indicador visual
- Funciona com screen readers (aria-label pode ser adicionado)

## Plano de Testes

### Fase 1: Implementação
- [ ] Slider com handles de barra vertical
- [ ] Drag 1:1 funcionando
- [ ] Setas ←/→ ajustando ±0.5s
- [ ] Shift+setas ajustando ±5s
- [ ] Handle ativo com destaque visual

### Fase 2: Integração
- [ ] Funciona na tab Mídia
- [ ] Funciona na tab YouTube
- [ ] Seek do vídeo sincroniza
- [ ] Campos de texto MM:SS sincronizam

### Fase 3: Edge Cases
- [ ] Limites respeitados (não passa de 0 ou duração)
- [ ] Handles não se cruzam (mínimo 1s entre eles)
- [ ] Funciona com vídeos curtos (<10s)
- [ ] Funciona com vídeos longos (1h+)

## Critérios de Aceite

- [ ] Slider segue mouse 1:1 (sem lag, sem drift)
- [ ] ← e → ajustam em ±0.5 segundo
- [ ] Shift + ← e → ajustam em ±5 segundos
- [ ] Handle ativo tem indicador visual claro
- [ ] Handles são barras verticais (não bolinhas)
- [ ] Formato de tempo é MM:SS
- [ ] Vídeo faz seek ao ajustar

## Vantagens desta Abordagem

1. **Simplicidade**: Sem lógica complexa de velocidade/drift
2. **Previsibilidade**: Comportamento consistente e compreensível
3. **Precisão garantida**: 0.5s independente da duração do vídeo
4. **Padrão conhecido**: Usuários de editores de vídeo conhecem este padrão
5. **Fácil de implementar**: Menos código, menos bugs
