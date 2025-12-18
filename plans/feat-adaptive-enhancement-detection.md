# feat: Detecção Adaptativa de Enhancement para Imagens Claras

## Overview

Implementar detecção automática de características da imagem (brilho, contraste) para escolher parâmetros de enhancement apropriados. Imagens claras e bem definidas devem usar parâmetros suaves para evitar flickering, enquanto imagens escuras ou de baixo contraste mantêm os parâmetros mais agressivos.

## Problem Statement

### Causa Raiz Identificada

Os parâmetros de enhancement atuais (`contrast=1.4`, `saturation=1.3`, `sharpness=1.5`) causam flickering em imagens claras e bem definidas. Investigação detalhada revelou:

| Métrica | Camel_FIRST (bom) | exp_A (ruim) | Diferença |
|---------|-------------------|--------------|-----------|
| Contraste | **1.15** | 1.4 | +22% |
| Saturação | **1.0** | 1.3 | +30% |
| Sharpness | **1.0** | 1.5 | +50% |
| Saturação vs Original | +12% | +52% | 4.3x |

### Por que Causa Flickering

1. **Sharpness 1.5** amplifica pequenas diferenças entre frames
2. **Contraste 1.4** exagera essas diferenças
3. **Saturação 1.3** faz variações de cor ficarem mais visíveis
4. Resultado: diferenças imperceptíveis no original viram flickering visível

### Evidências

- `Melhorias/Camel_FIRST.gif` - Referência de qualidade boa (gerado com parâmetros suaves)
- `Melhorias/exp_A_v1.gif` - Qualidade ruim (parâmetros agressivos atuais)
- 100% dos pixels são diferentes entre FIRST e exp_A
- 0 cores em comum entre as duas versões

## Proposed Solution

### Estratégia: Detecção Adaptativa Simples

Detectar características da imagem e escolher um dos três pipelines:

```
┌─────────────────────────────────────────────────────────────────┐
│                    DETECTION FLOW                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   [Image] ──► detect_brightness() ──► brightness < 0.3?         │
│                                              │                   │
│                                     ┌────────┴────────┐          │
│                                     ▼                 ▼          │
│                                   YES               NO           │
│                                     │                 │          │
│                                     ▼                 ▼          │
│                            [DARK PIPELINE]    detect_contrast()  │
│                            gamma + moderate          │           │
│                                              ┌───────┴───────┐   │
│                                              ▼               ▼   │
│                                         stddev < 50    stddev ≥ 50│
│                                              │               │   │
│                                              ▼               ▼   │
│                                    [BRIGHT_LOW_CONTRAST] [BRIGHT_HIGH_CONTRAST]│
│                                      moderate            minimal │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Três Pipelines de Enhancement

| Pipeline | Condição | Parâmetros |
|----------|----------|------------|
| **DARK** | brightness < 0.3 | gamma=0.6, contrast=1.15, sat=1.1, sharp=1.2 |
| **BRIGHT_LOW_CONTRAST** | brightness ≥ 0.3 AND stddev < 50 | contrast=1.25, sat=1.15, sharp=1.3 |
| **BRIGHT_HIGH_CONTRAST** | brightness ≥ 0.3 AND stddev ≥ 50 | contrast=1.15, sat=1.0, sharp=1.0 |

### Decisões Técnicas

1. **Detecção de Contraste**: Usar `ImageStat.Stat(grayscale).stddev[0]`
   - Simples, rápido, já disponível no Pillow
   - stddev < 50 = baixo contraste, stddev ≥ 50 = alto contraste

2. **Análise de Vídeo**: Usar média do primeiro frame
   - Evita inconsistência temporal
   - Performance aceitável (1 análise por conversão)

3. **Fallback**: Se detecção falhar, usar BRIGHT_HIGH_CONTRAST (mais seguro)

4. **Não modificar ConvertOptions**: Detecção interna ao `enhance_for_led_display()`

## Technical Approach

### Arquivos a Modificar

```
app/services/gif_converter.py
├── Linha 26-48: Adicionar novas constantes
├── Linha 240+: Nova função detect_contrast()
├── Linha 265-319: Modificar enhance_for_led_display()
└── Linha 480+: Verificar convert_image_pil() (sem mudanças)
```

### Implementação

#### Fase 1: Adicionar Constantes

```python
# app/services/gif_converter.py (após linha 48)

# ============================================
# Adaptive Enhancement Thresholds
# ============================================

# Contrast detection (stddev of grayscale)
CONTRAST_HIGH_THRESHOLD = 50  # stddev >= 50 = high contrast

# Enhancement presets
BRIGHT_HIGH_CONTRAST_PARAMS = {
    'contrast': 1.15,
    'saturation': 1.0,
    'sharpness': 1.0,
    'brightness_boost': 1.0,
}

BRIGHT_LOW_CONTRAST_PARAMS = {
    'contrast': 1.25,
    'saturation': 1.15,
    'sharpness': 1.3,
    'brightness_boost': 1.05,
}

# Dark image params já existem (DARK_IMAGE_*)
```

#### Fase 2: Adicionar detect_contrast()

```python
# app/services/gif_converter.py (após detect_brightness, ~linha 240)

def detect_contrast(image: Image.Image) -> float:
    """
    Detecta nível de contraste da imagem usando desvio padrão.

    Valores típicos:
    - < 30: Muito baixo contraste (flat, washed out)
    - 30-50: Baixo contraste
    - 50-80: Contraste normal
    - > 80: Alto contraste

    Args:
        image: Imagem PIL (qualquer modo)

    Returns:
        Desvio padrão da luminosidade (0-~127 para imagens típicas)
    """
    grayscale = image.convert('L')
    stat = ImageStat.Stat(grayscale)
    return stat.stddev[0]
```

#### Fase 3: Modificar enhance_for_led_display()

```python
# app/services/gif_converter.py (substituir linhas 265-319)

def enhance_for_led_display(
    image: Image.Image,
    contrast: float = DEFAULT_CONTRAST,
    saturation: float = DEFAULT_SATURATION,
    sharpness: float = DEFAULT_SHARPNESS,
    auto_brightness: bool = True
) -> Image.Image:
    """
    Otimiza imagem para displays LED como Pixoo 64.

    Usa detecção adaptativa para escolher parâmetros:
    - Imagens escuras: gamma correction + enhancement moderado
    - Imagens claras + baixo contraste: enhancement moderado
    - Imagens claras + alto contraste: enhancement mínimo (preservar qualidade)
    """
    img = image
    brightness_boost = DEFAULT_BRIGHTNESS_BOOST

    if auto_brightness:
        brightness = detect_brightness(image)
        image_contrast = detect_contrast(image)

        if brightness < DARK_IMAGE_THRESHOLD:
            # Pipeline DARK: gamma + moderate
            img = apply_gamma_correction(img, gamma=DARK_IMAGE_GAMMA)
            contrast = DARK_IMAGE_CONTRAST
            saturation = DARK_IMAGE_SATURATION
            sharpness = 1.2  # Sharpness moderado para dark
            brightness_boost = 1.05

        elif image_contrast >= CONTRAST_HIGH_THRESHOLD:
            # Pipeline BRIGHT_HIGH_CONTRAST: minimal enhancement
            contrast = BRIGHT_HIGH_CONTRAST_PARAMS['contrast']
            saturation = BRIGHT_HIGH_CONTRAST_PARAMS['saturation']
            sharpness = BRIGHT_HIGH_CONTRAST_PARAMS['sharpness']
            brightness_boost = BRIGHT_HIGH_CONTRAST_PARAMS['brightness_boost']

        else:
            # Pipeline BRIGHT_LOW_CONTRAST: moderate enhancement
            contrast = BRIGHT_LOW_CONTRAST_PARAMS['contrast']
            saturation = BRIGHT_LOW_CONTRAST_PARAMS['saturation']
            sharpness = BRIGHT_LOW_CONTRAST_PARAMS['sharpness']
            brightness_boost = BRIGHT_LOW_CONTRAST_PARAMS['brightness_boost']

    # Aplicar enhancement na ordem correta
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = ImageEnhance.Color(img).enhance(saturation)
    img = ImageEnhance.Brightness(img).enhance(brightness_boost)
    img = ImageEnhance.Sharpness(img).enhance(sharpness)

    return img
```

## Acceptance Criteria

### Functional Requirements

- [ ] Imagens claras com alto contraste usam parâmetros suaves (1.15/1.0/1.0)
- [ ] Imagens escuras continuam usando gamma correction + parâmetros moderados
- [ ] Imagens claras com baixo contraste usam parâmetros intermediários
- [ ] GIF dos camelos (Camelos_originais.webp) fica similar ao Camel_FIRST.gif

### Non-Functional Requirements

- [ ] Detecção adiciona < 50ms ao tempo de conversão
- [ ] Código segue padrões existentes (funções puras, docstrings)
- [ ] Constantes organizadas no bloco de constantes existente

### Quality Gates

- [ ] Testes passando
- [ ] Comparação visual: novo GIF dos camelos vs Camel_FIRST.gif
- [ ] Linter sem erros

## Test Plan

### Testes Manuais

1. **Camelos (imagem clara, alto contraste)**
   - Converter Camelos_originais.webp
   - Comparar com Camel_FIRST.gif
   - Esperado: Qualidade similar, sem flickering excessivo

2. **Imagem escura**
   - Usar imagem com brightness < 0.3
   - Verificar que gamma correction é aplicado
   - Esperado: Imagem clareada adequadamente

3. **Imagem clara, baixo contraste**
   - Usar imagem washed-out/flat
   - Verificar que enhancement moderado é aplicado
   - Esperado: Melhoria de contraste sem exagero

### Testes Automatizados

```python
# tests/test_gif_converter.py

class TestAdaptiveEnhancement:
    """Testes para detecção adaptativa de enhancement."""

    def test_detect_contrast_high_contrast_image(self):
        """Imagem com bordas definidas deve ter stddev alto."""
        # Criar imagem com alto contraste (preto e branco)
        img = Image.new('RGB', (64, 64))
        # ... preencher metade preto, metade branco
        contrast = detect_contrast(img)
        assert contrast >= CONTRAST_HIGH_THRESHOLD

    def test_detect_contrast_low_contrast_image(self):
        """Imagem flat deve ter stddev baixo."""
        # Criar imagem uniforme (cinza)
        img = Image.new('RGB', (64, 64), (128, 128, 128))
        contrast = detect_contrast(img)
        assert contrast < CONTRAST_HIGH_THRESHOLD

    def test_enhance_bright_high_contrast_uses_minimal(self):
        """Imagem clara com alto contraste usa parâmetros mínimos."""
        # Criar imagem clara com alto contraste
        # Verificar que enhancement não exagera saturação
        pass

    def test_enhance_dark_image_uses_gamma(self):
        """Imagem escura aplica gamma correction."""
        # Criar imagem escura
        # Verificar que brightness aumenta após enhancement
        pass
```

## Implementation Phases

### Phase 1: Implementação Core (Estimativa: 30 min)

- [ ] Adicionar constantes (thresholds, presets)
- [ ] Implementar `detect_contrast()`
- [ ] Modificar `enhance_for_led_display()`

### Phase 2: Testes e Validação (Estimativa: 30 min)

- [ ] Escrever testes automatizados
- [ ] Testar manualmente com Camelos_originais.webp
- [ ] Comparar resultado com Camel_FIRST.gif

### Phase 3: Refinamento (Estimativa: 15 min)

- [ ] Ajustar thresholds se necessário
- [ ] Verificar outros tipos de imagem
- [ ] Atualizar documentação (CLAUDE.md se necessário)

## Dependencies & Prerequisites

- Pillow >= 10.0.0 (já instalado)
- Arquivos de teste existentes em `Melhorias/`

## Risk Analysis & Mitigation

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Threshold de contraste não generaliza | Média | Alto | Constantes fáceis de ajustar |
| Performance degradada | Baixa | Médio | detect_contrast é O(n) simples |
| Regressão em imagens escuras | Baixa | Alto | Testes específicos para dark images |

## References

### Internal References

- `app/services/gif_converter.py:225-239` - detect_brightness() existente
- `app/services/gif_converter.py:265-319` - enhance_for_led_display() atual
- `app/services/gif_converter.py:26-48` - Constantes existentes
- `Melhorias/Camel_FIRST.gif` - Referência de qualidade
- `Melhorias/experiment.py` - Script de comparação

### External References

- [Pillow ImageStat Documentation](https://pillow.readthedocs.io/en/stable/reference/ImageStat.html)
- [Pillow ImageEnhance Documentation](https://pillow.readthedocs.io/en/stable/reference/ImageEnhance.html)

### Research Findings

- Parâmetros ideais para imagem clara/alta definição: `contrast=1.15, sat=1.0, sharp=1.0`
- Threshold de brilho para "escuro": 0.3 (já existente)
- Threshold de contraste sugerido: stddev >= 50 = alto contraste

---

**Gerado com [Claude Code](https://claude.com/claude-code)**
