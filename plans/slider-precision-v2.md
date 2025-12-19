# Slider de Precisão v2 - Pointer Lock API

**Data:** 2025-12-18
**Status:** Plano revisado após testes da v1

## Contexto

### Problema Original
- Vídeos podem ter até 1+ hora de duração
- Slider de ~400px → cada pixel = 9 segundos (para vídeo de 1h)
- Usuário precisa selecionar trechos com precisão de segundos

### Abordagem v1 (Falhou)
- Sensibilidade baseada em velocidade com multiplicadores no delta
- **Problema:** Handle "descola" do cursor, criando UX ruim
- Usuário espera que handle esteja sempre onde o cursor está

### Nova Abordagem v2
- **Pointer Lock API**: Cursor desaparece, handle é o único feedback visual
- Controle total sobre sensibilidade sem drift visual
- Padrão em editores profissionais (DaVinci, Premiere, jogos)

## Especificação Técnica

### Pointer Lock API

```javascript
// Ativar quando usuário clica no handle
element.requestPointerLock();

// Durante drag, recebemos movimento RAW do mouse
document.addEventListener('mousemove', (e) => {
    const rawDelta = e.movementX; // Pixels físicos movidos
    // Aplicar sensibilidade customizada
});

// Desativar quando solta o mouse
document.exitPointerLock();
```

### Curva de Sensibilidade Contínua

Em vez de níveis discretos, usar função contínua para transições imperceptíveis:

```javascript
/**
 * Calcula sensibilidade baseada na velocidade do mouse.
 *
 * @param {number} velocity - Velocidade em pixels/frame
 * @param {number} videoDuration - Duração do vídeo em segundos
 * @returns {number} - Segundos por pixel de movimento
 */
function calculateSensitivity(velocity, videoDuration) {
    // Parâmetros ajustáveis
    const CONFIG = {
        minSensitivity: 0.05,  // Movimento lento: 0.05s por pixel
        maxSensitivity: 2.0,   // Movimento rápido: 2s por pixel (ajusta com duração)
        velocityScale: 0.1,    // Quão rápido a sensibilidade aumenta

        // Escala máxima baseada na duração do vídeo
        durationFactor: Math.min(videoDuration / 600, 3), // Cap em 3x para vídeos > 10min
    };

    // Função sigmóide para transição suave
    const normalizedVelocity = velocity * CONFIG.velocityScale;
    const sigmoidFactor = 1 / (1 + Math.exp(-normalizedVelocity + 3));

    // Interpolar entre min e max
    const baseSensitivity = CONFIG.minSensitivity +
        (CONFIG.maxSensitivity - CONFIG.minSensitivity) * sigmoidFactor;

    // Ajustar para duração do vídeo
    return baseSensitivity * CONFIG.durationFactor;
}
```

### Comportamento Esperado

**Vídeo de 10 minutos (600s):**
| Velocidade Mouse | Sensibilidade | Resultado |
|------------------|---------------|-----------|
| Muito lento (1px/frame) | ~0.05s/px | Precisão de décimos de segundo |
| Lento (5px/frame) | ~0.2s/px | Ajuste fino |
| Normal (15px/frame) | ~0.8s/px | Navegação moderada |
| Rápido (30px/frame) | ~2s/px | Navegação rápida |

**Vídeo de 1 hora (3600s):**
| Velocidade Mouse | Sensibilidade | Resultado |
|------------------|---------------|-----------|
| Muito lento (1px/frame) | ~0.15s/px | Precisão de segundos |
| Lento (5px/frame) | ~0.6s/px | Ajuste fino |
| Normal (15px/frame) | ~2.4s/px | Navegação moderada |
| Rápido (30px/frame) | ~6s/px | Navegação rápida |

## Estrutura do Componente

### HTML

```html
<div class="precision-slider" x-data="precisionSlider()">
    <!-- Track de fundo -->
    <div class="slider-track"></div>

    <!-- Região selecionada -->
    <div class="slider-selection"
         :style="`left: ${startPercent}%; width: ${selectionWidth}%`">
    </div>

    <!-- Handle início (barra vertical) -->
    <div class="slider-handle slider-handle-start"
         :style="`left: ${startPercent}%`"
         @mousedown="startDrag($event, 'start')">
    </div>

    <!-- Handle fim (barra vertical) -->
    <div class="slider-handle slider-handle-end"
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
    transition: filter 0.1s;

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

.slider-handle.dragging {
    filter: brightness(1.3);
}
```

### JavaScript (Alpine.js)

```javascript
function precisionSlider() {
    return {
        // Estado
        dragging: null,           // 'start' | 'end' | null
        lastMovementTime: 0,
        velocityBuffer: [],       // Últimas N velocidades para smoothing

        // Configuração
        config: {
            minSensitivity: 0.05,
            maxSensitivity: 2.0,
            velocityScale: 0.1,
            velocityBufferSize: 5,  // Frames para média móvel
        },

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

        // Iniciar drag com Pointer Lock
        startDrag(event, handle) {
            event.preventDefault();
            this.dragging = handle;
            this.lastMovementTime = performance.now();
            this.velocityBuffer = [];

            // Ativar Pointer Lock
            event.target.requestPointerLock();

            // Listeners globais
            document.addEventListener('mousemove', this.onDrag);
            document.addEventListener('mouseup', this.endDrag);

            // Listener para saída do Pointer Lock
            document.addEventListener('pointerlockchange', this.onPointerLockChange);
        },

        // Handler de movimento
        onDrag(event) {
            if (!this.dragging) return;

            const now = performance.now();
            const deltaTime = now - this.lastMovementTime;
            const rawDelta = event.movementX;

            // Calcular velocidade (pixels por 16ms frame)
            const instantVelocity = Math.abs(rawDelta) / Math.max(deltaTime / 16, 1);

            // Média móvel para suavizar
            this.velocityBuffer.push(instantVelocity);
            if (this.velocityBuffer.length > this.config.velocityBufferSize) {
                this.velocityBuffer.shift();
            }
            const smoothVelocity = this.velocityBuffer.reduce((a, b) => a + b, 0)
                                   / this.velocityBuffer.length;

            // Calcular sensibilidade
            const duration = this.getMaxDuration();
            const sensitivity = this.calculateSensitivity(smoothVelocity, duration);

            // Aplicar mudança
            const timeChange = rawDelta * sensitivity;

            if (this.dragging === 'start') {
                this.startTime = Math.max(0, Math.min(
                    this.startTime + timeChange,
                    this.endTime - 1
                ));
                this.startTimeStr = utils.formatTime(this.startTime);
                if (this.seekToTime) this.seekToTime(this.startTime);
            } else {
                this.endTime = Math.max(
                    this.startTime + 1,
                    Math.min(this.endTime + timeChange, duration)
                );
                this.endTimeStr = utils.formatTime(this.endTime);
                if (this.seekToTime) this.seekToTime(this.endTime);
            }

            this.lastMovementTime = now;
        },

        // Calcular sensibilidade com curva contínua
        calculateSensitivity(velocity, videoDuration) {
            const { minSensitivity, maxSensitivity, velocityScale } = this.config;

            // Fator de escala baseado na duração
            const durationFactor = Math.min(videoDuration / 600, 3);

            // Função sigmóide para transição suave
            const normalizedVelocity = velocity * velocityScale;
            const sigmoidFactor = 1 / (1 + Math.exp(-normalizedVelocity + 3));

            // Interpolar
            const baseSensitivity = minSensitivity +
                (maxSensitivity - minSensitivity) * sigmoidFactor;

            return baseSensitivity * durationFactor;
        },

        // Finalizar drag
        endDrag() {
            this.dragging = null;
            this.velocityBuffer = [];

            // Sair do Pointer Lock
            document.exitPointerLock();

            // Remover listeners
            document.removeEventListener('mousemove', this.onDrag);
            document.removeEventListener('mouseup', this.endDrag);
        },

        // Handler para mudança de Pointer Lock (ESC para cancelar)
        onPointerLockChange() {
            if (!document.pointerLockElement && this.dragging) {
                this.endDrag();
            }
        }
    };
}
```

## Arquivos a Modificar

### 1. `app/static/js/app.js`

- Adicionar componente `precisionSlider()`
- Modificar `timeManagementMixin` para integrar
- Atualizar `formatTime()` para MM:SS (sem decimais)
- Atualizar `parseTimeStr()` para aceitar MM:SS

### 2. `app/templates/base.html`

- Substituir `<input type="range">` pelo novo componente
- Tab Mídia (vídeos locais)
- Tab YouTube

### 3. `app/static/css/styles.css`

- Adicionar estilos `.precision-slider`
- Remover estilos antigos dos range inputs

## Fluxo de Interação

```
1. Usuário posiciona mouse sobre handle
   └─► Cursor: ew-resize (seta horizontal)

2. Usuário clica e segura
   └─► Pointer Lock ativado
   └─► Cursor desaparece
   └─► Handle destaca (brightness)

3. Usuário move mouse
   └─► Movimento lento → handle move pouco (precisão)
   └─► Movimento rápido → handle move muito (navegação)
   └─► Vídeo faz seek em tempo real

4. Usuário solta o mouse
   └─► Pointer Lock desativado
   └─► Cursor reaparece
   └─► Handle volta ao estado normal

5. Usuário pressiona ESC durante drag
   └─► Cancela operação
   └─► Pointer Lock desativado
```

## Parâmetros para Calibração

```javascript
const CONFIG = {
    // Sensibilidade mínima (movimento muito lento)
    // Menor = mais preciso, mas mais lento para navegar
    minSensitivity: 0.05,  // segundos por pixel

    // Sensibilidade máxima (movimento rápido)
    // Maior = navegação mais rápida
    maxSensitivity: 2.0,   // segundos por pixel

    // Escala de velocidade
    // Menor = precisa mover mais rápido para atingir max
    velocityScale: 0.1,

    // Buffer de velocidade (suavização)
    // Maior = mais smooth, mas menos responsivo
    velocityBufferSize: 5,
};
```

## Plano de Testes

### Fase 1: Implementação Básica
- [ ] Criar componente precisionSlider()
- [ ] Integrar Pointer Lock API
- [ ] Verificar que cursor desaparece/reaparece corretamente
- [ ] Verificar ESC cancela drag

### Fase 2: Calibração
- [ ] Testar com vídeo de 30 segundos
- [ ] Testar com vídeo de 5 minutos
- [ ] Testar com vídeo de 30 minutos
- [ ] Testar com vídeo de 1 hora
- [ ] Ajustar CONFIG conforme feedback

### Fase 3: Integração
- [ ] Integrar com tab Mídia
- [ ] Integrar com tab YouTube
- [ ] Verificar seek do vídeo funciona
- [ ] Verificar campos de texto MM:SS sincronizam

### Fase 4: Refinamento
- [ ] Testar em diferentes tamanhos de janela
- [ ] Verificar comportamento com múltiplos monitores
- [ ] Polir visual dos handles

## Critérios de Aceite

- [ ] Movimento lento permite ajuste de ~1 segundo em vídeo de 1 hora
- [ ] Movimento rápido permite navegar de ponta a ponta em ~3 segundos
- [ ] Cursor desaparece durante drag (Pointer Lock)
- [ ] ESC cancela a operação
- [ ] Handles são barras verticais (não bolinhas)
- [ ] Formato de tempo é MM:SS
- [ ] Transições de sensibilidade são imperceptíveis (curva contínua)

## Riscos e Mitigações

| Risco | Probabilidade | Mitigação |
|-------|--------------|-----------|
| Pointer Lock não suportado | Baixa (suporte amplo) | Fallback para drag normal |
| Usuário não entende que cursor sumiu | Média | Handle destaca visualmente |
| Calibração difícil de acertar | Alta | Parâmetros facilmente ajustáveis |
| Performance com seek frequente | Baixa | Throttle no seek se necessário |

## Referências

- [Pointer Lock API - MDN](https://developer.mozilla.org/en-US/docs/Web/API/Pointer_Lock_API)
- [OBSlider - Variable Scrubbing](https://oleb.net/blog/2011/01/obslider-a-uislider-subclass-with-variable-scrubbing-speed/)
- [Sigmoid Function](https://en.wikipedia.org/wiki/Sigmoid_function)
