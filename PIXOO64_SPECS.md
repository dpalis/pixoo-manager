# Especificações do Pixoo 64

## Resolução
- **64×64 pixels** (obrigatório)
- Display com 4.096 LEDs RGB individuais

## Limites de Animação

| Operação | Limite | Notas |
|----------|--------|-------|
| Upload via API | **40 frames** | Limite do endpoint SendHttpGif |
| Conversão interna | **92 frames** | Limite do hardware |
| Duração de vídeo | **5 segundos** | ~40 frames a 8 FPS |

- Duração de frames é global (tempos individuais por frame são ignorados)
- GIFs com >40 frames precisam ser recortados antes do upload

## Formatos Aceitos
- **GIF** - formato principal
- **PNG/JPG** - convertidos para GIF pelo app
- **MP4/MOV/WebM** - convertidos pelo app

## Estrutura Técnica
- Dados de pixel em formato **RGB**
- Para 64x64: 12.288 bytes por frame (64×64×3)
- Animações começam com hex `1A` + número de frames
- Imagens estáticas 64x64 começam com hex `11 04`

## API HTTP
- Endpoint: `http://{ip}:80/post`
- Comando principal: `SendHttpGif`
- Formato: JSON com frames em Base64

## Cartão de Memória
- Cartão TF/microSD mínimo: **512MB**
- Formato: **FAT**

## Checklist para Criação de GIFs
- [ ] Resolução exata: 64×64 pixels
- [ ] Máximo 40 frames (para upload via API)
- [ ] Exportar como GIF
- [ ] Cores RGB (transparência convertida para preto)

## Fontes
- https://divoom.com/products/pixoo-64
- https://doc.divoom-gz.com/web/#/12?page_id=89
- https://github.com/Grayda/pixoo_api/blob/main/NOTES.md
