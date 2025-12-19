# Pixoo Manager

Aplicativo desktop para Mac (Apple Silicon) para gerenciar conteudo no display LED Divoom Pixoo 64.

## Funcionalidades

- Descoberta automatica do Pixoo 64 na rede local
- Upload de GIFs (converte automaticamente para 64x64)
- Conversao de fotos (PNG, JPG) para GIF animado
- Conversao de videos (MP4, MOV, WebM) com selecao de trecho
- Download de trechos do YouTube e conversao para GIF
- Preview antes de enviar
- Envio para Pixoo 64 via HTTP API local

## Instalacao

### Opcao 1: Baixar o App pronto

1. Baixe `Pixoo.app` da secao Releases
2. Mova para a pasta Aplicativos
3. Abra o app (pode precisar aprovar em Ajustes do Sistema > Privacidade e Seguranca)

### Opcao 2: Rodar em desenvolvimento

```bash
# Clonar o repositorio
git clone https://github.com/dpalis/pixoo-manager.git
cd pixoo-manager

# Criar e ativar virtualenv
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Rodar
python -m app.main
```

O app abrira automaticamente no browser em http://127.0.0.1:8000

## Build do App (.app)

Para criar o `Pixoo.app`:

### 1. Baixar FFmpeg (Apple Silicon)

```bash
mkdir -p bin
curl -L 'https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip' -o /tmp/ffmpeg.zip
unzip -o /tmp/ffmpeg.zip -d /tmp/ffmpeg_extracted
mv /tmp/ffmpeg_extracted/ffmpeg bin/ffmpeg
chmod +x bin/ffmpeg
```

### 2. Executar build

```bash
# Ativar virtualenv
source .venv/bin/activate

# Build com py2app
python setup.py py2app
```

O app sera criado em `dist/Pixoo.app` (~400MB)

## Uso

1. Conecte seu Pixoo 64 na mesma rede WiFi
2. Abra o Pixoo Manager
3. Clique em "Descobrir" para encontrar o dispositivo
4. Selecione o IP e conecte
5. Use as abas para:
   - **GIF**: Upload de GIFs prontos
   - **Foto/Video**: Converter imagens e videos
   - **YouTube**: Baixar trechos de videos

## Limites

| Limite | Valor |
|--------|-------|
| Dimensao do display | 64x64 pixels |
| Frames maximo (upload) | 40 |
| Frames maximo (conversao) | 92 |
| Duracao maxima de video | 10 segundos |
| Tamanho maximo de arquivo | 500MB |

## Stack Tecnica

- **Backend**: FastAPI + Uvicorn
- **Frontend**: Alpine.js + Pico.css
- **Processamento**: Pillow, MoviePy, imageio
- **YouTube**: yt-dlp
- **Packaging**: py2app

## Licenca

MIT
