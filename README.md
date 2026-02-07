# Pixoo Manager

Aplicativo desktop para Mac (Apple Silicon) para gerenciar conteudo no display LED Divoom Pixoo 64.

## Download

**[Baixar Pixoo Manager v1.4.0](https://github.com/dpalis/pixoo-manager/releases/latest)**

> Requer macOS 12+ (Apple Silicon)

## Funcionalidades

### Upload e Conversao
- Upload de GIFs (converte automaticamente para 64x64)
- Conversao de fotos (PNG, JPG) para GIF animado
- Conversao de videos (MP4, MOV, WebM) com selecao de trecho
- Download de trechos do YouTube e conversao para GIF
- **Crop** - recortar area especifica antes de converter
- **Trim** - selecionar range de frames em GIFs grandes

### Galeria
- Salvar GIFs favoritos para uso futuro
- Organizar com nomes e favoritos
- Deletar em lote ou limpar tudo
- Reenviar para o Pixoo a qualquer momento

### Conexao
- Descoberta automatica do Pixoo 64 na rede (scan completo 1-254)
- Reconexao rapida ao ultimo IP usado
- Indicador de status de conexao

### Sistema
- Verificador de atualizacoes integrado
- Desinstalador completo
- Instalador DMG profissional

## Instalacao

### Opcao 1: Baixar o Instalador (Recomendado)

1. Baixe o arquivo `.dmg` da [pagina de releases](https://github.com/dpalis/pixoo-manager/releases/latest)
2. Abra o DMG e arraste o app para Aplicativos
3. Na primeira execucao, o macOS pode mostrar um aviso de seguranca (veja abaixo)

#### Aviso de Seguranca do macOS

O app nao esta assinado com um certificado Apple Developer, entao o macOS exibe um aviso na primeira execucao.

**Solucao 1 - Via Ajustes (mais facil):**
1. Tente abrir o app normalmente
2. Clique "OK" no aviso (nao mova para o lixo)
3. Va em **Ajustes do Sistema → Privacidade e Seguranca**
4. Role ate ver a mensagem sobre "Pixoo foi bloqueado"
5. Clique em **"Abrir Mesmo Assim"**

**Solucao 2 - Via Terminal (mais rapido):**
```bash
xattr -cr /Applications/Pixoo.app
```

Depois disso, o app abre normalmente sem avisos.

### Opcao 2: Rodar em desenvolvimento

```bash
# Clonar o repositorio
git clone https://github.com/dpalis/pixoo-manager.git
cd pixoo-manager

# Criar e ativar virtualenv
python3 -m venv .venv
source .venv/bin/activate

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
curl -L 'https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffmpeg.zip' -o /tmp/ffmpeg.zip
unzip -o /tmp/ffmpeg.zip -d /tmp/ffmpeg_extracted
mv /tmp/ffmpeg_extracted/ffmpeg bin/ffmpeg
chmod +x bin/ffmpeg
```

### 2. Instalar dependencias de build

```bash
brew install create-dmg expat
```

### 3. Executar build

```bash
source .venv/bin/activate
./scripts/build_dmg.sh
```

O instalador sera criado como `Pixoo-{version}.dmg`

## Uso

1. Conecte seu Pixoo 64 na mesma rede WiFi
2. Abra o Pixoo Manager
3. Clique em "Descobrir" para encontrar o dispositivo
4. Selecione o IP e conecte
5. Use as abas para:
   - **GIF**: Upload de GIFs prontos
   - **Foto/Video**: Converter imagens e videos
   - **YouTube**: Baixar trechos de videos
   - **Galeria**: Gerenciar GIFs salvos

## Limites

| Limite | Valor |
|--------|-------|
| Dimensao do display | 64x64 pixels |
| Frames maximo (upload) | 40 |
| Frames maximo (conversao) | 92 |
| Duracao maxima de video | 5 segundos |
| Tamanho maximo de arquivo | 500MB |

## Stack Tecnica

- **Backend**: FastAPI + Uvicorn
- **Frontend**: Alpine.js + Pico.css
- **Processamento**: Pillow, MoviePy, imageio
- **YouTube**: yt-dlp
- **Packaging**: py2app

## Changelog

### v1.4.0 (2025-01-05)
- Galeria de GIFs persistente
- Crop para GIFs e videos
- Trim de frames para GIFs grandes
- Verificador de atualizacoes
- Desinstalador completo
- Bulk delete na galeria
- Auto-discover melhorado (scan 1-254)
- Instalador DMG profissional
- Melhorias de conexao para redes lentas

### v1.3.0
- Versao inicial publica

## Licenca

MIT
