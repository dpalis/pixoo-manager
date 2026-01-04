/**
 * Pixoo Manager - JavaScript
 * Componentes Alpine.js para interatividade
 */

// ============================================
// Heartbeat - Keep server alive while browser is open
// ============================================
let heartbeatFailures = 0;
const MAX_HEARTBEAT_FAILURES = 3;

async function sendHeartbeat() {
    try {
        await fetch('/api/heartbeat', { method: 'POST' });
        heartbeatFailures = 0; // Reset on success
    } catch {
        heartbeatFailures++;
        if (heartbeatFailures >= MAX_HEARTBEAT_FAILURES) {
            showServerClosedOverlay();
        }
    }
}

function showServerClosedOverlay() {
    // Prevent multiple overlays
    if (document.querySelector('.server-closed-overlay')) return;

    const overlay = document.createElement('div');
    overlay.className = 'server-closed-overlay';
    overlay.innerHTML = `
        <div class="server-closed-content">
            <div class="server-closed-icon">🔌</div>
            <h2>Servidor Encerrado</h2>
            <p>O Pixoo Manager foi fechado.</p>
            <p>Você pode fechar esta aba com segurança.</p>
        </div>
    `;
    document.body.appendChild(overlay);
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
     * Formata tempo em segundos para MM:SS
     */
    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
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
     * Formato: MM:SS ou SS
     */
    parseTimeStr(str) {
        const match = str.match(/^(?:(\d+):)?(\d+)$/);
        if (!match) return null;
        const mins = parseInt(match[1] || '0');
        const secs = parseInt(match[2]);
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
// Precision Slider Component (1:1 mapping + keyboard arrows)
// ============================================
/**
 * Factory function that creates a precision slider component.
 * Uses direct 1:1 mouse mapping with keyboard arrows for fine adjustment.
 *
 * Controls:
 * - Mouse drag: Direct 1:1 positioning
 * - ← / →: Adjust by ±0.2 second
 * - Shift + ← / →: Adjust by ±5 seconds
 *
 * @param {Object} parentComponent - Reference to the parent Alpine component
 *                                   (must have startTime, endTime, startTimeStr, endTimeStr,
 *                                   getMaxDuration(), and optionally seekToTime())
 */
function precisionSlider(parentComponent) {
    return {
        // Estado
        dragging: null,           // 'start' | 'end' | null
        lastActiveHandle: null,   // 'start' | 'end' | null - receives keyboard adjustments
        sliderRect: null,         // Bounding rect do slider
        dragOffset: 0,            // Offset entre mouse e centro do handle no início do drag

        // Referência ao componente pai
        parent: parentComponent,

        // Computed
        get startPercent() {
            const max = this.parent.getMaxDuration();
            return max > 0 ? (this.parent.startTime / max) * 100 : 0;
        },

        get endPercent() {
            const max = this.parent.getMaxDuration();
            return max > 0 ? (this.parent.endTime / max) * 100 : 0;
        },

        get selectionWidth() {
            return this.endPercent - this.startPercent;
        },

        // Bind handlers for proper `this` context
        init() {
            this._onDrag = this.onDrag.bind(this);
            this._endDrag = this.endDrag.bind(this);
        },

        // Iniciar drag
        startDrag(event, handle) {
            event.preventDefault();
            this.dragging = handle;
            this.lastActiveHandle = handle;

            // Pegar o container .precision-slider (pai do handle clicado)
            const sliderContainer = event.target.closest('.precision-slider');
            this.sliderRect = sliderContainer.getBoundingClientRect();

            // Calcular offset: diferença entre onde o mouse clicou e onde o handle está
            const mouseX = event.clientX - this.sliderRect.left;
            const currentPercent = handle === 'start' ? this.startPercent : this.endPercent;
            const handleX = (currentPercent / 100) * this.sliderRect.width;
            this.dragOffset = mouseX - handleX;

            // Focus no slider para receber eventos de teclado
            sliderContainer.focus();

            // Listeners globais
            document.addEventListener('mousemove', this._onDrag);
            document.addEventListener('mouseup', this._endDrag);
        },

        // Handler de movimento - mapeamento 1:1 direto com offset
        onDrag(event) {
            if (!this.dragging || !this.sliderRect) return;

            // Calcular posição do mouse relativa ao slider, compensando o offset inicial
            const mouseX = event.clientX - this.sliderRect.left - this.dragOffset;
            const percent = Math.max(0, Math.min(1, mouseX / this.sliderRect.width));
            const duration = this.parent.getMaxDuration();
            const newTime = percent * duration;

            // Aplicar com limites
            if (this.dragging === 'start') {
                // Não ultrapassar o handle de fim (mínimo 1s de diferença)
                this.parent.startTime = Math.max(0, Math.min(newTime, this.parent.endTime - 1));
                this.parent.startTimeStr = utils.formatTime(this.parent.startTime);
                if (this.parent.seekToTime) this.parent.seekToTime(this.parent.startTime);
            } else {
                // Não ficar antes do handle de início
                this.parent.endTime = Math.max(this.parent.startTime + 1, Math.min(newTime, duration));
                this.parent.endTimeStr = utils.formatTime(this.parent.endTime);
                if (this.parent.seekToTime) this.parent.seekToTime(this.parent.endTime);
            }
        },

        // Finalizar drag
        endDrag() {
            this.dragging = null;

            // Remover listeners
            document.removeEventListener('mousemove', this._onDrag);
            document.removeEventListener('mouseup', this._endDrag);
        },

        // Ajuste via setas do teclado
        adjustTime(delta) {
            if (!this.lastActiveHandle) {
                // Se nenhum handle foi selecionado, selecionar o de início
                this.lastActiveHandle = 'start';
            }

            const duration = this.parent.getMaxDuration();

            if (this.lastActiveHandle === 'start') {
                const newTime = this.parent.startTime + delta;
                // Limites: >= 0 e < endTime - 1
                this.parent.startTime = Math.max(0, Math.min(newTime, this.parent.endTime - 1));
                this.parent.startTimeStr = utils.formatTime(this.parent.startTime);
                if (this.parent.seekToTime) this.parent.seekToTime(this.parent.startTime);
            } else {
                const newTime = this.parent.endTime + delta;
                // Limites: > startTime + 1 e <= duration
                this.parent.endTime = Math.max(this.parent.startTime + 1, Math.min(newTime, duration));
                this.parent.endTimeStr = utils.formatTime(this.parent.endTime);
                if (this.parent.seekToTime) this.parent.seekToTime(this.parent.endTime);
            }
        },

        // Handler de teclado
        handleKeydown(event) {
            if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;

            event.preventDefault();
            const delta = event.shiftKey ? 5 : 0.2;

            if (event.key === 'ArrowLeft') {
                this.adjustTime(-delta);
            } else {
                this.adjustTime(delta);
            }
        }
    };
}

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
        menuOpen: false,

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
        },

        showAbout() {
            alert('Pixoo Manager v1.3.0\n\nGerenciador de conteúdo para Divoom Pixoo 64.\n\nEnvie GIFs, fotos, vídeos e texto para seu display LED.');
        },

        async confirmShutdown() {
            this.menuOpen = false;

            if (confirm('Encerrar o Pixoo Manager?')) {
                try {
                    await fetch('/api/system/shutdown', { method: 'POST' });
                    showServerClosedOverlay();
                } catch (e) {
                    console.error('Erro ao encerrar:', e);
                }
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
        maxDuration: 5,  // Atualizado pelo backend
        startTime: 0,
        endTime: 5,
        startTimeStr: '00:00',
        endTimeStr: '00:05',
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
        // GIF trim state (para GIFs com muitos frames)
        needsTrim: false,
        gifTotalFrames: 0,
        gifDurationMs: 0,
        startFrame: 0,
        endFrame: 40,
        trimming: false,
        trimApplied: false,
        originalGifUploadId: null,
        originalGifPreviewUrl: null,
        originalGifTotalFrames: 0,
        // Frame preview (único frame, muda conforme slider ativo)
        currentFramePreviewUrl: null,
        currentFrameIndex: null,
        // GIF crop state (para selecionar área antes de converter)
        gifRawUploadId: null,
        gifFirstFrameUrl: null,
        gifCropApplied: false,
        gifCropApplying: false,
        gifOriginalWidth: 0,
        gifOriginalHeight: 0,
        // Video crop state (para selecionar área antes de converter)
        videoCropApplied: false,
        videoCropApplying: false,
        videoCropData: null,  // {x, y, width, height}
        videoFrameUrl: null,  // URL do frame extraído para cropper
        // Save to gallery state
        saveModalOpen: false,
        galleryName: '',
        savingToGallery: false,

        async init() {
            await this.restoreState();
            // Auto-save state when key properties change
            this.$watch('uploadId', () => this.saveState());
            this.$watch('previewUrl', () => this.saveState());
            this.$watch('converted', () => this.saveState());
            this.$watch('convertedPreviewUrl', () => this.saveState());
            // GIF-specific watchers
            this.$watch('gifRawUploadId', () => this.saveState());
            this.$watch('gifCropApplied', () => this.saveState());
            this.$watch('gifTotalFrames', () => this.saveState());
            this.$watch('startFrame', () => this.saveState());
            this.$watch('endFrame', () => this.saveState());
            this.$watch('needsTrim', () => this.saveState());
            this.$watch('trimApplied', () => this.saveState());
            // Video crop watchers
            this.$watch('videoCropApplied', () => this.saveState());
            this.$watch('videoCropData', () => this.saveState());
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
                cropApplied: this.cropApplied,
                // GIF-specific state
                gifRawUploadId: this.gifRawUploadId,
                gifFirstFrameUrl: this.gifFirstFrameUrl,
                gifCropApplied: this.gifCropApplied,
                gifTotalFrames: this.gifTotalFrames,
                startFrame: this.startFrame,
                endFrame: this.endFrame,
                needsTrim: this.needsTrim,
                trimApplied: this.trimApplied,
                // Video crop state
                videoCropApplied: this.videoCropApplied,
                videoCropData: this.videoCropData
                // Não salvar: file (File object), videoUrl (blob URL), cropper, originalImageUrl, videoFrameUrl
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

                // Validar gifRawUploadId (GIF antes do crop)
                if (state.gifRawUploadId && !state.uploadId) {
                    // Usar frame/0 endpoint (preview não existe para raw uploads)
                    const response = await fetch(`/api/gif/frame/${state.gifRawUploadId}/0`, { method: 'HEAD' });
                    if (!response.ok) {
                        console.log('GIF raw upload expirado, limpando estado local');
                        sessionStorage.removeItem('mediaUpload');
                        return;
                    }
                }

                Object.assign(this, state);

                // Inicializar frame preview se estiver no modo trim
                if (this.needsTrim && this.uploadId) {
                    this.$nextTick(() => this.initFramePreviews());
                }
            } catch (e) {
                console.error('Erro ao restaurar estado:', e);
                sessionStorage.removeItem('mediaUpload');
            }
        },

        get hasFile() {
            return this.uploadId !== null || this.gifRawUploadId !== null || this.originalImageUrl !== null;
        },

        get segmentDuration() {
            return Math.max(0, this.endTime - this.startTime);
        },

        get segmentTooLong() {
            // Arredonda para 1 casa decimal para evitar erros de ponto flutuante
            const rounded = Math.round(this.segmentDuration * 10) / 10;
            return rounded > this.maxDuration;
        },

        get canSend() {
            return (this.mediaType === 'gif' && this.uploadId && this.gifCropApplied && !this.needsTrim) ||
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
            // GIF and WebP may be animated - show cropper first
            const animatedTypes = ['image/gif', 'image/webp'];
            // Static images show cropper first
            const imageTypes = ['image/png', 'image/jpeg'];
            const videoTypes = ['video/mp4', 'video/quicktime', 'video/webm'];

            const isGif = animatedTypes.includes(file.type);
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

            // GIFs mostram cropper no primeiro frame
            if (isGif) {
                this.mediaType = 'gif';
                this.gifCropApplied = false;
                this.fileInfo = file.name;
                this.showMessage('Enviando GIF...', 'info');

                // Upload raw (sem conversão) para obter primeiro frame
                const formData = new FormData();
                formData.append('file', file);

                try {
                    const response = await fetch('/api/gif/upload-raw', {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) {
                        const error = await response.json();
                        this.showMessage(error.detail || 'Erro no upload', 'error');
                        return;
                    }

                    const data = await response.json();
                    this.gifRawUploadId = data.id;
                    this.gifFirstFrameUrl = data.first_frame_url;
                    this.gifOriginalWidth = data.width;
                    this.gifOriginalHeight = data.height;
                    this.gifTotalFrames = data.frames;
                    this.gifDurationMs = data.duration_ms;
                    this.fileInfo = `${data.width}x${data.height} - ${data.frames} frames`;
                    this.clearMessage();

                    // Inicializar cropper no primeiro frame
                    this.$nextTick(() => {
                        this.initGifCropper();
                    });
                } catch (e) {
                    console.error('Erro no upload:', e);
                    this.showMessage('Erro ao enviar arquivo', 'error');
                }
                return;
            }

            // Videos fazem upload direto e mostram cropper
            const formData = new FormData();
            formData.append('file', file);

            try {
                this.showMessage('Enviando arquivo...', 'info');

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

                // Video - primeiro mostra cropper
                this.mediaType = 'video';
                this.videoUrl = URL.createObjectURL(file);
                this.videoDuration = data.duration;
                this.maxDuration = data.max_duration || 5;
                this.endTime = Math.min(this.maxDuration, data.duration);
                this.endTimeStr = utils.formatTime(this.endTime);
                this.fileInfo = `${data.width}x${data.height} - ${data.duration.toFixed(1)}s`;
                this.videoCropApplied = false;
                this.videoCropData = null;
                this.clearMessage();

                // Aguardar vídeo carregar e extrair frame para cropper
                this.$nextTick(() => {
                    this.initVideoCropper();
                });

            } catch (e) {
                console.error('Erro no upload:', e);
                this.showMessage('Erro ao enviar arquivo', 'error');
            }
        },

        // Inicializa Cropper.js em qualquer ref de imagem
        initCropperFor(refName) {
            const image = this.$refs[refName];
            if (!image || this.cropper) return;

            this.cropper = new Cropper(image, {
                aspectRatio: 1,
                viewMode: 1,
                autoCropArea: 1,
                responsive: true,
                minContainerWidth: 300,
                minContainerHeight: 300
            });
        },

        initCropper() {
            this.initCropperFor('cropImage');
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

        initGifCropper() {
            this.initCropperFor('gifCropImage');
        },

        async applyGifCrop() {
            if (!this.cropper || this.gifCropApplying || !this.gifRawUploadId) return;

            this.gifCropApplying = true;
            this.showMessage('Processando recorte...', 'info');

            try {
                // Obter dados do crop
                const cropData = this.cropper.getData(true); // true = rounded values

                // Enviar para o backend aplicar crop em todos os frames
                const response = await fetch('/api/gif/crop-and-convert', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id: this.gifRawUploadId,
                        crop_x: Math.round(cropData.x),
                        crop_y: Math.round(cropData.y),
                        crop_width: Math.round(cropData.width),
                        crop_height: Math.round(cropData.height)
                    })
                });

                if (!response.ok) {
                    const error = await response.json();
                    this.showMessage(error.detail || 'Erro no recorte', 'error');
                    return;
                }

                const data = await response.json();
                this.uploadId = data.id;
                this.previewUrl = data.preview_url;
                this.fileInfo = `${data.width}x${data.height} - ${data.frames} frames`;
                this.gifCropApplied = true;

                // Destruir cropper
                if (this.cropper) {
                    this.cropper.destroy();
                    this.cropper = null;
                }

                // Verificar se precisa trim
                if (data.needs_trim) {
                    this.needsTrim = true;
                    this.gifTotalFrames = data.frames;
                    this.startFrame = 0;
                    this.endFrame = Math.min(40, data.frames);
                    this.converted = false;
                    // Inicializar previews de frames após um tick para garantir que uploadId está setado
                    this.$nextTick(() => this.initFramePreviews());
                    this.showMessage(`GIF tem ${data.frames} frames. Selecione um trecho de até 40 frames.`, 'info');
                } else {
                    this.needsTrim = false;
                    this.converted = true;
                    this.showMessage('Recorte aplicado!', 'success');
                }

            } catch (e) {
                console.error('Erro ao aplicar recorte:', e);
                this.showMessage('Erro ao processar recorte', 'error');
            } finally {
                this.gifCropApplying = false;
            }
        },

        initVideoCropper() {
            // Aguardar vídeo carregar para extrair frame
            const video = this.$refs.videoForCrop;
            if (!video) return;

            // Quando vídeo carregar, extrair frame
            video.onloadeddata = () => {
                this.extractVideoFrame();
            };

            // Se já carregou, extrair imediatamente
            if (video.readyState >= 2) {
                this.extractVideoFrame();
            }
        },

        extractVideoFrame() {
            const video = this.$refs.videoForCrop;
            if (!video) return;

            // Criar canvas para extrair frame
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0);

            // Converter para URL
            this.videoFrameUrl = canvas.toDataURL('image/png');

            // Inicializar cropper após render
            this.$nextTick(() => this.initCropperFor('videoCropImage'));
        },

        applyVideoCrop() {
            if (!this.cropper || this.videoCropApplying) return;

            this.videoCropApplying = true;

            try {
                // Obter dados do crop
                const cropData = this.cropper.getData(true);

                // Guardar coordenadas para usar na conversão
                this.videoCropData = {
                    x: Math.round(cropData.x),
                    y: Math.round(cropData.y),
                    width: Math.round(cropData.width),
                    height: Math.round(cropData.height)
                };

                this.videoCropApplied = true;

                // Destruir cropper
                if (this.cropper) {
                    this.cropper.destroy();
                    this.cropper = null;
                }

                // Limpar URL do frame
                this.videoFrameUrl = null;

                this.showMessage('Área de recorte selecionada. Agora selecione o trecho do vídeo.', 'success');

            } catch (e) {
                console.error('Erro ao aplicar recorte:', e);
                this.showMessage('Erro ao processar recorte', 'error');
            } finally {
                this.videoCropApplying = false;
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
                // Construir request com dados de crop se disponíveis
                const requestBody = {
                    id: this.uploadId,
                    start: this.startTime,
                    end: this.endTime
                };

                // Incluir coordenadas de crop se definidas
                if (this.videoCropData) {
                    requestBody.crop_x = this.videoCropData.x;
                    requestBody.crop_y = this.videoCropData.y;
                    requestBody.crop_width = this.videoCropData.width;
                    requestBody.crop_height = this.videoCropData.height;
                }

                // Usar endpoint sincrono por simplicidade
                const response = await fetch('/api/media/convert-sync', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestBody)
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
            this.maxDuration = 5;
            this.startTime = 0;
            this.endTime = 5;
            this.startTimeStr = '00:00';
            this.endTimeStr = '00:05';
            this.converting = false;
            this.converted = false;
            this.convertedPreviewUrl = null;
            this.convertedFrames = 0;

            // Reset estado do crop
            this.originalImageUrl = null;
            this.cropApplied = false;
            this.cropApplying = false;

            // Reset estado do trim (GIF)
            this.needsTrim = false;
            this.gifTotalFrames = 0;
            this.gifDurationMs = 0;
            this.startFrame = 0;
            this.endFrame = 40;
            this.trimming = false;
            this.trimApplied = false;
            this.originalGifUploadId = null;
            this.originalGifPreviewUrl = null;
            this.originalGifTotalFrames = 0;
            // Reset frame preview URLs
            this.currentFramePreviewUrl = null;
            this.currentFrameIndex = null;

            // Reset estado do crop (GIF)
            this.gifRawUploadId = null;
            this.gifFirstFrameUrl = null;
            this.gifCropApplied = false;
            this.gifCropApplying = false;
            this.gifOriginalWidth = 0;
            this.gifOriginalHeight = 0;

            // Reset estado do crop (Video)
            this.videoCropApplied = false;
            this.videoCropApplying = false;
            this.videoCropData = null;
            this.videoFrameUrl = null;

            this.clearMessage();
            sessionStorage.removeItem('mediaUpload');
        },

        clearConversion() {
            // Limpa apenas a conversão, mantendo o vídeo carregado
            this.converted = false;
            this.convertedPreviewUrl = null;
            this.convertedFrames = 0;
            this.converting = false;
            this.convertProgress = 0;
            this.convertPhase = '';
            this.clearMessage();
            this.saveState();
        },

        async trimGif() {
            // Recorta o GIF para o intervalo selecionado
            if (!this.uploadId || !this.needsTrim) return;

            const frameCount = this.endFrame - this.startFrame;
            if (frameCount > 40) {
                this.showMessage('Selecione no máximo 40 frames', 'error');
                return;
            }
            if (frameCount < 1) {
                this.showMessage('Selecione pelo menos 1 frame', 'error');
                return;
            }

            this.trimming = true;
            this.showMessage('Recortando GIF...', 'info');

            try {
                // Guardar original antes do primeiro trim
                if (!this.trimApplied) {
                    this.originalGifUploadId = this.uploadId;
                    this.originalGifPreviewUrl = this.previewUrl;
                    this.originalGifTotalFrames = this.gifTotalFrames;
                }

                const response = await fetch('/api/gif/trim', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id: this.uploadId,
                        start_frame: this.startFrame,
                        end_frame: this.endFrame
                    })
                });

                if (!response.ok) {
                    const error = await response.json();
                    this.showMessage(error.detail || 'Erro ao recortar', 'error');
                    return;
                }

                const data = await response.json();

                // Atualizar com o novo GIF recortado
                this.uploadId = data.id;
                this.previewUrl = data.preview_url;
                this.fileInfo = `${data.width}x${data.height} - ${data.frames} frames`;
                this.needsTrim = data.needs_trim;
                this.converted = !data.needs_trim;
                this.convertedFrames = data.frames;
                this.trimApplied = true;

                if (data.needs_trim) {
                    this.showMessage(`Ainda tem ${data.frames} frames. Reduza para 40.`, 'error');
                } else {
                    this.showMessage(`GIF recortado! ${data.frames} frames`, 'success');
                }

            } catch (e) {
                console.error('Erro ao recortar GIF:', e);
                this.showMessage('Erro ao recortar GIF', 'error');
            } finally {
                this.trimming = false;
            }
        },

        clearTrim() {
            // Volta ao GIF original para refazer o recorte
            if (!this.trimApplied || !this.originalGifUploadId) return;

            this.uploadId = this.originalGifUploadId;
            this.previewUrl = this.originalGifPreviewUrl;
            this.gifTotalFrames = this.originalGifTotalFrames;
            this.needsTrim = true;
            this.trimApplied = false;
            this.converted = false;
            this.startFrame = 0;
            this.endFrame = Math.min(40, this.originalGifTotalFrames);
            this.fileInfo = `64x64 - ${this.originalGifTotalFrames} frames`;
            // Reinicializar previews de frames
            this.$nextTick(() => this.initFramePreviews());
            this.showMessage('Recorte limpo. Selecione novos frames.', 'info');
        },

        get selectedFrameCount() {
            return Math.max(0, this.endFrame - this.startFrame);
        },

        get framesTooMany() {
            return this.selectedFrameCount > 40;
        },

        // Valida e ajusta frames quando startFrame muda
        validateStartFrame() {
            // Garante que startFrame não ultrapasse endFrame - 1
            if (this.startFrame >= this.endFrame) {
                this.startFrame = Math.max(0, this.endFrame - 1);
            }
            // Mostra o frame do slider que foi movido
            this.showFramePreview(this.startFrame);
        },

        // Valida e ajusta frames quando endFrame muda
        validateEndFrame() {
            // Garante que endFrame não seja menor que startFrame + 1
            if (this.endFrame <= this.startFrame) {
                this.endFrame = Math.min(this.gifTotalFrames, this.startFrame + 1);
            }
            // endFrame é exclusivo, então mostramos endFrame - 1
            this.showFramePreview(Math.max(0, this.endFrame - 1));
        },

        // Mostra preview de um frame específico (um único preview)
        showFramePreview(frameIndex) {
            if (!this.uploadId) return;
            this.currentFrameIndex = frameIndex;
            // Sem cache-busting - frames são imutáveis para um dado uploadId
            this.currentFramePreviewUrl = `/api/gif/frame/${this.uploadId}/${frameIndex}`;
        },

        // Inicializa preview quando entra no modo trim (mostra primeiro frame)
        initFramePreviews() {
            if (this.uploadId && this.needsTrim) {
                this.showFramePreview(this.startFrame);
            }
        },

        showMessage(text, type) {
            utils.showMessage(this, text, type);
        },

        clearMessage() {
            utils.clearMessage(this);
        },

        // Save to Gallery methods
        showSaveToGalleryModal() {
            // Default name based on file name (without extension)
            const baseName = this.fileName.replace(/\.[^/.]+$/, '');
            this.galleryName = baseName || 'Minha imagem';
            this.saveModalOpen = true;

            // Close on Escape key
            const closeOnEscape = (e) => {
                if (e.key === 'Escape' && this.saveModalOpen) {
                    this.saveModalOpen = false;
                    window.removeEventListener('keydown', closeOnEscape);
                }
            };
            window.addEventListener('keydown', closeOnEscape);
        },

        async saveToGallery() {
            if (!this.uploadId || !this.galleryName.trim() || this.savingToGallery) return;

            this.savingToGallery = true;

            try {
                const response = await fetch('/api/gallery/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        upload_id: this.uploadId,
                        name: this.galleryName.trim(),
                        source_type: this.mediaType || 'image'
                    })
                });

                const data = await response.json();
                if (response.ok) {
                    this.saveModalOpen = false;
                    this.showMessage(data.warning || 'Salvo na galeria!', data.warning ? 'warning' : 'success');
                } else {
                    this.showMessage(data.detail || 'Erro ao salvar', 'error');
                }
            } catch (e) {
                console.error('Erro ao salvar na galeria:', e);
                this.showMessage('Erro de conexão', 'error');
            } finally {
                this.savingToGallery = false;
            }
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
        endTime: 5,
        startTimeStr: '00:00',
        endTimeStr: '00:05',
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
        // Save to gallery state
        saveModalOpen: false,
        galleryName: '',
        savingToGallery: false,

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
            // Shorts permitem ate 60s, videos normais ate 5s
            return this.videoInfo?.max_duration || 5;
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
                // Just seek - the onStateChange handler will pause after frame loads
                this.player.seekTo(time, true);
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

            // Wait for YouTube IFrame API to be ready (with timeout for offline scenarios)
            if (!window.youtubeApiReady) {
                try {
                    await Promise.race([
                        new Promise(resolve => {
                            window.addEventListener('youtube-api-ready', resolve, { once: true });
                        }),
                        new Promise((_, reject) => setTimeout(() => reject(new Error('API timeout')), 5000))
                    ]);
                } catch (e) {
                    console.warn('YouTube API failed to load:', e.message);
                    this.playerError = true;
                    return;
                }
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
                        playsinline: 1    // iOS inline playback
                    },
                    events: {
                        onReady: () => {
                            // Player API ready - mark as ready immediately
                            if (this.playerTimeout) {
                                clearTimeout(this.playerTimeout);
                                this.playerTimeout = null;
                            }
                            this.playerReady = true;
                            // Don't seek on load - just let it show first frame
                            // Seek will happen when user moves slider
                        },
                        onStateChange: (event) => {
                            // When video starts playing, pause after brief delay to show frame
                            // NOTE: 100ms delay is required because YouTube IFrame API doesn't
                            // provide a "frame rendered" callback. Pausing immediately after
                            // seekTo() shows a black frame. This is a known API limitation.
                            if (event.data === YT.PlayerState.PLAYING) {
                                setTimeout(() => {
                                    if (this.player) {
                                        this.player.pauseVideo();
                                    }
                                }, 100);
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
            this.endTime = 5;
            this.startTimeStr = '00:00';
            this.endTimeStr = '00:05';
            this.downloading = false;
            this.downloadId = null;
            this.previewUrl = null;
            this.convertedFrames = 0;
            this.clearMessage();
            sessionStorage.removeItem('youtubeDownload');
        },

        clearConversion() {
            // Limpa apenas a conversão, mantendo o vídeo do YouTube
            this.downloadId = null;
            this.previewUrl = null;
            this.convertedFrames = 0;
            this.downloading = false;
            this.downloadProgress = 0;
            this.downloadPhase = '';
            this.clearMessage();
            this.saveState();
        },

        showMessage(text, type) {
            utils.showMessage(this, text, type);
        },

        clearMessage() {
            utils.clearMessage(this);
        },

        // Save to Gallery methods
        showSaveToGalleryModal() {
            // Default name based on video title
            this.galleryName = this.videoInfo?.title || 'YouTube clip';
            this.saveModalOpen = true;

            // Close on Escape key
            const closeOnEscape = (e) => {
                if (e.key === 'Escape' && this.saveModalOpen) {
                    this.saveModalOpen = false;
                    window.removeEventListener('keydown', closeOnEscape);
                }
            };
            window.addEventListener('keydown', closeOnEscape);
        },

        async saveToGallery() {
            if (!this.downloadId || !this.galleryName.trim() || this.savingToGallery) return;

            this.savingToGallery = true;

            try {
                const response = await fetch('/api/gallery/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        upload_id: this.downloadId,
                        name: this.galleryName.trim(),
                        source_type: 'youtube'
                    })
                });

                const data = await response.json();
                if (response.ok) {
                    this.saveModalOpen = false;
                    this.showMessage(data.warning || 'Salvo na galeria!', data.warning ? 'warning' : 'success');
                } else {
                    this.showMessage(data.detail || 'Erro ao salvar', 'error');
                }
            } catch (e) {
                console.error('Erro ao salvar na galeria:', e);
                this.showMessage('Erro de conexão', 'error');
            } finally {
                this.savingToGallery = false;
            }
        }
    };
}

// ============================================
// Text Display Component
// ============================================
function textDisplay() {
    return {
        text: '',
        color: '#FFFFFF',
        backgroundColor: '#000000',
        speed: 50,
        fontStyle: 0,
        y: 28,
        sending: false,
        message: '',
        messageType: '',
        animationId: null,
        scrollX: 320,
        ctx: null,

        get canSend() {
            return this.text.trim().length > 0 && !this.sending;
        },

        init() {
            this.$nextTick(() => this.initCanvas());
        },

        initCanvas() {
            const canvas = this.$refs.previewCanvas;
            if (!canvas) return;
            this.ctx = canvas.getContext('2d');
            this.animate();
        },

        updatePreview() {
            // Reset scroll position when text changes
            if (this.text.length === 0) {
                this.scrollX = 320;
            }
        },

        animate() {
            if (!this.ctx) return;
            const ctx = this.ctx;

            // Clear canvas with background color (simulating LED display)
            ctx.fillStyle = this.backgroundColor;
            ctx.fillRect(0, 0, 320, 320);

            // Draw grid (64x64 pixels scaled 5x)
            ctx.strokeStyle = '#1a1a2e';
            ctx.lineWidth = 0.5;
            for (let i = 0; i <= 64; i++) {
                ctx.beginPath();
                ctx.moveTo(i * 5, 0);
                ctx.lineTo(i * 5, 320);
                ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(0, i * 5);
                ctx.lineTo(320, i * 5);
                ctx.stroke();
            }

            // Draw text if present
            if (this.text) {
                ctx.fillStyle = this.color;

                // Font size and style based on fontStyle selection
                // IDs: 0=Normal, 2=Compacto, 4=Largo, 5=Retro, 7=Pequeno, 8=Fino
                let fontSize = 40;
                let fontWeight = 'normal';
                let fontFamily = 'monospace';

                switch (parseInt(this.fontStyle)) {
                    case 0:  // Normal
                        fontSize = 40;
                        break;
                    case 2:  // Compacto
                        fontSize = 36;
                        fontFamily = 'Arial Narrow, sans-serif';
                        break;
                    case 4:  // Largo
                        fontSize = 48;
                        break;
                    case 5:  // Retro/Pixel
                        fontSize = 40;
                        fontFamily = 'Courier New, monospace';
                        break;
                    case 7:  // Pequeno
                        fontSize = 28;
                        break;
                    case 8:  // Fino
                        fontSize = 36;
                        fontWeight = '300';
                        break;
                }

                ctx.font = `${fontWeight} ${fontSize}px ${fontFamily}`;
                ctx.textBaseline = 'top';
                ctx.fillText(this.text, this.scrollX, parseInt(this.y) * 5);

                // Animate scroll
                const textWidth = ctx.measureText(this.text).width;
                // Speed: lower value = faster scroll
                const scrollSpeed = (210 - this.speed) / 30;
                this.scrollX -= scrollSpeed;

                // Reset when text scrolls off screen
                if (this.scrollX < -textWidth) {
                    this.scrollX = 320;
                }
            }

            this.animationId = requestAnimationFrame(() => this.animate());
        },

        async sendText() {
            if (!this.canSend) return;

            this.sending = true;
            this.clearMessage();

            try {
                const response = await fetch('/api/text/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text: this.text,
                        color: this.color,
                        background_color: this.backgroundColor,
                        speed: parseInt(this.speed),
                        font: parseInt(this.fontStyle),  // Usa fontStyle como ID de fonte
                        y: parseInt(this.y)
                    })
                });

                const data = await response.json();
                if (response.ok && data.success) {
                    this.showMessage('Texto enviado!', 'success');
                } else {
                    this.showMessage(data.detail || 'Erro ao enviar', 'error');
                }
            } catch (e) {
                console.error('Erro ao enviar texto:', e);
                this.showMessage('Erro de conexao', 'error');
            } finally {
                this.sending = false;
            }
        },

        async clearText() {
            try {
                const response = await fetch('/api/text/clear', { method: 'POST' });
                const data = await response.json();

                if (response.ok && data.success) {
                    this.showMessage('Textos limpos!', 'success');
                } else {
                    this.showMessage(data.detail || 'Erro ao limpar', 'error');
                }
            } catch (e) {
                console.error('Erro ao limpar textos:', e);
                this.showMessage('Erro ao limpar', 'error');
            }
        },

        showMessage(text, type) {
            this.message = text;
            this.messageType = type;
            setTimeout(() => this.clearMessage(), 3000);
        },

        clearMessage() {
            this.message = '';
            this.messageType = '';
        }
    };
}


// ============================================
// Gallery View Component
// ============================================

function galleryView() {
    return {
        // State
        items: [],
        loading: false,
        sending: false,
        selectedItem: null,
        searchQuery: '',
        showFavoritesOnly: false,
        modalOpen: false,
        deleteConfirmId: null,
        message: '',
        messageType: '',

        // Selection mode state
        selectionMode: false,
        selectedIds: [],
        bulkDeleteConfirm: false,
        clearGalleryConfirm: false,
        clearGalleryInput: '',

        // Stats
        stats: null,

        // Pagination
        page: 1,
        perPage: 50,
        total: 0,
        hasMore: false,

        // Debounce timer
        searchDebounceTimer: null,

        // Getters
        get filteredItems() {
            // Filtering is done server-side, this just returns items
            return this.items;
        },

        get canSend() {
            return this.selectedItem && !this.sending;
        },

        get isEmpty() {
            return !this.loading && this.items.length === 0 && !this.searchQuery && !this.showFavoritesOnly;
        },

        get noResults() {
            return !this.loading && this.items.length === 0 && (this.searchQuery || this.showFavoritesOnly);
        },

        get selectedCount() {
            return this.selectedIds.length;
        },

        get allSelected() {
            return this.items.length > 0 && this.items.every(i => this.selectedIds.includes(i.id));
        },

        // Lifecycle
        async init() {
            await this.loadGallery();
            await this.loadStats();
        },

        // Methods
        async loadGallery() {
            this.loading = true;
            this.clearMessage();

            try {
                const params = new URLSearchParams({
                    page: this.page.toString(),
                    per_page: this.perPage.toString(),
                });

                if (this.showFavoritesOnly) {
                    params.append('favorites_only', 'true');
                }
                if (this.searchQuery.trim()) {
                    params.append('search', this.searchQuery.trim());
                }

                const response = await fetch(`/api/gallery/list?${params}`);
                const data = await response.json();

                if (response.ok) {
                    this.items = data.items;
                    this.total = data.total;
                    this.hasMore = data.has_more;
                } else {
                    this.showMessage(data.detail || 'Erro ao carregar galeria', 'error');
                }
            } catch (e) {
                console.error('Erro ao carregar galeria:', e);
                this.showMessage('Erro de conexão', 'error');
            } finally {
                this.loading = false;
            }
        },

        async loadStats() {
            try {
                const response = await fetch('/api/gallery/stats');
                if (response.ok) {
                    this.stats = await response.json();
                }
            } catch (e) {
                console.error('Erro ao carregar stats:', e);
            }
        },

        async loadMore() {
            if (!this.hasMore || this.loading) return;

            this.page++;
            this.loading = true;

            try {
                const params = new URLSearchParams({
                    page: this.page.toString(),
                    per_page: this.perPage.toString(),
                });

                if (this.showFavoritesOnly) {
                    params.append('favorites_only', 'true');
                }
                if (this.searchQuery.trim()) {
                    params.append('search', this.searchQuery.trim());
                }

                const response = await fetch(`/api/gallery/list?${params}`);
                const data = await response.json();

                if (response.ok) {
                    this.items = [...this.items, ...data.items];
                    this.total = data.total;
                    this.hasMore = data.has_more;
                }
            } catch (e) {
                console.error('Erro ao carregar mais:', e);
            } finally {
                this.loading = false;
            }
        },

        // Search with debounce
        onSearchInput() {
            clearTimeout(this.searchDebounceTimer);
            this.searchDebounceTimer = setTimeout(() => {
                this.page = 1;
                this.loadGallery();
            }, 300);
        },

        // Toggle favorites filter
        toggleFavoritesFilter() {
            this.showFavoritesOnly = !this.showFavoritesOnly;
            this.page = 1;
            this.loadGallery();
        },

        // Select item for preview
        selectItem(item) {
            this.selectedItem = item;
            this.modalOpen = true;
        },

        // Close modal
        closeModal() {
            this.modalOpen = false;
            this.selectedItem = null;
        },

        // Send to Pixoo
        async sendToPixoo() {
            if (!this.canSend) return;

            this.sending = true;
            this.clearMessage();

            try {
                const response = await fetch(`/api/gallery/${this.selectedItem.id}/send`, {
                    method: 'POST',
                });

                const data = await response.json();
                if (response.ok && data.success) {
                    this.showMessage(`Enviado! ${data.frames_sent} frames`, 'success');
                } else {
                    this.showMessage(data.detail || 'Erro ao enviar', 'error');
                }
            } catch (e) {
                console.error('Erro ao enviar:', e);
                this.showMessage('Erro de conexão', 'error');
            } finally {
                this.sending = false;
            }
        },

        // Toggle favorite
        async toggleFavorite(item, event) {
            event.stopPropagation();

            try {
                const response = await fetch(`/api/gallery/${item.id}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ is_favorite: !item.is_favorite }),
                });

                if (response.ok) {
                    const updated = await response.json();
                    // Update item in list
                    const index = this.items.findIndex(i => i.id === item.id);
                    if (index !== -1) {
                        this.items[index] = updated;
                    }
                    // Update selected item if it's the same
                    if (this.selectedItem && this.selectedItem.id === item.id) {
                        this.selectedItem = updated;
                    }
                    // Reload stats
                    await this.loadStats();
                }
            } catch (e) {
                console.error('Erro ao favoritar:', e);
            }
        },

        // Show delete confirmation
        confirmDelete(item, event) {
            event.stopPropagation();
            this.deleteConfirmId = item.id;
        },

        // Cancel delete
        cancelDelete() {
            this.deleteConfirmId = null;
        },

        // Delete item
        async deleteItem(item, event) {
            if (event) event.stopPropagation();

            try {
                const response = await fetch(`/api/gallery/${item.id}`, {
                    method: 'DELETE',
                });

                if (response.ok) {
                    // Remove from list
                    this.items = this.items.filter(i => i.id !== item.id);
                    this.total--;
                    this.deleteConfirmId = null;

                    // Close modal if this item was selected
                    if (this.selectedItem && this.selectedItem.id === item.id) {
                        this.closeModal();
                    }

                    // Reload stats
                    await this.loadStats();

                    this.showMessage('Item removido', 'success');
                } else {
                    const data = await response.json();
                    this.showMessage(data.detail || 'Erro ao remover', 'error');
                }
            } catch (e) {
                console.error('Erro ao remover:', e);
                this.showMessage('Erro de conexão', 'error');
            }
        },

        // Selection mode methods
        toggleSelectionMode() {
            this.selectionMode = !this.selectionMode;
            if (!this.selectionMode) {
                this.selectedIds = [];
                this.bulkDeleteConfirm = false;
            }
        },

        isSelected(id) {
            return this.selectedIds.includes(id);
        },

        toggleSelection(item, event) {
            if (event) event.stopPropagation();
            const idx = this.selectedIds.indexOf(item.id);
            if (idx === -1) {
                this.selectedIds.push(item.id);
            } else {
                this.selectedIds.splice(idx, 1);
            }
        },

        selectAll() {
            this.selectedIds = this.items.map(i => i.id);
        },

        clearSelection() {
            this.selectedIds = [];
        },

        // Bulk delete methods
        confirmBulkDelete() {
            if (this.selectedCount === 0) return;
            this.bulkDeleteConfirm = true;
        },

        cancelBulkDelete() {
            this.bulkDeleteConfirm = false;
        },

        async deleteSelected() {
            if (this.selectedCount === 0) return;

            this.loading = true;
            try {
                const response = await fetch('/api/gallery/delete-batch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ item_ids: this.selectedIds }),
                });

                if (response.ok) {
                    const data = await response.json();
                    // Remove deleted items from list
                    this.items = this.items.filter(i => !this.selectedIds.includes(i.id));
                    this.total -= data.deleted_count;
                    this.selectedIds = [];
                    this.selectionMode = false;
                    this.bulkDeleteConfirm = false;
                    await this.loadStats();
                    this.showMessage(`${data.deleted_count} itens removidos`, 'success');
                } else {
                    const data = await response.json();
                    this.showMessage(data.detail || 'Erro ao deletar', 'error');
                }
            } catch (e) {
                console.error('Erro ao deletar:', e);
                this.showMessage('Erro de conexão', 'error');
            } finally {
                this.loading = false;
            }
        },

        // Clear gallery methods
        showClearGalleryModal() {
            this.clearGalleryConfirm = true;
            this.clearGalleryInput = '';
        },

        cancelClearGallery() {
            this.clearGalleryConfirm = false;
            this.clearGalleryInput = '';
        },

        get canClearGallery() {
            return this.clearGalleryInput.toUpperCase() === 'LIMPAR';
        },

        async clearGallery() {
            if (!this.canClearGallery) return;

            this.loading = true;
            try {
                const response = await fetch('/api/gallery/all', {
                    method: 'DELETE',
                });

                if (response.ok) {
                    const data = await response.json();
                    this.items = [];
                    this.total = 0;
                    this.selectionMode = false;
                    this.selectedIds = [];
                    this.clearGalleryConfirm = false;
                    this.clearGalleryInput = '';
                    await this.loadStats();
                    this.showMessage(`Galeria limpa (${data.deleted_count} itens)`, 'success');
                } else {
                    const data = await response.json();
                    this.showMessage(data.detail || 'Erro ao limpar', 'error');
                }
            } catch (e) {
                console.error('Erro ao limpar galeria:', e);
                this.showMessage('Erro de conexão', 'error');
            } finally {
                this.loading = false;
            }
        },

        // Format file size
        formatSize(bytes) {
            return utils.formatFileSize(bytes);
        },

        // Format date
        formatDate(isoString) {
            const date = new Date(isoString);
            return date.toLocaleDateString('pt-BR', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
            });
        },

        // Message helpers
        showMessage(text, type) {
            this.message = text;
            this.messageType = type;
            setTimeout(() => this.clearMessage(), 3000);
        },

        clearMessage() {
            this.message = '';
            this.messageType = '';
        },

        // Keyboard navigation
        handleKeydown(event) {
            // ESC: Close modals or exit selection mode
            if (event.key === 'Escape') {
                if (this.bulkDeleteConfirm) {
                    this.cancelBulkDelete();
                } else if (this.clearGalleryConfirm) {
                    this.cancelClearGallery();
                } else if (this.modalOpen) {
                    this.closeModal();
                } else if (this.selectionMode) {
                    this.toggleSelectionMode();
                }
                return;
            }

            if (this.modalOpen) {
                if (event.key === 'Enter' && this.canSend) {
                    this.sendToPixoo();
                } else if (event.key === 'Delete' && this.selectedItem) {
                    this.confirmDelete(this.selectedItem, event);
                }
            }
        }
    };
}


// Expose utils globally for template use
window.formatTime = utils.formatTime;
window.formatFileSize = utils.formatFileSize;
