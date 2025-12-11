# Especificações do Pixoo 64 para Criação de GIFs

## Resolução
- **64×64 pixels** (obrigatório)
- Display com 4.096 LEDs individuais

## Limites de Animação
- **Máximo de 92 frames** por animação
- Duração de frames é global (tempos individuais são ignorados)

## Formatos Aceitos
- **GIF** - formato principal
- **MP4** - convertido pelo app

## Estrutura Técnica
- Dados de pixel em formato **RGB**
- Para 64x64: 12.288 elementos por frame (64×64×3)
- Animações começam com hex `1A` + número de frames
- Imagens estáticas 64x64 começam com hex `11 04`

## Cartão de Memória
- Cartão TF/microSD mínimo: **512MB**
- Formato: **FAT**

## Checklist para Criação
- [ ] Resolução exata: 64×64 pixels
- [ ] Máximo 92 frames
- [ ] Exportar como GIF
- [ ] Cores RGB (sem transparência complexa)

## Fontes
- https://divoom.com/products/pixoo-64
- https://github.com/Grayda/pixoo_api/blob/main/NOTES.md
- https://pypi.org/project/APIxoo/
