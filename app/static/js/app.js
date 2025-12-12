/**
 * Pixoo Manager - JavaScript
 * Componentes Alpine.js para interatividade
 */

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
            if (!file.type.includes('gif')) {
                this.showMessage('Por favor, selecione um arquivo GIF', 'error');
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
            this.message = text;
            this.messageType = type;
        },

        clearMessage() {
            this.message = '';
            this.messageType = '';
        }
    };
}

// ============================================
// Utility Functions
// ============================================

/**
 * Formata tempo em segundos para MM:SS.ms
 */
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
}

/**
 * Formata tamanho de arquivo em bytes para string legivel
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
