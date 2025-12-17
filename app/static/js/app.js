/**
 * Pixoo Manager - JavaScript
 * Componentes Alpine.js para interatividade
 */

// ============================================
// Heartbeat - Keep server alive while browser is open
// ============================================
async function sendHeartbeat() {
    try {
        await fetch('/api/heartbeat', { method: 'POST' });
    } catch {
        // Silently ignore errors
    }
}

setInterval(sendHeartbeat, 15000);
sendHeartbeat();

document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') sendHeartbeat();
});

// ============================================
// Session-based State Management
// ============================================
(function() {
    const serverSessionId = document.querySelector('meta[name="server-session-id"]')?.content;
    const storedSessionId = sessionStorage.getItem('serverSessionId');

    // Se session ID mudou (servidor reiniciou), limpar todo o estado
    if (serverSessionId && serverSessionId !== storedSessionId) {
        sessionStorage.removeItem('mediaUpload');
        sessionStorage.removeItem('youtubeDownload');
        sessionStorage.setItem('serverSessionId', serverSessionId);
    }

    // Também limpar em F5 (reload)
    const navEntries = performance.getEntriesByType('navigation');
    if (navEntries.length > 0 && navEntries[0].type === 'reload') {
        sessionStorage.removeItem('mediaUpload');
        sessionStorage.removeItem('youtubeDownload');
    }
})();

// ============================================
// Utility Functions (Shared)
// ============================================
const utils = {
    /**
     * Formata tempo em segundos para MM:SS.ms
     */
    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = (seconds % 60).toFixed(2);
        return `${mins.toString().padStart(2, '0')}:${secs.padStart(5, '0')}`;
    },

    /**
     * Formata duração em segundos para MM:SS
     */
    formatDuration(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    },

    /**
     * Parse string de tempo para segundos
     * Formato: MM:SS.ms ou SS.ms ou SS
     */
    parseTimeStr(str) {
        const match = str.match(/^(?:(\d+):)?(\d+(?:\.\d+)?)$/);
        if (!match) return null;
        const mins = parseInt(match[1] || '0');
        const secs = parseFloat(match[2]);
        return mins * 60 + secs;
    },

    /**
     * Formata tamanho de arquivo em bytes para string legivel
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    /**
     * Mostra mensagem em um componente
     */
    showMessage(component, text, type) {
        component.message = text;
        component.messageType = type;
    },

    /**
     * Limpa mensagem de um componente
     */
    clearMessage(component) {
        component.message = '';
        component.messageType = '';
    }
};

// ============================================
// Time Management Mixin (shared between mediaUpload and youtubeDownload)
// ============================================
const timeManagementMixin = {
    updateStartTime() {
        this.startTime = parseFloat(this.startTime);
        if (this.startTime >= this.endTime) {
            this.startTime = Math.max(0, this.endTime - 0.1);
        }
        this.startTimeStr = utils.formatTime(this.startTime);
        if (this.seekToTime) this.seekToTime(this.startTime);
    },

    updateEndTime() {
        this.endTime = parseFloat(this.endTime);
        const maxDuration = this.getMaxDuration();
        if (this.endTime <= this.startTime) {
            this.endTime = Math.min(maxDuration, this.startTime + 0.1);
        }
        this.endTimeStr = utils.formatTime(this.endTime);
        if (this.seekToTime) this.seekToTime(this.endTime);
    },

    parseStartTime() {
        const seconds = utils.parseTimeStr(this.startTimeStr);
        if (seconds !== null && this.getMaxDuration() > 0) {
            this.startTime = Math.max(0, Math.min(seconds, this.endTime - 0.1));
            this.startTimeStr = utils.formatTime(this.startTime);
            if (this.seekToTime) this.seekToTime(this.startTime);
        }
    },

    parseEndTime() {
        const seconds = utils.parseTimeStr(this.endTimeStr);
        const maxDuration = this.getMaxDuration();
        if (seconds !== null && maxDuration > 0) {
            this.endTime = Math.max(this.startTime + 0.1, Math.min(seconds, maxDuration));
            this.endTimeStr = utils.formatTime(this.endTime);
            if (this.seekToTime) this.seekToTime(this.endTime);
        }
    }
};

// ============================================
// Connection Status Component
// ============================================
function connectionStatus() {
    return {
        connected: false,
        loading: false,
        currentIp: null,
        showManualIp: false,
        manualIp: '',

        get statusText() {
            if (this.loading) return 'Conectando...';
            if (this.connected) return `Conectado a ${this.currentIp}`;
            return 'Desconectado';
        },

        async init() {
            // Verificar status inicial
            await this.checkStatus();
        },

        async checkStatus() {
            try {
                const response = await fetch('/api/status');
                if (response.ok) {
                    const data = await response.json();
                    this.connected = data.connected;
                    this.currentIp = data.ip;
                }
            } catch (e) {
                console.error('Erro ao verificar status:', e);
            }
        },

        async toggleConnection() {
            if (this.connected) {
                await this.disconnect();
            } else {
                await this.discover();
            }
        },

        async discover() {
            this.loading = true;
            try {
                const response = await fetch('/api/discover', { method: 'POST' });
                const data = await response.json();

                if (data.devices && data.devices.length > 0) {
                    // Conectar automaticamente ao primeiro dispositivo
                    await this.connect(data.devices[0]);
                } else {
                    // Mostrar campo para IP manual
                    this.showManualIp = true;
                }
            } catch (e) {
                console.error('Erro ao descobrir dispositivos:', e);
                this.showManualIp = true;
            } finally {
                this.loading = false;
            }
        },

        async connect(ip) {
            this.loading = true;
            try {
                const response = await fetch('/api/connect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ip })
                });

                if (response.ok) {
                    const data = await response.json();
                    this.connected = true;
                    this.currentIp = ip;
                    this.showManualIp = false;
                } else {
                    const error = await response.json();
                    alert(error.detail || 'Falha ao conectar');
                }
            } catch (e) {
                console.error('Erro ao conectar:', e);
                alert('Erro ao conectar com o Pixoo');
            } finally {
                this.loading = false;
            }
        },

        async connectManual() {
            if (this.manualIp) {
                await this.connect(this.manualIp);
            }
        },

        async disconnect() {
            this.loading = true;
            try {
                await fetch('/api/disconnect', { method: 'POST' });
                this.connected = false;
                this.currentIp = null;
            } catch (e) {
                console.error('Erro ao desconectar:', e);
            } finally {
                this.loading = false;
            }
        }
    };
}

// ============================================
// GIF Upload Component
// ============================================
function gifUpload() {
    return {
        dragOver: false,
        file: null,
        previewUrl: null,
        fileName: '',
        fileInfo: '',
        message: '',
        messageType: '',
        uploadId: null,

        get canSend() {
            // Por enquanto, apenas verifica se tem arquivo
            // Na Fase 2, vai verificar também se está conectado
            return this.uploadId !== null;
        },

        getDisplayPreviewUrl() {
            // Retorna URL escalada para melhor visualização
            if (this.uploadId && this.previewUrl) {
                return `${this.previewUrl}/scaled`;
            }
            return this.previewUrl;
        },

        handleDrop(event) {
            this.dragOver = false;
            const files = event.dataTransfer.files;
            if (files.length > 0) {
                this.processFile(files[0]);
            }
        },

        handleFileSelect(event) {
            const files = event.target.files;
            if (files.length > 0) {
                this.processFile(files[0]);
            }
        },

        async processFile(file) {
            // Validar tipo
            const allowedTypes = ['image/gif', 'image/png', 'image/jpeg', 'image/webp'];
            if (!allowedTypes.includes(file.type)) {
                this.showMessage('Por favor, selecione um GIF ou imagem (PNG, JPEG, WebP)', 'error');
                return;
            }

            this.file = file;
            this.fileName = file.name;

            // Criar preview local
            this.previewUrl = URL.createObjectURL(file);

            // Enviar para o servidor para processamento
            await this.uploadForPreview();
        },

        async uploadForPreview() {
            const formData = new FormData();
            formData.append('file', this.file);

            try {
                this.showMessage('Processando...', 'info');

                const response = await fetch('/api/gif/upload', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    this.uploadId = data.id;
                    this.fileInfo = `${data.width}x${data.height} - ${data.frames} frames`;

                    // Atualizar preview com versao processada
                    if (data.preview_url) {
                        this.previewUrl = data.preview_url;
                    }

                    this.clearMessage();
                } else {
                    const error = await response.json();
                    this.showMessage(error.detail || 'Erro ao processar GIF', 'error');
                }
            } catch (e) {
                console.error('Erro no upload:', e);
                this.showMessage('Erro ao enviar arquivo', 'error');
            }
        },

        async sendToPixoo() {
            if (!this.uploadId) return;

            try {
                this.showMessage('Enviando para Pixoo...', 'info');

                const response = await fetch('/api/gif/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: this.uploadId })
                });

                if (response.ok) {
                    this.showMessage('GIF enviado com sucesso!', 'success');
                } else {
                    const error = await response.json();
                    this.showMessage(error.detail || 'Erro ao enviar para Pixoo', 'error');
                }
            } catch (e) {
                console.error('Erro ao enviar:', e);
                this.showMessage('Erro ao enviar para Pixoo', 'error');
            }
        },

        clearFile() {
            if (this.previewUrl) {
                URL.revokeObjectURL(this.previewUrl);
            }
            this.file = null;
            this.previewUrl = null;
            this.fileName = '';
            this.fileInfo = '';
            this.uploadId = null;
            this.clearMessage();
        },

        showMessage(text, type) {
            utils.showMessage(this, text, type);
        },

        clearMessage() {
            utils.clearMessage(this);
        }
    };
}

// ============================================
// Media Upload Component (Foto/Video)
// ============================================
function mediaUpload() {
    return {
        ...timeManagementMixin,
        dragOver: false,
        file: null,
        uploadId: null,
        mediaType: null, // 'image', 'video' ou 'gif'
        fileName: '',
        fileInfo: '',
        previewUrl: null,
        videoUrl: null,
        videoDuration: 0,
        startTime: 0,
        endTime: 10,
        startTimeStr: '00:00.00',
        endTimeStr: '00:10.00',
        converting: false,
        convertProgress: 0,
        convertPhase: '',
        converted: false,
        convertedPreviewUrl: null,
        convertedFrames: 0,
        sending: false,
        message: '',
        messageType: '',
        // Crop state (para imagens)
        originalImageUrl: null,
        cropper: null,
        cropApplied: false,
        cropApplying: false,

        async init() {
            await this.restoreState();
            // Auto-save state when key properties change
            this.$watch('uploadId', () => this.saveState());
            this.$watch('previewUrl', () => this.saveState());
            this.$watch('converted', () => this.saveState());
            this.$watch('convertedPreviewUrl', () => this.saveState());
        },

        saveState() {
            const state = {
                uploadId: this.uploadId,
                mediaType: this.mediaType,
                fileName: this.fileName,
                fileInfo: this.fileInfo,
                previewUrl: this.previewUrl,
                videoDuration: this.videoDuration,
                startTime: this.startTime,
                endTime: this.endTime,
                startTimeStr: this.startTimeStr,
                endTimeStr: this.endTimeStr,
                converted: this.converted,
                convertedPreviewUrl: this.convertedPreviewUrl,
                convertedFrames: this.convertedFrames,
                cropApplied: this.cropApplied
                // Não salvar: file (File object), videoUrl (blob URL), cropper, originalImageUrl
            };
            sessionStorage.setItem('mediaUpload', JSON.stringify(state));
        },

        async restoreState() {
            // State is always cleared on page load (see top of file)
            // This function now only validates any remaining state
            const saved = sessionStorage.getItem('mediaUpload');
            if (!saved) return;

            try {
                const state = JSON.parse(saved);

                // Validar com servidor se há uploadId
                if (state.uploadId) {
                    const endpoint = state.mediaType === 'gif'
                        ? `/api/gif/preview/${state.uploadId}`
                        : `/api/media/preview/${state.uploadId}`;

                    const response = await fetch(endpoint, { method: 'HEAD' });
                    if (!response.ok) {
                        // Upload expirou no servidor
                        console.log('Upload expirado, limpando estado local');
                        sessionStorage.removeItem('mediaUpload');
                        return;
                    }
                }

                Object.assign(this, state);
            } catch (e) {
                console.error('Erro ao restaurar estado:', e);
                sessionStorage.removeItem('mediaUpload');
            }
        },

        get hasFile() {
            return this.uploadId !== null;
        },

        get segmentDuration() {
            return Math.max(0, this.endTime - this.startTime);
        },

        get segmentTooLong() {
            // Arredonda para 1 casa decimal para evitar erros de ponto flutuante
            const rounded = Math.round(this.segmentDuration * 10) / 10;
            return rounded > 10;
        },

        get canSend() {
            return (this.mediaType === 'gif' && this.uploadId) ||
                   (this.mediaType === 'image' && this.uploadId) ||
                   (this.mediaType === 'video' && this.converted);
        },

        handleDrop(event) {
            this.dragOver = false;
            const files = event.dataTransfer.files;
            if (files.length > 0) {
                // Se ja tem arquivo carregado, limpar antes de processar novo
                if (this.hasFile || this.originalImageUrl) {
                    this.clearFile();
                }
                this.processFile(files[0]);
            }
        },

        handleFileSelect(event) {
            const files = event.target.files;
            if (files.length > 0) {
                this.processFile(files[0]);
            }
        },

        async processFile(file) {
            const gifTypes = ['image/gif'];
            const imageTypes = ['image/png', 'image/jpeg', 'image/webp'];
            const videoTypes = ['video/mp4', 'video/quicktime', 'video/webm'];

            const isGif = gifTypes.includes(file.type);
            const isImage = imageTypes.includes(file.type);
            const isVideo = videoTypes.includes(file.type);

            if (!isGif && !isImage && !isVideo) {
                this.showMessage('Formato não suportado. Use GIF, PNG, JPEG, WebP, MP4, MOV ou WebM.', 'error');
                return;
            }

            this.file = file;
            this.fileName = file.name;

            // Imagens mostram cropper primeiro (não fazem upload imediato)
            if (isImage) {
                this.mediaType = 'image';
                this.originalImageUrl = URL.createObjectURL(file);
                this.cropApplied = false;
                this.fileInfo = file.name;
                this.clearMessage();

                // Inicializar cropper após render
                this.$nextTick(() => {
                    this.initCropper();
                });
                return;
            }

            // GIFs e videos fazem upload direto
            const formData = new FormData();
            formData.append('file', file);

            try {
                this.showMessage('Enviando arquivo...', 'info');

                // GIFs usam endpoint dedicado, outros usam /api/media
                const endpoint = isGif ? '/api/gif/upload' : '/api/media/upload';
                const response = await fetch(endpoint, {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const error = await response.json();
                    this.showMessage(error.detail || 'Erro no upload', 'error');
                    return;
                }

                const data = await response.json();
                this.uploadId = data.id;

                if (isGif) {
                    this.mediaType = 'gif';
                    this.previewUrl = data.preview_url;
                    this.fileInfo = `${data.width}x${data.height} - ${data.frames} frames`;
                    this.converted = true;
                    this.clearMessage();
                } else {
                    // Video
                    this.mediaType = 'video';
                    this.videoUrl = URL.createObjectURL(file);
                    this.videoDuration = data.duration;
                    this.endTime = Math.min(10, data.duration);
                    this.endTimeStr = utils.formatTime(this.endTime);
                    this.fileInfo = `${data.width}x${data.height} - ${data.duration.toFixed(1)}s`;
                    this.clearMessage();
                }

            } catch (e) {
                console.error('Erro no upload:', e);
                this.showMessage('Erro ao enviar arquivo', 'error');
            }
        },

        initCropper() {
            const image = this.$refs.cropImage;
            if (!image || this.cropper) return;

            // Debounce para evitar atualizações excessivas do preview (60fps -> ~15fps)
            let debounceTimer = null;
            const debouncedUpdate = () => {
                if (debounceTimer) clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => this.updateCropPreview(), 66);
            };

            this.cropper = new Cropper(image, {
                aspectRatio: 1,
                viewMode: 1,
                autoCropArea: 0.8,
                responsive: true,
                crop: debouncedUpdate
            });
        },

        updateCropPreview() {
            if (!this.cropper) return;

            const canvas = this.$refs.cropPreviewCanvas;
            if (!canvas) return;

            const ctx = canvas.getContext('2d');
            const croppedCanvas = this.cropper.getCroppedCanvas({
                width: 64,
                height: 64
            });

            if (croppedCanvas) {
                ctx.clearRect(0, 0, 64, 64);
                ctx.drawImage(croppedCanvas, 0, 0, 64, 64);
            }
        },

        async applyCrop() {
            if (!this.cropper || this.cropApplying) return;

            this.cropApplying = true;
            this.showMessage('Processando recorte...', 'info');

            try {
                // Obter canvas com o recorte em resolução original
                // O servidor fará o redimensionamento para 64x64 com Pillow (melhor qualidade)
                const canvas = this.cropper.getCroppedCanvas();

                // Converter para blob
                const blob = await new Promise(resolve => {
                    canvas.toBlob(resolve, 'image/png');
                });

                // Upload do recorte
                const formData = new FormData();
                formData.append('file', blob, 'cropped.png');

                const response = await fetch('/api/media/upload', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const error = await response.json();
                    this.showMessage(error.detail || 'Erro no upload', 'error');
                    return;
                }

                const data = await response.json();
                this.uploadId = data.id;
                this.previewUrl = data.preview_url;
                this.fileInfo = `${data.width}x${data.height}`;
                this.converted = true;
                this.cropApplied = true;

                // Destruir cropper
                if (this.cropper) {
                    this.cropper.destroy();
                    this.cropper = null;
                }

                this.showMessage('Recorte aplicado!', 'success');

            } catch (e) {
                console.error('Erro ao aplicar recorte:', e);
                this.showMessage('Erro ao processar recorte', 'error');
            } finally {
                this.cropApplying = false;
            }
        },

        onVideoLoaded() {
            const video = this.$refs.videoPlayer;
            if (video) {
                this.videoDuration = video.duration;
                this.endTime = Math.min(10, video.duration);
                this.endTimeStr = utils.formatTime(this.endTime);
            }
        },

        onTimeUpdate() {
            // Opcional: atualizar UI durante reproducao
        },

        // Time management mixin delegates
        getMaxDuration() {
            return this.videoDuration;
        },

        seekToTime(time) {
            if (this.$refs.videoPlayer && this.$refs.videoPlayer.readyState >= 2) {
                this.$refs.videoPlayer.currentTime = time;
            }
        },

        async convertVideo() {
            if (!this.uploadId || this.segmentTooLong) return;

            this.converting = true;
            this.convertProgress = 0;
            this.convertPhase = 'Iniciando...';

            try {
                // Usar endpoint sincrono por simplicidade
                const response = await fetch('/api/media/convert-sync', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id: this.uploadId,
                        start: this.startTime,
                        end: this.endTime
                    })
                });

                if (!response.ok) {
                    const error = await response.json();
                    this.showMessage(error.detail || 'Erro na conversao', 'error');
                    return;
                }

                const data = await response.json();
                this.converted = true;
                this.convertedPreviewUrl = data.preview_url;
                this.convertedFrames = data.frames;
                this.showMessage(`Convertido! ${data.frames} frames`, 'success');

            } catch (e) {
                console.error('Erro na conversao:', e);
                this.showMessage('Erro ao converter video', 'error');
            } finally {
                this.converting = false;
            }
        },

        async sendToPixoo() {
            if (!this.canSend) return;

            this.sending = true;
            try {
                this.showMessage('Enviando para Pixoo...', 'info');

                // GIFs usam endpoint dedicado
                const endpoint = this.mediaType === 'gif' ? '/api/gif/send' : '/api/media/send';
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: this.uploadId })
                });

                if (response.ok) {
                    const data = await response.json();
                    this.showMessage(`Enviado! ${data.frames_sent} frames`, 'success');
                } else {
                    const error = await response.json();
                    this.showMessage(error.detail || 'Erro ao enviar', 'error');
                }
            } catch (e) {
                console.error('Erro ao enviar:', e);
                this.showMessage('Erro ao enviar para Pixoo', 'error');
            } finally {
                this.sending = false;
            }
        },

        downloadGif() {
            if (!this.uploadId || !this.converted) return;

            // GIFs usam endpoint dedicado
            const endpoint = this.mediaType === 'gif'
                ? `/api/gif/download/${this.uploadId}`
                : `/api/media/download/${this.uploadId}`;

            const a = document.createElement('a');
            a.href = endpoint;
            a.download = `pixoo_${this.uploadId}.gif`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        },

        clearFile() {
            // Limpar blob URLs
            if (this.videoUrl) {
                URL.revokeObjectURL(this.videoUrl);
            }
            if (this.originalImageUrl) {
                URL.revokeObjectURL(this.originalImageUrl);
            }

            // Limpar cropper
            if (this.cropper) {
                this.cropper.destroy();
                this.cropper = null;
            }

            // Reset estado
            this.file = null;
            this.uploadId = null;
            this.mediaType = null;
            this.fileName = '';
            this.fileInfo = '';
            this.previewUrl = null;
            this.videoUrl = null;
            this.videoDuration = 0;
            this.startTime = 0;
            this.endTime = 10;
            this.startTimeStr = '00:00.00';
            this.endTimeStr = '00:10.00';
            this.converting = false;
            this.converted = false;
            this.convertedPreviewUrl = null;
            this.convertedFrames = 0;

            // Reset estado do crop
            this.originalImageUrl = null;
            this.cropApplied = false;
            this.cropApplying = false;

            this.clearMessage();
            sessionStorage.removeItem('mediaUpload');
        },

        showMessage(text, type) {
            utils.showMessage(this, text, type);
        },

        clearMessage() {
            utils.clearMessage(this);
        }
    };
}

// ============================================
// YouTube Download Component
// ============================================
function youtubeDownload() {
    return {
        ...timeManagementMixin,
        url: '',
        loading: false,
        videoInfo: null,
        startTime: 0,
        endTime: 10,
        startTimeStr: '00:00.00',
        endTimeStr: '00:10.00',
        downloading: false,
        downloadProgress: 0,
        downloadPhase: '',
        downloadId: null,
        previewUrl: null,
        convertedFrames: 0,
        sending: false,
        message: '',
        messageType: '',
        // YouTube player state
        player: null,
        playerReady: false,
        playerError: false,
        playerTimeout: null,
        playerId: 0,  // Unique ID for each player instance

        async init() {
            await this.restoreState();
            // Auto-save state when key properties change
            this.$watch('downloadId', () => this.saveState());
            this.$watch('previewUrl', () => this.saveState());
            this.$watch('videoInfo', () => this.saveState());
        },

        saveState() {
            const state = {
                url: this.url,
                videoInfo: this.videoInfo,
                startTime: this.startTime,
                endTime: this.endTime,
                startTimeStr: this.startTimeStr,
                endTimeStr: this.endTimeStr,
                downloadId: this.downloadId,
                previewUrl: this.previewUrl,
                convertedFrames: this.convertedFrames
            };
            sessionStorage.setItem('youtubeDownload', JSON.stringify(state));
        },

        async restoreState() {
            // State is always cleared on page load (see top of file)
            // This function now only validates any remaining state
            const saved = sessionStorage.getItem('youtubeDownload');
            if (!saved) return;

            try {
                const state = JSON.parse(saved);

                // Validar com servidor se há downloadId
                if (state.downloadId) {
                    const response = await fetch(`/api/youtube/preview/${state.downloadId}`, { method: 'HEAD' });
                    if (!response.ok) {
                        // Download expirou no servidor
                        console.log('Download expirado, limpando estado local');
                        sessionStorage.removeItem('youtubeDownload');
                        return;
                    }
                }

                Object.assign(this, state);
            } catch (e) {
                console.error('Erro ao restaurar estado:', e);
                sessionStorage.removeItem('youtubeDownload');
            }
        },

        get segmentDuration() {
            return Math.max(0, this.endTime - this.startTime);
        },

        get maxDuration() {
            // Shorts permitem ate 60s, videos normais ate 10s
            return this.videoInfo?.max_duration || 10;
        },

        get segmentTooLong() {
            // Arredonda para 1 casa decimal para evitar erros de ponto flutuante
            const rounded = Math.round(this.segmentDuration * 10) / 10;
            return rounded > this.maxDuration;
        },

        formatDuration(seconds) {
            return utils.formatDuration(seconds);
        },

        async fetchInfo() {
            if (!this.url) return;

            this.loading = true;
            this.clearMessage();

            try {
                const response = await fetch('/api/youtube/info', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: this.url })
                });

                if (!response.ok) {
                    const error = await response.json();
                    this.showMessage(error.detail || 'Erro ao buscar video', 'error');
                    return;
                }

                this.videoInfo = await response.json();
                // Usar max_duration do backend (60s para Shorts, 10s para videos normais)
                this.endTime = Math.min(this.videoInfo.max_duration, this.videoInfo.duration);
                this.endTimeStr = utils.formatTime(this.endTime);

                // Initialize YouTube player for preview
                // Use $nextTick to wait for Alpine to render the player container
                const videoId = this.extractVideoId(this.url);
                if (videoId) {
                    this.$nextTick(() => {
                        this.initPlayer(videoId);
                    });
                }

            } catch (e) {
                console.error('Erro:', e);
                this.showMessage('Erro ao buscar video', 'error');
            } finally {
                this.loading = false;
            }
        },

        // Extract video ID from YouTube URL
        extractVideoId(url) {
            const patterns = [
                /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)([^&?/]+)/,
            ];
            for (const pattern of patterns) {
                const match = url.match(pattern);
                if (match) return match[1];
            }
            return null;
        },

        // Time management mixin delegate
        getMaxDuration() {
            return this.videoInfo?.duration || 0;
        },

        // YouTube Player - seek to time for slider preview
        seekToTime(time) {
            if (this.player && this.playerReady) {
                this.player.seekTo(time, true);
                this.player.pauseVideo();
            }
        },

        // Initialize YouTube embedded player
        async initPlayer(videoId) {
            // Destroy any existing player first
            this.destroyPlayer();

            // Find wrapper and create fresh target element with unique ID
            const wrapper = document.querySelector('.youtube-player-wrapper');
            if (!wrapper) {
                console.warn('YouTube player wrapper not found');
                this.playerError = true;
                return;
            }

            // Clear wrapper and create new target with unique ID
            wrapper.innerHTML = '';
            this.playerId++;
            const targetId = `youtube-player-${this.playerId}`;
            const targetEl = document.createElement('div');
            targetEl.id = targetId;
            wrapper.appendChild(targetEl);

            // Wait for YouTube IFrame API to be ready
            if (!window.youtubeApiReady) {
                await new Promise(resolve => {
                    window.addEventListener('youtube-api-ready', resolve, { once: true });
                });
            }

            // Verify YT object exists
            if (typeof YT === 'undefined' || typeof YT.Player === 'undefined') {
                console.warn('YouTube IFrame API not available');
                this.playerError = true;
                return;
            }

            // Create player
            try {
                // Timeout: if video doesn't load in 8s, show error
                this.playerTimeout = setTimeout(() => {
                    if (!this.playerReady) {
                        console.warn('YouTube player timeout - video not loading');
                        this.playerError = true;
                    }
                }, 8000);

                this.player = new YT.Player(targetId, {
                    videoId: videoId,
                    playerVars: {
                        controls: 0,      // Hide controls
                        disablekb: 1,     // Disable keyboard
                        modestbranding: 1,
                        rel: 0,           // No related videos
                        mute: 1,          // Muted for autoplay
                        playsinline: 1,   // iOS inline playback
                        autoplay: 1       // Start loading immediately
                    },
                    events: {
                        onReady: () => {
                            // Player API ready, but video might still be loading
                            // Start playback to trigger video loading
                            if (this.player) {
                                this.player.playVideo();
                            }
                        },
                        onStateChange: (event) => {
                            // States: -1=unstarted, 0=ended, 1=playing, 2=paused, 3=buffering, 5=cued
                            if (event.data === YT.PlayerState.PLAYING && !this.playerReady) {
                                // Video is actually playing - now we can seek
                                if (this.playerTimeout) {
                                    clearTimeout(this.playerTimeout);
                                    this.playerTimeout = null;
                                }
                                this.playerReady = true;
                                if (this.player) {
                                    this.player.seekTo(this.startTime, true);
                                    this.player.pauseVideo();
                                }
                            }
                        },
                        onError: (e) => {
                            // Error codes: 2 = invalid param, 5 = HTML5 error,
                            // 100 = not found, 101/150 = embed disabled
                            if (this.playerTimeout) {
                                clearTimeout(this.playerTimeout);
                                this.playerTimeout = null;
                            }
                            console.warn('YouTube player error:', e.data);
                            this.playerError = true;
                        }
                    }
                });
            } catch (e) {
                console.error('Failed to create YouTube player:', e);
                this.playerError = true;
            }
        },

        // Destroy YouTube player
        destroyPlayer() {
            // Clear pending timeout
            if (this.playerTimeout) {
                clearTimeout(this.playerTimeout);
                this.playerTimeout = null;
            }

            if (this.player) {
                try {
                    this.player.destroy();
                } catch (e) {
                    // Player might already be destroyed
                }
                this.player = null;
            }
            this.playerReady = false;
            this.playerError = false;
        },

        async downloadAndConvert() {
            if (!this.videoInfo || this.segmentTooLong) return;

            this.downloading = true;
            this.downloadProgress = 0;
            this.downloadPhase = 'Baixando e convertendo...';

            try {
                const response = await fetch('/api/youtube/download', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        url: this.url,
                        start: this.startTime,
                        end: this.endTime
                    })
                });

                if (!response.ok) {
                    const error = await response.json();
                    this.showMessage(error.detail || 'Erro no download', 'error');
                    return;
                }

                const data = await response.json();
                this.downloadId = data.id;
                this.previewUrl = data.preview_url;
                this.convertedFrames = data.frames;
                this.showMessage(`Convertido! ${data.frames} frames`, 'success');

            } catch (e) {
                console.error('Erro:', e);
                this.showMessage('Erro no download', 'error');
            } finally {
                this.downloading = false;
            }
        },

        async sendToPixoo() {
            if (!this.downloadId) return;

            this.sending = true;
            try {
                this.showMessage('Enviando para Pixoo...', 'info');

                const response = await fetch('/api/youtube/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: this.downloadId })
                });

                if (response.ok) {
                    const data = await response.json();
                    this.showMessage(`Enviado! ${data.frames_sent} frames`, 'success');
                } else {
                    const error = await response.json();
                    this.showMessage(error.detail || 'Erro ao enviar', 'error');
                }
            } catch (e) {
                console.error('Erro:', e);
                this.showMessage('Erro ao enviar para Pixoo', 'error');
            } finally {
                this.sending = false;
            }
        },

        downloadGif() {
            if (!this.downloadId) return;

            const a = document.createElement('a');
            a.href = `/api/youtube/download/${this.downloadId}`;
            a.download = `youtube_${this.downloadId}.gif`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        },

        clearVideo() {
            // Destroy YouTube player first
            this.destroyPlayer();

            this.url = '';
            this.videoInfo = null;
            this.startTime = 0;
            this.endTime = 10;
            this.startTimeStr = '00:00.00';
            this.endTimeStr = '00:10.00';
            this.downloading = false;
            this.downloadId = null;
            this.previewUrl = null;
            this.convertedFrames = 0;
            this.clearMessage();
            sessionStorage.removeItem('youtubeDownload');
        },

        showMessage(text, type) {
            utils.showMessage(this, text, type);
        },

        clearMessage() {
            utils.clearMessage(this);
        }
    };
}

// Expose utils globally for template use
window.formatTime = utils.formatTime;
window.formatFileSize = utils.formatFileSize;
