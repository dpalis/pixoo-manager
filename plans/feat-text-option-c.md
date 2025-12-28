# feat: Aba Texto Opção C - Múltiplas Linhas + Templates de Layout

## Resumo

Expandir a aba "Texto" para suportar múltiplas linhas simultâneas (até 20 via TextId), templates de layout com fundos visuais, e maior variedade de fontes organizadas por tamanho e tipo.

## Escopo

### Incluído
- [x] Múltiplas linhas de texto (1-20 via TextId)
- [x] Posicionamento X/Y por linha
- [x] Templates de layout pré-definidos
- [x] Fundos: cor sólida, gradiente, padrões, imagem
- [x] Fontes: separar tamanho (P/M/G) e tipo (sans/serif/pixel)
- [x] Preview canvas em tempo real
- [x] Envio ordenado (fundo → textos)

### Excluído
- Histórico de mensagens
- Persistência entre sessões
- Export/import de layouts

---

## Descobertas da Pesquisa

### API SendHttpText - Parâmetros Confirmados
```json
{
  "Command": "Draw/SendHttpText",
  "TextId": 1,           // 1-20 (até 20 textos simultâneos)
  "x": 0,                // Posição X (0-63)
  "y": 28,               // Posição Y (0-63)
  "dir": 0,              // Direção scroll (0=esquerda)
  "font": 0,             // ID da fonte (0-7 seguros)
  "TextWidth": 64,       // Largura do texto
  "TextString": "Hello", // Conteúdo
  "speed": 100,          // Velocidade scroll (10-200ms)
  "color": "#FFFFFF",    // Cor hex
  "align": 1             // Alinhamento (1=esq, 2=centro, 3=dir)
}
```

### Fontes Seguras Descobertas
| ID | Tipo | Tamanho | Notas |
|----|------|---------|-------|
| 0 | Sans | Médio | Default, mais testada |
| 2 | Sans | Pequeno | Compacta |
| 4 | Sans | Grande | Larga |
| 5 | Pixel | Pequeno | Estilo retro |
| 8 | Sans | Pequeno | Muito usada na comunidade |

**Fontes da comunidade:** PICO-8, GICKO, five_pix, eleven_pix

### Limitação Crítica
> Texto só pode sobrepor GIFs enviados via HTTP. Não funciona sobre conteúdo do SD card ou galeria.

**Implicação:** Todo layout DEVE ter um fundo (mesmo que seja GIF preto 64x64).

### Referências de Templates
- [pixoo-homeassistant](https://github.com/gickowtf/pixoo-homeassistant) - Sistema de componentes
- [pizzoo](https://github.com/pabletos/pizzoo) - Templates XML
- [Home Assistant Blueprint](https://community.home-assistant.io/t/divoom-pixoo64-send-text-4-lines/554428) - 4 linhas padrão

---

## Decisões Técnicas

### Posicionamento de Texto
**Decisão:** Usar Y absoluto (0-63) + X opcional (default 0)
- Templates definem posições pré-calculadas
- Modo livre permite ajuste manual
- Preview mostra grid 64x64 para referência

### TextId Lifecycle
**Decisão:** Limpar todos antes de enviar
1. Enviar `Draw/ClearHttpText`
2. Enviar fundo como GIF
3. Enviar cada linha com TextId sequencial (1, 2, 3...)
- Evita conflitos com estado anterior do device

### Fundo Obrigatório
**Decisão:** Sempre gerar fundo, default = preto sólido
- Cor sólida → GIF 64x64 de 1 frame
- Gradiente → GIF gerado com Pillow
- Padrão → GIF gerado programaticamente
- Imagem → Upload e conversão para 64x64

### Delay Entre Comandos
**Decisão:** 300ms após fundo, 50ms entre textos
- Total para 10 linhas: ~800ms (aceitável)
- Configurável se precisar ajustar

---

## Templates Pré-definidos

### Template 1: Relógio
```
┌────────────────┐
│                │
│    12:45       │  <- Y=20, Grande, Branco
│    Sábado      │  <- Y=40, Pequeno, Cinza
│                │
└────────────────┘
Fundo: Preto sólido
```

### Template 2: Duas Linhas
```
┌────────────────┐
│  Linha 1       │  <- Y=16, Médio, Vermelho
│                │
│  Linha 2       │  <- Y=40, Médio, Verde
└────────────────┘
Fundo: Gradiente vertical azul→preto
```

### Template 3: Recado
```
┌────────────────┐
│ ♥ ♥ ♥ ♥ ♥ ♥ ♥ │  <- Borda decorativa (imagem)
│   Feliz        │  <- Y=24, Grande, Rosa
│ Aniversário!   │  <- Y=40, Médio, Branco
│ ♥ ♥ ♥ ♥ ♥ ♥ ♥ │
└────────────────┘
Fundo: Imagem com corações
```

### Template 4: Status
```
┌────────────────┐
│ CPU: 45%       │  <- Y=8, Pixel, Verde
│ RAM: 2.1GB     │  <- Y=24, Pixel, Amarelo
│ Temp: 62°C     │  <- Y=40, Pixel, Laranja
│ Net: 12MB/s    │  <- Y=56, Pixel, Azul
└────────────────┘
Fundo: Preto com grid sutil
```

---

## Arquitetura

### Novos Arquivos

#### `app/services/layout_renderer.py`
```python
class LayoutRenderer:
    def render_background(self, config: BackgroundConfig) -> Path:
        """Gera GIF 64x64 para fundo (sólido/gradiente/padrão/imagem)"""

    def render_layout(self, template: LayoutTemplate) -> tuple[Path, list[TextLine]]:
        """Gera fundo e prepara lista de textos para envio"""
```

#### `app/services/multi_text_sender.py`
```python
class MultiTextSender:
    async def send_layout(self, background_path: Path, lines: list[TextLine]):
        """Envia layout completo: limpa → fundo → textos"""

    async def clear_all(self):
        """Limpa todos os textos do device"""
```

#### `app/routers/layout.py`
```python
# POST /api/layout/send - Envia layout completo
# POST /api/layout/preview - Gera preview (retorna base64)
# GET /api/layout/templates - Lista templates disponíveis
# POST /api/layout/clear - Limpa textos do device
```

### Arquivos a Modificar

| Arquivo | Mudanças |
|---------|----------|
| `app/main.py` | Registrar router layout |
| `app/templates/base.html` | Expandir aba Texto com UI multi-linha |
| `app/static/js/app.js` | Novo componente `layoutEditor()` |
| `app/static/css/styles.css` | Estilos para editor de layout |

---

## UI Proposta

```
┌─ Aba Texto ──────────────────────────────────────────────────┐
│                                                              │
│  📋 Templates                                                │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                        │
│  │Reló- │ │2 Li- │ │Reca- │ │Sta-  │  ← Clique aplica      │
│  │gio   │ │nhas  │ │do    │ │tus   │                        │
│  └──────┘ └──────┘ └──────┘ └──────┘                        │
│                                                              │
│  🎨 Fundo                                                    │
│  ( ) Cor sólida  [████████]                                 │
│  ( ) Gradiente   [████] → [████]  Direção: [Vertical ▼]     │
│  ( ) Padrão      [Xadrez ▼] Cores: [██] [██]                │
│  ( ) Imagem      [Escolher arquivo...]                      │
│                                                              │
│  📝 Linhas de Texto                                          │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ [↑][↓] Texto: [____________] Y:[28] Cor:[██] Fonte:[▼] ││
│  │ [↑][↓] Texto: [____________] Y:[44] Cor:[██] Fonte:[▼] ││
│  └─────────────────────────────────────────────────────────┘│
│  [+ Adicionar Linha]                                        │
│                                                              │
│  👁️ Preview                     Fonte: [Tamanho ▼][Tipo ▼]  │
│  ┌────────────────────┐                                     │
│  │                    │        Tamanho: Pequeno/Médio/Grande│
│  │   Preview 64x64    │        Tipo: Sans/Serif/Pixel       │
│  │   (canvas 320x320) │                                     │
│  │                    │                                     │
│  └────────────────────┘                                     │
│                                                              │
│  [Limpar Textos]                              [📤 Enviar]   │
└──────────────────────────────────────────────────────────────┘
```

---

## Fases de Implementação

### Fase 1: Multi-texto Básico
- [ ] Expandir `text_sender.py` para múltiplos TextIds
- [ ] UI para adicionar/remover linhas
- [ ] Posição Y por linha
- [ ] Envio sequencial com delays
- [ ] Clear all textos

### Fase 2: Fundos Visuais
- [ ] Criar `layout_renderer.py`
- [ ] Gerar GIF para cor sólida
- [ ] Gerar GIF para gradiente (2 cores, vertical/horizontal)
- [ ] Gerar GIF para padrões (xadrez, listras, pontos)
- [ ] Upload de imagem como fundo

### Fase 3: Templates
- [ ] Definir schema JSON para templates
- [ ] Criar 4-6 templates iniciais
- [ ] UI para seleção de template
- [ ] Aplicar template preenche form

### Fase 4: Fontes Avançadas
- [ ] Mapear fontes por tamanho e tipo
- [ ] Dropdown separado: Tamanho + Tipo
- [ ] Testar combinações no device
- [ ] Documentar quais funcionam

### Fase 5: Preview Avançado
- [ ] Canvas com animação de scroll
- [ ] Múltiplas linhas renderizadas
- [ ] Fundo renderizado (gradientes, padrões)
- [ ] Grid 64x64 para referência

---

## Modelos Pydantic

```python
class TextLine(BaseModel):
    text: str = Field(..., max_length=100)
    x: int = Field(default=0, ge=0, le=63)
    y: int = Field(..., ge=0, le=63)
    color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    font_size: Literal["small", "medium", "large"] = "medium"
    font_type: Literal["sans", "serif", "pixel"] = "sans"
    speed: int = Field(default=100, ge=10, le=200)

class BackgroundConfig(BaseModel):
    type: Literal["solid", "gradient", "pattern", "image"] = "solid"
    color: str = "#000000"
    gradient_start: str = "#000000"
    gradient_end: str = "#333333"
    gradient_direction: Literal["vertical", "horizontal"] = "vertical"
    pattern_type: Literal["checkerboard", "stripes", "dots"] = "checkerboard"
    pattern_color1: str = "#000000"
    pattern_color2: str = "#1a1a2e"
    image_path: Optional[str] = None

class LayoutTemplate(BaseModel):
    name: str
    lines: List[TextLine] = Field(max_length=20)
    background: BackgroundConfig
```

---

## Sequência de Envio

```
1. POST /api/layout/send
   ↓
2. Gerar GIF do fundo (64x64)
   ↓
3. Enviar Draw/ClearHttpText
   ↓
4. Enviar Draw/SendHttpGif (fundo)
   ↓ (aguardar 300ms)
5. Para cada linha (1..N):
   └─ Enviar Draw/SendHttpText (TextId=i)
      ↓ (aguardar 50ms)
6. Retornar sucesso
```

---

## Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Fonte crashar device | Média | Alto | Whitelist IDs 0, 2, 4, 5, 8 |
| Delays insuficientes | Média | Médio | Configurável, começar conservador |
| Preview ≠ Device | Alta | Baixo | Disclaimer + usar fontes aproximadas |
| Muitas linhas ilegíveis | Alta | Médio | Warning UI se >8 linhas |
| Gradiente não renderiza | Baixa | Médio | Fallback para cor sólida |

---

## Checklist de Testes

### Funcional
- [ ] 1 linha com fundo preto envia OK
- [ ] 10 linhas com gradiente envia OK
- [ ] 20 linhas (máximo) envia OK
- [ ] Limpar remove todas as linhas
- [ ] Template aplica corretamente
- [ ] Posição Y funciona (0, 32, 63)
- [ ] Cores diferentes funcionam
- [ ] Cada tipo de fundo funciona

### Edge Cases
- [ ] Texto vazio → pula linha
- [ ] Texto muito longo → trunca ou scroll
- [ ] Y fora do range → clamp
- [ ] Sem conexão → botão desabilitado
- [ ] Falha no meio → mostra erro

### Performance
- [ ] Preview atualiza sem lag
- [ ] Envio de 20 linhas < 3s
- [ ] Canvas não vaza memória

---

## Referências

### Projetos
- [pixoo-homeassistant](https://github.com/gickowtf/pixoo-homeassistant) - Melhor sistema de templates
- [pizzoo](https://github.com/pabletos/pizzoo) - Templates XML
- [font8x8](https://github.com/dhepper/font8x8) - Fontes bitmap para canvas

### Documentação
- [Divoom API](http://doc.divoom-gz.com/web/#/12?page_id=196)
- [Grayda Notes](https://github.com/Grayda/pixoo_api/blob/main/NOTES.md)
- [MDN Canvas Text](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API/Tutorial/Drawing_text)

### Arquivos do Projeto
- `app/services/text_sender.py` - Base para expansão
- `app/services/pixoo_upload.py:166` - Padrão upload_single_frame
- `app/static/js/app.js:1564` - Componente textDisplay() atual
- `plans/feat-text-messages.md` - Plano Opção B (base)
