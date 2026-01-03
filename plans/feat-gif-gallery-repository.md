# feat: GIF Gallery Repository

> Repositorio persistente para salvar e reutilizar GIFs criados no Pixoo Manager

## Overview

Criar um sistema de galeria/repositorio no app Pixoo Manager que permita:
- Salvar GIFs convertidos permanentemente (nao expiram como os temporarios)
- Carregar e enviar GIFs salvos com um clique
- Organizar com favoritos e busca por nome

**Motivacao:** Atualmente, GIFs convertidos sao temporarios e expiram apos 1 hora. Usuarios precisam reconverter midias frequentemente usadas. Uma galeria persistente elimina retrabalho.

---

## Proposed Solution

### Arquitetura

```
~/.pixoo_manager/gallery/
├── gifs/           # GIFs salvos (UUID.gif)
├── thumbnails/     # Thumbnails 128x128 JPEG
├── metadata.json   # Indice com metadados
└── metadata.json.bak # Backup (criado antes de cada save)
```

### Componentes

| Componente | Arquivo | Responsabilidade |
|------------|---------|------------------|
| GalleryManager | `services/gallery_manager.py` | Persistencia, CRUD, thumbnails, atomic writes |
| Gallery Router | `routers/gallery.py` | API endpoints |
| galleryView() | `static/js/app.js` | Componente Alpine.js |
| Gallery Tab | `templates/base.html` | HTML da nova tab |

### Fluxos Principais

1. **Salvar:** Converter midia -> Preview -> "Salvar na Galeria" -> Nome -> Salvo
2. **Carregar:** Galeria -> Click thumbnail -> Preview -> "Enviar para Pixoo"
3. **Deletar:** Galeria -> Hover -> Delete icon -> Confirmar -> Removido

---

## Technical Approach

### Backend

#### Metadata Schema (`metadata.json`)

```json
{
  "version": "1.0",
  "items": {
    "a3f2e1d0": {
      "id": "a3f2e1d0",
      "name": "Sunset Animation",
      "filename": "a3f2e1d0.gif",
      "source_type": "video",
      "created_at": "2026-01-03T10:30:00Z",
      "file_size_bytes": 245760,
      "frame_count": 32,
      "is_favorite": false
    }
  }
}
```

#### API Endpoints

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/api/gallery/list` | Lista itens (paginado) |
| GET | `/api/gallery/thumbnail/{id}` | Retorna thumbnail JPEG |
| GET | `/api/gallery/{id}` | Retorna GIF completo |
| POST | `/api/gallery/save` | Salva GIF do upload atual |
| PATCH | `/api/gallery/{id}` | Atualiza metadados (nome, favorito) |
| DELETE | `/api/gallery/{id}` | Remove item |
| POST | `/api/gallery/{id}/send` | Envia para Pixoo |

#### Geracao de Thumbnails

```python
# services/gallery_manager.py
def generate_thumbnail(gif_path: Path, output_path: Path):
    """Gera thumbnail 128x128 com NEAREST para pixel art."""
    with Image.open(gif_path) as img:
        img.seek(0)  # Primeiro frame
        frame = img.convert('RGB')
        # 2x scale para retina (64->128) com NEAREST para preservar pixels
        scaled = frame.resize((128, 128), Image.Resampling.NEAREST)
        scaled.save(output_path, "JPEG", quality=85, optimize=True)
```

#### Atomic File Write Pattern

```python
# services/gallery_manager.py
def _atomic_json_write(self, filepath: Path, data: dict) -> None:
    """Escreve JSON atomicamente usando temp + replace."""
    # Backup antes de escrever
    if filepath.exists():
        backup_path = filepath.with_suffix('.json.bak')
        shutil.copy2(filepath, backup_path)

    # Criar temp file no mesmo diretorio (mesmo filesystem)
    fd, temp_path = tempfile.mkstemp(
        dir=filepath.parent,
        prefix=f".{filepath.name}.",
        suffix=".tmp"
    )
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(temp_path, filepath)  # Atomico
    except:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
```

### Frontend

#### Componente Alpine.js

```javascript
// static/js/app.js
function galleryView() {
    return {
        items: [],
        loading: false,
        selectedItem: null,
        searchQuery: '',
        showFavoritesOnly: false,
        modalOpen: false,
        deleteConfirmId: null,

        get filteredItems() {
            return this.items.filter(item => {
                if (this.showFavoritesOnly && !item.is_favorite) return false;
                if (this.searchQuery) {
                    return item.name.toLowerCase().includes(this.searchQuery.toLowerCase());
                }
                return true;
            });
        },

        async init() { await this.loadGallery(); },
        async loadGallery() { /* fetch /api/gallery/list */ },
        async sendToPixoo(id) { /* POST /api/gallery/{id}/send */ },
        async deleteItem(id) { /* DELETE /api/gallery/{id} */ },
        async toggleFavorite(id) { /* PATCH /api/gallery/{id} */ }
    };
}
```

#### Layout CSS Grid

```css
/* static/css/styles.css */
.gallery-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 1rem;
}

.gallery-item {
    aspect-ratio: 1;
    position: relative;
    cursor: pointer;
}

.gallery-thumbnail {
    width: 100%;
    height: 100%;
    object-fit: cover;
    image-rendering: pixelated; /* Pixels nitidos */
    border-radius: 0.5rem;
}
```

---

## Decisions Made

As decisoes a seguir foram tomadas com base na pesquisa de melhores praticas:

| Decisao | Opcao Escolhida | Justificativa |
|---------|-----------------|---------------|
| Nomes duplicados | Auto-numerar | "sunset (2).gif" - mais amigavel que erro |
| Naming no disco | UUID | Evita colisoes, seguro para filesystem |
| Limite de itens | 500 itens OU 500 MB | Equilibrio entre utilidade e performance |
| Armazenamento | JSON (nao SQLite) | Simples para < 500 itens, legivel |
| Backup | metadata.json.bak | Antes de cada save |
| Thumbnails | JPEG 128x128, NEAREST | Pixels nitidos para pixel art |
| Cache thumbnails | Arquivos em disco | Nao regenerar a cada load |
| Lazy loading | 50 itens por batch | Balance entre performance e UX |
| Search debounce | 300ms | Responsivo sem sobrecarregar |
| Sort order | Favoritos primeiro, depois alfabetico | Intuitivo para usuarios |
| Nome vazio | Auto-gerar timestamp | "gif_20260103_143022" |
| Max nome | 100 caracteres | Limite razoavel para UI |
| Caracteres nome | Alfanum + espaco + - _ ( ) . | Seguro para filesystem |

---

## Acceptance Criteria

### Functional Requirements

- [ ] **Salvar GIF:** Botao "Salvar na Galeria" aparece apos conversao em todas as tabs (Media, YouTube, GIF)
- [ ] **Persistencia:** GIFs salvos em `~/.pixoo_manager/gallery/` sobrevivem restart do app
- [ ] **Listar:** Nova tab "Galeria" exibe grid de thumbnails 128x128
- [ ] **Preview:** Click em thumbnail abre modal com GIF em tamanho real
- [ ] **Enviar:** Botao "Enviar para Pixoo" envia GIF selecionado (requer conexao)
- [ ] **Deletar:** Botao delete com confirmacao remove GIF e thumbnail
- [ ] **Favoritos:** Star icon marca/desmarca favorito
- [ ] **Busca:** Campo de busca filtra por nome em tempo real (300ms debounce)
- [ ] **Empty State:** Mensagem amigavel quando galeria vazia
- [ ] **Nome duplicado:** Auto-numera se nome ja existe ("sunset (2).gif")
- [ ] **Limite:** Warning em 90% (450 items ou 450 MB), erro em 100%

### Non-Functional Requirements

- [ ] **Performance:** Galeria com 100 itens carrega em < 2 segundos
- [ ] **Lazy Loading:** Thumbnails carregam 50 por batch via Intersection Observer
- [ ] **Cache:** Thumbnails com `Cache-Control: max-age=86400`
- [ ] **Acessibilidade:** Navegacao por teclado (Tab entre items, Enter abre, Delete remove, Escape fecha modal)
- [ ] **Atomic Writes:** metadata.json escrito via temp+replace, backup em .bak

### Quality Gates

- [ ] Testes unitarios para `GalleryManager` (CRUD, atomic writes, corruption recovery)
- [ ] Teste de integracao para endpoints da API
- [ ] Teste manual de todos os fluxos listados

---

## Success Metrics

| Metrica | Target |
|---------|--------|
| Tempo para salvar GIF | < 1 segundo |
| Tempo para carregar galeria (50 itens) | < 1 segundo |
| Tempo para enviar do galeria | Igual ao envio normal |
| Uso de disco por GIF | ~300 KB (GIF) + ~10 KB (thumb) |

---

## Dependencies & Prerequisites

### Tecnicas
- [x] FastAPI com routers pattern (ja existe)
- [x] Alpine.js para componentes reativos (ja existe)
- [x] Pillow para processamento de imagem (ja existe)
- [x] Padrao UploadManager para referencia (ja existe)

---

## Risk Analysis & Mitigation

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|---------------|---------|-----------|
| Metadata corruption | Media | Alto | Atomic writes + backup .bak + rebuild por scan |
| Disco cheio | Baixa | Medio | Limite de 500 MB, warning em 80% |
| Thumbnail generation fail | Baixa | Baixo | Fallback para primeiro frame |
| Race condition em save | Baixa | Medio | Lock no GalleryManager (RLock) |
| GIF faltando no disco | Baixa | Medio | Mostrar placeholder + permitir delete |
| metadata.json + .bak corrompidos | Muito baixa | Alto | Rebuild catalogo escaneando arquivos GIF |

---

## Implementation Phases

### Phase 1: Backend Core
**Arquivos:** `services/gallery_manager.py`, `config.py`

```
app/config.py (modificar)
  + GALLERY_DIR = Path.home() / ".pixoo_manager" / "gallery"
  + GALLERY_MAX_ITEMS = 500
  + GALLERY_MAX_SIZE_MB = 500
  + GALLERY_WARN_THRESHOLD = 0.9  # 90%
```

```
app/services/gallery_manager.py (novo)
  class GalleryManager:
    - _ensure_directories()
    - _load_metadata()
    - _save_metadata()  # atomic write
    - _generate_thumbnail()
    - save_gif(source_path, name, source_type) -> GalleryItem
    - list_items(page, per_page) -> List[GalleryItem]
    - get_item(id) -> GalleryItem
    - delete_item(id) -> bool
    - update_item(id, name?, is_favorite?) -> GalleryItem
    - get_gif_path(id) -> Path
    - get_thumbnail_path(id) -> Path
    - _get_storage_stats() -> (item_count, total_bytes)
    - _can_save(new_file_size) -> (bool, warning_message?)
    - _sanitize_name(name) -> str
    - _generate_unique_name(name) -> str
    - _recover_from_backup() -> bool
    - _rebuild_from_files() -> int
```

- [ ] Criar `GALLERY_DIR` e constantes em config.py
- [ ] Implementar `GalleryManager` class
  - [ ] `_ensure_directories()` - cria estrutura ~/.pixoo_manager/gallery/
  - [ ] `_load_metadata()` / `_save_metadata()` - com atomic writes
  - [ ] `save_gif()` - copia GIF, gera thumbnail, atualiza metadata
  - [ ] `list_items()` - lista com paginacao
  - [ ] `delete_item()` - remove arquivos e metadata
  - [ ] `get_gif_path()` / `get_thumbnail_path()`
  - [ ] `_sanitize_name()` - remove caracteres invalidos
  - [ ] `_generate_unique_name()` - adiciona (2), (3) se duplicado
  - [ ] `_recover_from_backup()` - fallback para .bak
  - [ ] `_rebuild_from_files()` - escaneia gifs/ e recria metadata

### Phase 2: API Router
**Arquivos:** `routers/gallery.py`, `main.py`

```
app/routers/gallery.py (novo)
  router = APIRouter(prefix="/api/gallery", tags=["gallery"])

  class GalleryItemResponse(BaseModel): ...
  class GalleryListResponse(BaseModel): ...
  class SaveRequest(BaseModel): ...
  class UpdateRequest(BaseModel): ...

  GET  /list - lista paginada
  GET  /thumbnail/{id} - FileResponse com cache
  GET  /{id} - FileResponse do GIF
  POST /save - salva do upload atual (recebe upload_id + name)
  PATCH /{id} - atualiza nome/favorito
  DELETE /{id} - remove
  POST /{id}/send - envia para Pixoo
```

```
app/main.py (modificar)
  + from app.routers import gallery as gallery_router
  + app.include_router(gallery_router.router)
  + @app.get("/gallery") -> TemplateResponse("base.html", active_tab="gallery")
```

- [ ] Criar router com prefix `/api/gallery`
- [ ] Implementar Pydantic models para request/response
- [ ] Implementar endpoints:
  - [ ] `GET /list` - lista paginada
  - [ ] `GET /thumbnail/{id}` - FileResponse com Cache-Control
  - [ ] `GET /{id}` - FileResponse do GIF
  - [ ] `POST /save` - salva do upload atual
  - [ ] `PATCH /{id}` - atualiza nome/favorito
  - [ ] `DELETE /{id}` - remove
  - [ ] `POST /{id}/send` - envia para Pixoo
- [ ] Registrar router em `main.py`
- [ ] Adicionar rota `/gallery` para pagina

### Phase 3: Frontend - Gallery Tab
**Arquivos:** `static/js/app.js`, `static/css/styles.css`, `templates/base.html`

```
app/templates/base.html (modificar)
  + <a href="/gallery" class="tab">Galeria</a> na nav
  + {% elif active_tab == 'gallery' %} section com x-data="galleryView()"
```

```
app/static/js/app.js (modificar)
  + function galleryView() { ... }
```

```
app/static/css/styles.css (modificar)
  + .gallery-grid { ... }
  + .gallery-item { ... }
  + .gallery-thumbnail { ... }
  + .gallery-empty { ... }
  + .gallery-modal { ... }
  + .favorite-star { ... }
  + .delete-btn { ... }
```

- [ ] Adicionar tab "Galeria" na navegacao (apos Texto)
- [ ] Criar `galleryView()` em app.js
  - [ ] Estado: items, loading, selectedItem, searchQuery, showFavoritesOnly, modalOpen
  - [ ] Getters: filteredItems, canSend
  - [ ] Metodos: loadGallery, sendToPixoo, deleteItem, toggleFavorite
- [ ] Implementar grid responsivo com thumbnails
- [ ] Implementar modal de preview (x-show, x-transition, focus trap)
- [ ] Implementar acoes: enviar, deletar, favoritar
- [ ] Implementar busca (300ms debounce) e filtro de favoritos
- [ ] Implementar empty state (galeria vazia vs busca sem resultados)
- [ ] Adicionar lazy loading com Intersection Observer (x-intersect)
- [ ] Adicionar keyboard navigation (Tab, Enter, Delete, Escape)
- [ ] Adicionar CSS para grid, thumbnails, modal, estados

### Phase 4: Integration - Save Button
**Arquivos:** `templates/base.html`, `static/js/app.js`

- [ ] Adicionar botao "Salvar na Galeria" na tab Media (apos Download)
- [ ] Adicionar botao "Salvar na Galeria" na tab YouTube (apos Download)
- [ ] Adicionar botao "Salvar na Galeria" na tab GIF (apos conversao)
- [ ] Implementar modal para nome do GIF ao salvar
- [ ] Feedback de sucesso com link "Ver na Galeria"

### Phase 5: Polish & Edge Cases

- [ ] Keyboard navigation (Tab, Enter, Escape, Delete)
- [ ] Loading states em todas as acoes
- [ ] Error handling com mensagens claras
- [ ] Metadata corruption recovery (backup + rebuild)
- [ ] Limite de armazenamento com warning em 90%
- [ ] ARIA labels para acessibilidade
- [ ] Focus management (apos delete, foco no proximo item)

---

## File Structure

```
app/
├── config.py                    # + GALLERY_DIR, GALLERY_MAX_SIZE, GALLERY_WARN_THRESHOLD
├── main.py                      # + include_router(gallery_router), + /gallery route
├── routers/
│   └── gallery.py               # NEW: API endpoints
├── services/
│   └── gallery_manager.py       # NEW: Persistencia e CRUD
├── static/
│   ├── css/
│   │   └── styles.css           # + Gallery styles (.gallery-grid, .gallery-item, etc)
│   └── js/
│       └── app.js               # + galleryView()
└── templates/
    └── base.html                # + Gallery tab + section
```

---

## References & Research

### Internal References (padroes do projeto)
- `app/services/upload_manager.py:35-202` - Padrao de manager com TTL e RLock
- `app/services/file_utils.py:297-328` - Padrao cleanup_files()
- `app/routers/gif_upload.py:47-100` - Padrao de router com Pydantic models
- `app/static/js/app.js:591-1463` - Padrao de componente Alpine.js (mediaUpload)
- `app/templates/base.html:81-105` - Sistema de tabs com Jinja2
- `app/config.py:36` - Padrao TEMP_DIR com Path

### External References
- [FastAPI FileResponse](https://fastapi.tiangolo.com/advanced/custom-response/#fileresponse) - Cache-Control headers
- [Pillow Resampling](https://pillow.readthedocs.io/en/stable/handbook/concepts.html#filters) - NEAREST para pixel art
- [Alpine.js x-for](https://alpinejs.dev/directives/for) - Loop em grid
- [Alpine.js x-intersect](https://alpinejs.dev/plugins/intersect) - Lazy loading
- [Python os.replace](https://docs.python.org/3/library/os.html#os.replace) - Atomic file operations
- [CSS Grid auto-fill](https://developer.mozilla.org/en-US/docs/Web/CSS/repeat) - Grid responsivo

### Related Work
- Issue #62 - Shutdown button (merged)
- Pattern: Upload Manager TTL - `compounding-knowledge/patterns/upload-manager-ttl.md`

---

## AI-Era Notes

- Pesquisa realizada com 3 agentes paralelos (repo-analyst, best-practices, framework-docs)
- SpecFlow Analyzer identificou 23 questoes criticas -> todas resolvidas neste plano
- Implementacao estimada: 1-2 sessoes de desenvolvimento com Claude Code
- Testes manuais criticos: empty state, 100+ itens, metadata corruption, atomic writes
