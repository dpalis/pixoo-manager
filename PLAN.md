# Pixoo Manager v1.2 - Qualidade e UX

## Overview

A v1.2 do Pixoo Manager foca em duas áreas principais:

1. **Qualidade de Conversão:** Melhorar resultados para conteúdo escuro (imagens e vídeos)
2. **UX de Seleção:** Preview em tempo real nos sliders de tempo para vídeos

**Problema identificado pelo usuário:**
- Imagens escuras ficam com pixelização ruim após conversão
- Vídeos escuros geram GIFs com flickering (pixels oscilando entre frames)
- Sliders de tempo são "às cegas" - não mostram o frame correspondente

---

## Problem Statement

### Qualidade em Conteúdo Escuro

O pipeline atual de enhancement (`enhance_for_led_display()`) usa parâmetros fixos otimizados para imagens com brilho médio:

```python
# Parâmetros atuais (gif_converter.py:211-245)
contrast=1.4      # Esmaga tons escuros
brightness=1.05   # Compensação insuficiente
saturation=1.3    # Fica estranho em áreas escuras
```

Para imagens escuras (brightness < 0.3), esses parâmetros **pioram** a qualidade:
- Contraste 1.4x faz preto ficar mais preto, esmagando detalhes
- Brilho +5% é insuficiente para compensar
- Saturação em tons escuros produz cores não naturais

### Flickering em GIFs de Vídeo

O Pillow quantiza cada frame independentemente ao salvar GIFs:

```python
# Código atual (video_converter.py:241-248)
processed_frames[0].save(
    output_path,
    save_all=True,
    append_images=processed_frames[1:],
    ...
)
```

Cada frame recebe uma paleta de 256 cores ligeiramente diferente. Em tons escuros, pequenas variações de cor são muito perceptíveis → **flickering visual**.

### Seleção "às Cegas"

Os sliders de tempo em vídeos locais e YouTube apenas atualizam texto formatado:

```javascript
// Código atual (app.js:633-663)
updateStartTime() {
    this.startTime = parseFloat(this.startTime);
    this.startTimeStr = utils.formatTime(this.startTime);
    // NÃO faz seek do vídeo
}
```

O usuário não sabe qual frame está selecionando até converter o vídeo.

---

## Proposed Solution

### Ordem de Implementação

```
F3 (Imagens Escuras) → F4 (Anti-Flickering) → F1 (Slider Local) → F2 (Slider YouTube)
```

**Justificativa:** Resolver qualidade primeiro (F3, F4), depois UX (F1, F2). Validar melhorias de qualidade com preview básico antes de investir em YouTube IFrame API.

---

## F1: Preview de Slider - Vídeo Local

### Arquivos

| Arquivo | Modificação |
|---------|-------------|
| `app/static/js/app.js` | Adicionar seek em `updateStartTime()` e `updateEndTime()` |

### Implementação

```javascript
// app/static/js/app.js - função mediaUpload()

updateStartTime() {
    this.startTime = parseFloat(this.startTime);
    if (this.startTime >= this.endTime) {
        this.startTime = Math.max(0, this.endTime - 0.1);
    }
    this.startTimeStr = utils.formatTime(this.startTime);

    // NOVO: Seek do vídeo para posição do slider
    if (this.$refs.videoPlayer && this.$refs.videoPlayer.readyState >= 2) {
        this.$refs.videoPlayer.currentTime = this.startTime;
    }
},

updateEndTime() {
    this.endTime = parseFloat(this.endTime);
    if (this.endTime <= this.startTime) {
        this.endTime = Math.min(this.videoDuration, this.startTime + 0.1);
    }
    this.endTimeStr = utils.formatTime(this.endTime);

    // NOVO: Seek do vídeo para posição do slider
    if (this.$refs.videoPlayer && this.$refs.videoPlayer.readyState >= 2) {
        this.$refs.videoPlayer.currentTime = this.endTime;
    }
}
```

### Decisões Técnicas

| Questão | Decisão | Justificativa |
|---------|---------|---------------|
| Debounce | Não necessário inicialmente | HTML5 Video já trata seeks rápidos internamente |
| Seek failure | Ignorar silenciosamente | `readyState >= 2` garante que vídeo está pronto |
| Codecs não suportados | Erro existente do browser | Já tratado pelo upload |

### Acceptance Criteria

- [ ] Arrastar slider de início faz vídeo mostrar frame correspondente
- [ ] Arrastar slider de fim faz vídeo mostrar frame correspondente
- [ ] Slider só faz seek quando vídeo está carregado (`readyState >= 2`)
- [ ] Digitação manual de tempo também faz seek (via `parseStartTime/parseEndTime`)

---

## F2: Preview de Slider - YouTube

### Arquivos

| Arquivo | Modificação |
|---------|-------------|
| `app/templates/base.html` | Adicionar script YouTube IFrame API, container do player |
| `app/static/js/app.js` | Inicializar player, conectar sliders, gerenciar lifecycle |

### Implementação

#### 1. Carregar YouTube IFrame API

```html
<!-- app/templates/base.html - antes do </body> -->
<script>
    // Flag global para saber quando API está pronta
    window.youtubeApiReady = false;
    window.onYouTubeIframeAPIReady = function() {
        window.youtubeApiReady = true;
        // Dispara evento para Alpine.js
        window.dispatchEvent(new CustomEvent('youtube-api-ready'));
    };
</script>
<script src="https://www.youtube.com/iframe_api"></script>
```

#### 2. Container do Player

```html
<!-- app/templates/base.html - substituir thumbnail por player -->
<template x-if="videoInfo">
    <div class="video-preview-container">
        <!-- Player YouTube (substituir thumbnail) -->
        <div x-show="playerReady" id="youtube-player" class="youtube-player"></div>

        <!-- Fallback: thumbnail estática -->
        <img x-show="!playerReady && !playerError"
             :src="videoInfo.thumbnail"
             class="video-thumbnail"
             alt="Thumbnail do vídeo">

        <!-- Erro de embed -->
        <div x-show="playerError" class="player-error">
            Este vídeo não permite incorporação.
            Selecione o trecho e baixe diretamente.
        </div>
    </div>
</template>
```

#### 3. Lógica do Player

```javascript
// app/static/js/app.js - função youtubeDownload()

function youtubeDownload() {
    return {
        // Estado existente...
        url: '',
        videoInfo: null,
        startTime: 0,
        endTime: 10,

        // NOVO: Estado do player
        player: null,
        playerReady: false,
        playerError: false,

        async fetchInfo() {
            // Código existente de fetch...
            const response = await fetch('/api/youtube/info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: this.url })
            });
            this.videoInfo = await response.json();

            // NOVO: Inicializar player após obter info
            this.initPlayer();
        },

        initPlayer() {
            // Aguardar API estar pronta
            if (!window.youtubeApiReady) {
                window.addEventListener('youtube-api-ready', () => this.initPlayer(), { once: true });
                return;
            }

            // Destruir player anterior se existir
            this.destroyPlayer();

            // Criar novo player
            this.player = new YT.Player('youtube-player', {
                height: '180',
                width: '320',
                videoId: this.videoInfo.id,
                playerVars: {
                    'playsinline': 1,
                    'controls': 0,
                    'modestbranding': 1,
                    'rel': 0,
                    'mute': 1,
                    'origin': window.location.origin
                },
                events: {
                    'onReady': (e) => this.onPlayerReady(e),
                    'onError': (e) => this.onPlayerError(e)
                }
            });
        },

        onPlayerReady(event) {
            this.playerReady = true;
            this.playerError = false;
            // Seek para tempo inicial
            this.player.seekTo(this.startTime, true);
            this.player.pauseVideo();
        },

        onPlayerError(event) {
            // Códigos 101 e 150 = embed desabilitado
            if (event.data === 101 || event.data === 150) {
                this.playerError = true;
                this.playerReady = false;
            }
        },

        updateStartTime() {
            // Código existente de validação...
            this.startTime = parseFloat(this.startTime);
            if (this.startTime >= this.endTime) {
                this.startTime = Math.max(0, this.endTime - 0.1);
            }
            this.startTimeStr = utils.formatTime(this.startTime);

            // NOVO: Seek do player YouTube
            if (this.player && this.playerReady) {
                this.player.seekTo(this.startTime, true);
                this.player.pauseVideo();
            }
        },

        updateEndTime() {
            // Código existente de validação...
            this.endTime = parseFloat(this.endTime);
            if (this.endTime <= this.startTime) {
                this.endTime = Math.min(this.videoInfo.duration, this.startTime + 0.1);
            }
            this.endTimeStr = utils.formatTime(this.endTime);

            // NOVO: Seek do player YouTube
            if (this.player && this.playerReady) {
                this.player.seekTo(this.endTime, true);
                this.player.pauseVideo();
            }
        },

        destroyPlayer() {
            if (this.player) {
                this.player.destroy();
                this.player = null;
            }
            this.playerReady = false;
            this.playerError = false;
        },

        clearVideo() {
            // NOVO: Destruir player ao limpar
            this.destroyPlayer();

            // Código existente de reset...
            this.videoInfo = null;
            this.url = '';
            this.startTime = 0;
            this.endTime = 10;
            // ...
        }
    };
}
```

### Decisões Técnicas

| Questão | Decisão | Justificativa |
|---------|---------|---------------|
| Player size | 320x180 (16:9 thumbnail size) | Consistente com thumbnail atual |
| Controls | Desabilitados (`controls: 0`) | Usuário não precisa play/pause, só seek |
| Mute | Sim (`mute: 1`) | Evita som inesperado |
| Embed disabled | Fallback para thumbnail + mensagem | Vídeo ainda pode ser baixado, só não preview |
| API timeout | Não implementar | Raro, complexidade não justificada |
| Debounce | Não necessário | YouTube API já trata internamente |

### Acceptance Criteria

- [ ] Player YouTube aparece após buscar info do vídeo
- [ ] Arrastar slider de início faz player mostrar frame correspondente
- [ ] Arrastar slider de fim faz player mostrar frame correspondente
- [ ] Player permanece pausado após seek (não continua rodando)
- [ ] Vídeos com embed desabilitado mostram mensagem e mantêm thumbnail
- [ ] Player é destruído ao clicar "Limpar" ou buscar novo vídeo
- [ ] Funciona mesmo se IFrame API demora para carregar

---

## F3: Qualidade em Imagens Escuras

### Arquivos

| Arquivo | Modificação |
|---------|-------------|
| `app/services/gif_converter.py` | Adicionar `detect_brightness()`, `apply_gamma_correction()`, modificar `convert_image_pil()` |

### Implementação

#### 1. Detecção de Brilho

```python
# app/services/gif_converter.py - nova função

def detect_brightness(image: Image.Image) -> float:
    """
    Detecta brilho médio da imagem usando RMS (Root Mean Square).

    RMS é melhor que média simples porque considera variância.

    Args:
        image: Imagem PIL (qualquer modo)

    Returns:
        Brilho normalizado (0.0 a 1.0)
    """
    from PIL import ImageStat

    # Converter para grayscale para cálculo de luminosidade
    grayscale = image.convert('L')
    stat = ImageStat.Stat(grayscale)

    # RMS normalizado para 0-1
    return stat.rms[0] / 255.0
```

#### 2. Correção Gamma

```python
# app/services/gif_converter.py - nova função

def apply_gamma_correction(image: Image.Image, gamma: float = 0.7) -> Image.Image:
    """
    Aplica correção gamma para clarear tons escuros.

    Gamma < 1.0: Clareia (0.5-0.7 para imagens escuras)
    Gamma = 1.0: Sem mudança
    Gamma > 1.0: Escurece

    Args:
        image: Imagem PIL em RGB
        gamma: Fator de correção

    Returns:
        Imagem com gamma corrigido
    """
    # Criar lookup table para performance
    inv_gamma = 1.0 / gamma
    lut = [int((i / 255.0) ** inv_gamma * 255.0) for i in range(256)]

    # Aplicar LUT a cada canal
    return image.point(lut * 3)  # *3 para RGB
```

#### 3. Enhancement Adaptativo

```python
# app/services/gif_converter.py - modificar função existente

def enhance_for_led_display(
    image: Image.Image,
    contrast: float = 1.4,
    saturation: float = 1.3,
    sharpness: float = 1.5,
    auto_brightness: bool = True  # NOVO parâmetro
) -> Image.Image:
    """
    Otimiza imagem para displays LED como Pixoo 64.

    Se auto_brightness=True, detecta brilho e ajusta parâmetros:
    - Imagens escuras (brightness < 0.3): gamma correction + parâmetros suaves
    - Imagens normais: parâmetros padrão

    Args:
        image: Imagem PIL
        contrast: Fator de contraste (ignorado se auto_brightness e imagem escura)
        saturation: Fator de saturação
        sharpness: Fator de nitidez
        auto_brightness: Detectar e ajustar automaticamente

    Returns:
        Imagem otimizada para LED
    """
    img = image

    # NOVO: Detecção e ajuste para imagens escuras
    if auto_brightness:
        brightness = detect_brightness(image)

        if brightness < 0.3:  # Imagem escura
            # Passo 1: Gamma correction para clarear tons escuros
            img = apply_gamma_correction(img, gamma=0.6)

            # Passo 2: Contraste mais suave (não esmagar tons)
            contrast = 1.15

            # Passo 3: Saturação reduzida (tons escuros ficam estranhos com alta saturação)
            saturation = 1.1

    # Pipeline existente com parâmetros ajustados
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = ImageEnhance.Color(img).enhance(saturation)
    img = ImageEnhance.Brightness(img).enhance(1.05)
    img = ImageEnhance.Sharpness(img).enhance(sharpness)

    return img
```

#### 4. Atualizar ConvertOptions

```python
# app/services/gif_converter.py - modificar dataclass

@dataclass
class ConvertOptions:
    """Opções de conversão para GIF."""
    target_size: int = PIXOO_SIZE
    max_frames: int = MAX_CONVERT_FRAMES
    enhance: bool = True
    led_optimize: bool = True
    focus_center: bool = False
    darken_bg: bool = False
    num_colors: int = 0
    auto_brightness: bool = True  # NOVO: Ajuste automático para imagens escuras
```

#### 5. Propagar Flag

```python
# app/services/gif_converter.py - modificar convert_image_pil()

def convert_image_pil(image: Image.Image, options: Optional[ConvertOptions] = None) -> Image.Image:
    if options is None:
        options = ConvertOptions()

    # Downscale adaptativo
    converted = adaptive_downscale(image, options.target_size)

    # Melhorar contraste básico (opcional)
    if options.enhance and not options.led_optimize:
        converted = enhance_contrast(converted, factor=1.15)

    # Otimização para LED display (MODIFICADO: passar auto_brightness)
    if options.led_optimize:
        converted = enhance_for_led_display(
            converted,
            auto_brightness=options.auto_brightness  # NOVO
        )

    # ... resto do código existente
```

### Decisões Técnicas

| Questão | Decisão | Justificativa |
|---------|---------|---------------|
| Threshold de brilho | 0.3 (com `<`, não `<=`) | Baseado em testes - 0.3 RMS é "visivelmente escuro" |
| Gamma para escuras | 0.6 | Clareia sem estourar - testado em imagens reais |
| Contraste para escuras | 1.15 (vs 1.4 padrão) | Evita esmagar tons, preserva detalhes |
| Indicador visual | Não implementar | Simplicidade - usuário vê resultado no preview |
| Cache de brightness | Não implementar | Imagem processada uma vez só, não vale complexidade |

### Acceptance Criteria

- [ ] Imagens com brilho < 0.3 recebem gamma correction automático
- [ ] Imagens com brilho >= 0.3 usam parâmetros padrão
- [ ] `ConvertOptions.auto_brightness=False` desabilita detecção
- [ ] Qualidade visual de imagens escuras melhora visivelmente
- [ ] Imagens normais não são afetadas negativamente

---

## F4: Anti-Flickering em Vídeos Escuros

### Arquivos

| Arquivo | Modificação |
|---------|-------------|
| `app/services/gif_converter.py` | Adicionar `create_global_palette()`, `apply_palette_to_frames()` |
| `app/services/video_converter.py` | Usar paleta global em `convert_video_to_gif()` |

### Implementação

#### 1. Criar Paleta Global

```python
# app/services/gif_converter.py - nova função

def create_global_palette(
    frames: list[Image.Image],
    num_colors: int = 256,
    sample_rate: int = 4
) -> Image.Image:
    """
    Cria paleta de cores otimizada a partir de múltiplos frames.

    Combina pixels de frames amostrados para criar paleta consistente.
    Usa median cut (rápido e bom para animações).

    Args:
        frames: Lista de frames PIL em RGB
        num_colors: Número de cores na paleta (max 256 para GIF)
        sample_rate: Amostrar 1 a cada N frames (para performance)

    Returns:
        Imagem quantizada com paleta otimizada (usar .palette)
    """
    if not frames:
        raise ConversionError("Lista de frames vazia")

    # Amostrar frames para não usar memória demais
    sampled = frames[::sample_rate] if len(frames) > sample_rate else frames

    # Combinar pixels de todos os frames amostrados
    width, height = frames[0].size
    combined_width = width * len(sampled)
    combined = Image.new('RGB', (combined_width, height))

    for i, frame in enumerate(sampled):
        combined.paste(frame.convert('RGB'), (i * width, 0))

    # Quantizar para obter paleta otimizada
    palette_image = combined.quantize(
        colors=num_colors,
        method=Image.Quantize.MEDIANCUT  # Rápido e bom para animações
    )

    return palette_image
```

#### 2. Aplicar Paleta aos Frames

```python
# app/services/gif_converter.py - nova função

def apply_palette_to_frames(
    frames: list[Image.Image],
    palette_image: Image.Image
) -> list[Image.Image]:
    """
    Aplica mesma paleta a todos os frames para consistência.

    Usa dither=0 (sem dithering) para evitar artefatos temporais.
    Trade-off: gradientes podem ter banding, mas animação será suave.

    Args:
        frames: Lista de frames PIL
        palette_image: Imagem quantizada com paleta (de create_global_palette)

    Returns:
        Lista de frames quantizados com paleta consistente
    """
    result = []

    for frame in frames:
        # Converter para RGB e aplicar paleta
        rgb_frame = frame.convert('RGB')
        quantized = rgb_frame.quantize(
            palette=palette_image,
            dither=0  # Sem dithering = consistência temporal
        )
        # Converter de volta para RGB para compatibilidade
        result.append(quantized.convert('RGB'))

    return result
```

#### 3. Integrar em Video Converter

```python
# app/services/video_converter.py - modificar convert_video_to_gif()

def convert_video_to_gif(
    path: Path,
    start: float,
    end: float,
    options: Optional[ConvertOptions] = None,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> Tuple[Path, int]:
    # ... código existente de extração e processamento de frames ...

    # Após processar todos os frames:
    if not processed_frames:
        raise ConversionError("Nenhum frame extraido do video")

    if progress_callback:
        progress_callback("processing", 1.0)

    # NOVO: Criar paleta global para consistência (anti-flickering)
    if progress_callback:
        progress_callback("optimizing", 0.0)

    from app.services.gif_converter import create_global_palette, apply_palette_to_frames

    global_palette = create_global_palette(processed_frames, num_colors=256, sample_rate=4)
    processed_frames = apply_palette_to_frames(processed_frames, global_palette)

    if progress_callback:
        progress_callback("optimizing", 1.0)
        progress_callback("saving", 0.0)

    # Salvar com optimize=False para manter paleta consistente
    durations = [frame_duration] * len(processed_frames)

    processed_frames[0].save(
        output_path,
        save_all=True,
        append_images=processed_frames[1:],
        duration=durations,
        loop=0,
        optimize=False  # IMPORTANTE: Não re-otimizar paleta
    )

    # ... resto do código existente ...
```

#### 4. Aplicar em GIF Converter também

```python
# app/services/gif_converter.py - modificar convert_gif()

def convert_gif(
    input_path: Path,
    options: Optional[ConvertOptions] = None,
    progress_callback: Optional[callable] = None
) -> Tuple[Path, GifMetadata]:
    # ... código existente de processamento de frames ...

    # Após processar todos os frames:

    # NOVO: Aplicar paleta global para consistência
    if len(converted_frames) > 1:
        global_palette = create_global_palette(converted_frames, num_colors=256, sample_rate=4)
        converted_frames = apply_palette_to_frames(converted_frames, global_palette)

    # Criar arquivo de saída
    output_path = create_temp_output(".gif")

    try:
        # Usar Pillow ao invés de imageio para controle de paleta
        converted_frames[0].save(
            output_path,
            save_all=True,
            append_images=converted_frames[1:],
            duration=durations,
            loop=0,
            optimize=False
        )
        # ... resto do código existente ...
```

### Decisões Técnicas

| Questão | Decisão | Justificativa |
|---------|---------|---------------|
| Número de cores | 256 (máximo GIF) | Melhor qualidade possível |
| Sample rate | 4 (1 a cada 4 frames) | Balança memória vs qualidade |
| Dithering | Desabilitado (`dither=0`) | Evita flickering de dithering |
| Aplicar a todos os vídeos | Sim, incondicionalmente | Simplicidade - não prejudica vídeos claros significativamente |
| Fase de progresso | "optimizing" | Usuário sabe que está otimizando |

### Acceptance Criteria

- [ ] GIFs de vídeos escuros não apresentam flickering visível
- [ ] Paleta é criada a partir de frames amostrados (não todos)
- [ ] Progresso mostra fase "optimizing" durante criação de paleta
- [ ] GIFs de vídeos claros mantêm qualidade aceitável
- [ ] GIFs animados (upload) também usam paleta global
- [ ] Tempo de conversão aumenta no máximo 20% (paleta + apply)

---

## Technical Considerations

### Performance

| Operação | Impacto | Mitigação |
|----------|---------|-----------|
| Brightness detection | ~10ms por imagem 64x64 | Negligível |
| Gamma correction | ~5ms por imagem 64x64 | Negligível |
| Global palette creation | ~50-100ms para 92 frames | Sample rate 4 reduz para ~23 frames |
| Palette application | ~5ms por frame | Total ~500ms para 92 frames |

### Memory

| Operação | Uso | Mitigação |
|----------|-----|-----------|
| Combined image para paleta | 64 × 64 × 23 × 3 = ~280KB | Aceitável |
| Frames em memória | Já existente, não muda | N/A |

### Compatibilidade

- **Pillow >= 10.0:** Necessário para `Image.Quantize.MEDIANCUT`
- **YouTube IFrame API:** Requer HTTPS em produção (localhost OK)
- **HTML5 Video:** Suportado em todos browsers modernos

---

## Dependencies & Risks

### Dependencies

| Dependência | Feature | Risco |
|-------------|---------|-------|
| YouTube IFrame API | F2 | API externa, pode mudar |
| Pillow ImageStat | F3 | Já instalado |
| Pillow quantize | F4 | Já instalado |

### Risks

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| YouTube muda API | Baixa | Alto | Fallback para thumbnail |
| Paleta global piora vídeos coloridos | Média | Baixo | Trade-off aceitável |
| Gamma muito agressivo | Baixa | Médio | Testado com 0.6, conservador |

---

## Success Metrics

| Métrica | Baseline | Target |
|---------|----------|--------|
| Qualidade visual em imagens escuras | Ruim (feedback usuário) | Boa (sem crushing) |
| Flickering em vídeos escuros | Presente (feedback usuário) | Ausente ou mínimo |
| Tempo de conversão | ~2s para 5s vídeo | ~2.5s (max +25%) |
| UX de seleção de tempo | "às cegas" | Preview em tempo real |

---

## Test Plan

### F1: Preview Slider Local

- [ ] Upload vídeo MP4 → arrastar slider início → vídeo mostra frame
- [ ] Upload vídeo MP4 → arrastar slider fim → vídeo mostra frame
- [ ] Arrastar slider rápido → último frame é mostrado (não acumula)
- [ ] Digitar tempo manual → vídeo mostra frame correspondente

### F2: Preview Slider YouTube

- [ ] Buscar vídeo público → player aparece → arrastar slider → frame atualiza
- [ ] Buscar vídeo com embed desabilitado → mensagem de erro + thumbnail
- [ ] Buscar outro vídeo → player anterior é destruído
- [ ] Clicar "Limpar" → player é destruído

### F3: Imagens Escuras

- [ ] Upload imagem escura (brightness < 0.3) → gamma aplicado → preview mais claro
- [ ] Upload imagem normal → parâmetros padrão → sem mudança perceptível
- [ ] Comparar antes/depois lado a lado

### F4: Anti-Flickering

- [ ] Converter vídeo escuro 5s → GIF sem flickering visível
- [ ] Converter vídeo claro 5s → GIF com qualidade aceitável
- [ ] Verificar que progresso mostra fase "optimizing"
- [ ] Medir tempo de conversão (max +25%)

---

## References

### Internal

- `app/services/gif_converter.py:211-245` - enhance_for_led_display() atual
- `app/services/video_converter.py:147-260` - convert_video_to_gif() atual
- `app/static/js/app.js:633-663` - updateStartTime/updateEndTime atuais
- `app/static/js/app.js:804-1055` - youtubeDownload() atual

### External

- [YouTube IFrame API Reference](https://developers.google.com/youtube/iframe_api_reference)
- [Pillow ImageStat](https://pillow.readthedocs.io/en/stable/reference/ImageStat.html)
- [Pillow Image.quantize](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.quantize)
- [Gamma Correction](https://en.wikipedia.org/wiki/Gamma_correction)

### Research Files (generated)

- `/Users/dpalis/Coding/Pixoo 64/FRAMEWORK_DOCS.md` - Documentação completa dos frameworks
- `/Users/dpalis/Coding/Pixoo 64/RESEARCH_SUMMARY.md` - Resumo da pesquisa

---

## Checklist de Implementação

### Fase 1: Qualidade (F3 + F4)

- [ ] **F3.1:** Adicionar `detect_brightness()` em gif_converter.py
- [ ] **F3.2:** Adicionar `apply_gamma_correction()` em gif_converter.py
- [ ] **F3.3:** Modificar `enhance_for_led_display()` para detecção automática
- [ ] **F3.4:** Adicionar `auto_brightness` em ConvertOptions
- [ ] **F3.5:** Testar com imagens escuras e normais
- [ ] **F4.1:** Adicionar `create_global_palette()` em gif_converter.py
- [ ] **F4.2:** Adicionar `apply_palette_to_frames()` em gif_converter.py
- [ ] **F4.3:** Integrar em `convert_video_to_gif()`
- [ ] **F4.4:** Integrar em `convert_gif()`
- [ ] **F4.5:** Adicionar fase "optimizing" no progress callback
- [ ] **F4.6:** Testar com vídeos escuros e claros

### Fase 2: UX (F1 + F2)

- [ ] **F1.1:** Adicionar seek em `updateStartTime()` do mediaUpload
- [ ] **F1.2:** Adicionar seek em `updateEndTime()` do mediaUpload
- [ ] **F1.3:** Testar com diferentes formatos de vídeo
- [ ] **F2.1:** Adicionar script YouTube IFrame API em base.html
- [ ] **F2.2:** Adicionar container do player em base.html
- [ ] **F2.3:** Implementar `initPlayer()` em youtubeDownload
- [ ] **F2.4:** Implementar `destroyPlayer()` em youtubeDownload
- [ ] **F2.5:** Conectar sliders ao player
- [ ] **F2.6:** Adicionar tratamento de erro para embed desabilitado
- [ ] **F2.7:** Testar com vídeos públicos e restritos

---

## Estimativa

| Feature | Complexidade | Tempo Estimado |
|---------|--------------|----------------|
| F3: Imagens Escuras | Baixa-Média | 30-45 min |
| F4: Anti-Flickering | Média | 1-2h |
| F1: Slider Local | Baixa | 15 min |
| F2: Slider YouTube | Média | 1-2h |
| **Total** | | **3-5h** |

**Com multiplicador 3x:** 1-2 dias úteis
