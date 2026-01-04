# feat: Deleção em Massa na Galeria

> Permitir seleção múltipla de GIFs e deleção em lote

## Overview

Adicionar funcionalidade para o usuário:
- Selecionar múltiplos GIFs de uma vez
- Deletar todos os selecionados com um clique
- Deletar toda a galeria (limpar tudo)

**Motivação:** Atualmente, deletar GIFs é individual (1 por vez). Para uma galeria com muitos itens, limpar ou reorganizar é tedioso.

---

## Estado Atual

### Backend (`services/gallery_manager.py`)
- `delete_item(item_id)` - deleta um item por vez
- Não há método para deleção em massa

### API (`routers/gallery.py`)
- `DELETE /api/gallery/{item_id}` - deleta um item
- Não há endpoint para batch delete

### Frontend (`static/js/app.js` - `galleryView()`)
- `deleteItem(item)` - deleta um item
- `deleteConfirmId` - confirmação individual
- Não há modo de seleção múltipla

---

## Proposed Solution

### Fluxo do Usuário

1. **Seleção Múltipla:**
   - Clicar em "Selecionar" entra em modo de seleção
   - Click nos thumbnails adiciona/remove da seleção (checkbox aparece)
   - "Selecionar Todos" marca todos os visíveis
   - "Limpar Seleção" desmarca todos

2. **Deletar Selecionados:**
   - Botão "Deletar (N)" aparece quando há seleção
   - Confirmação: "Deletar N GIFs? Esta ação é irreversível."
   - Após deletar, sai do modo de seleção

3. **Limpar Galeria:**
   - Botão no footer ou menu: "Limpar Galeria"
   - Confirmação dupla: digitar "LIMPAR" para confirmar
   - Deleta TODOS os itens da galeria

---

## Technical Approach

### Phase 1: Backend

#### `services/gallery_manager.py`

```python
def delete_items(self, item_ids: List[str]) -> int:
    """
    Remove múltiplos itens da galeria.

    Returns:
        Quantidade de itens removidos
    """
    with self._lock:
        deleted = 0
        for item_id in item_ids:
            item = self._items.get(item_id)
            if item is None:
                continue

            # Remover arquivos
            gif_path = self.gifs_dir / item.filename
            thumb_path = self.thumbnails_dir / f"{item_id}.jpg"

            if gif_path.exists():
                gif_path.unlink()
            if thumb_path.exists():
                thumb_path.unlink()

            del self._items[item_id]
            deleted += 1

        if deleted > 0:
            self._save_metadata()

        return deleted

def delete_all(self) -> int:
    """
    Remove TODOS os itens da galeria.

    Returns:
        Quantidade de itens removidos
    """
    with self._lock:
        count = len(self._items)

        # Limpar diretórios
        for gif in self.gifs_dir.glob("*.gif"):
            gif.unlink()
        for thumb in self.thumbnails_dir.glob("*.jpg"):
            thumb.unlink()

        self._items.clear()
        self._save_metadata()

        return count
```

### Phase 2: API

#### `routers/gallery.py`

```python
class BulkDeleteRequest(BaseModel):
    """Request para deletar múltiplos itens."""
    item_ids: List[str] = Field(..., min_length=1, max_length=500)

class BulkDeleteResponse(BaseModel):
    """Response após deleção em massa."""
    deleted_count: int

@router.post("/delete-batch", response_model=BulkDeleteResponse)
async def delete_batch(request: BulkDeleteRequest):
    """
    Remove múltiplos itens da galeria.
    """
    count = await asyncio.to_thread(gallery.delete_items, request.item_ids)
    return BulkDeleteResponse(deleted_count=count)

@router.delete("/all", response_model=BulkDeleteResponse)
async def delete_all():
    """
    Remove TODOS os itens da galeria.

    ⚠️ AÇÃO IRREVERSÍVEL - Use com cuidado!
    """
    count = await asyncio.to_thread(gallery.delete_all)
    return BulkDeleteResponse(deleted_count=count)
```

### Phase 3: Frontend

#### Estado adicional em `galleryView()`

```javascript
// Seleção múltipla
selectionMode: false,
selectedIds: new Set(),

get selectedCount() {
    return this.selectedIds.size;
},

get allSelected() {
    return this.items.length > 0 &&
           this.items.every(i => this.selectedIds.has(i.id));
},
```

#### Métodos novos

```javascript
// Entrar/sair do modo de seleção
toggleSelectionMode() {
    this.selectionMode = !this.selectionMode;
    if (!this.selectionMode) {
        this.selectedIds.clear();
    }
},

// Toggle seleção de um item
toggleSelection(item, event) {
    event.stopPropagation();
    if (this.selectedIds.has(item.id)) {
        this.selectedIds.delete(item.id);
    } else {
        this.selectedIds.add(item.id);
    }
    // Forçar reatividade
    this.selectedIds = new Set(this.selectedIds);
},

// Selecionar todos
selectAll() {
    this.items.forEach(item => this.selectedIds.add(item.id));
    this.selectedIds = new Set(this.selectedIds);
},

// Limpar seleção
clearSelection() {
    this.selectedIds.clear();
    this.selectedIds = new Set(this.selectedIds);
},

// Deletar selecionados
async deleteSelected() {
    if (this.selectedIds.size === 0) return;

    const ids = Array.from(this.selectedIds);

    try {
        const response = await fetch('/api/gallery/delete-batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ item_ids: ids }),
        });

        if (response.ok) {
            const data = await response.json();
            this.items = this.items.filter(i => !this.selectedIds.has(i.id));
            this.total -= data.deleted_count;
            this.selectedIds.clear();
            this.selectionMode = false;
            await this.loadStats();
            this.showMessage(`${data.deleted_count} itens removidos`, 'success');
        }
    } catch (e) {
        this.showMessage('Erro ao deletar', 'error');
    }
},

// Limpar galeria (deletar tudo)
async clearGallery() {
    try {
        const response = await fetch('/api/gallery/all', {
            method: 'DELETE',
        });

        if (response.ok) {
            const data = await response.json();
            this.items = [];
            this.total = 0;
            this.selectionMode = false;
            this.selectedIds.clear();
            await this.loadStats();
            this.showMessage(`Galeria limpa (${data.deleted_count} itens)`, 'success');
        }
    } catch (e) {
        this.showMessage('Erro ao limpar galeria', 'error');
    }
}
```

### Phase 4: UI/HTML

#### Barra de seleção (acima do grid)

```html
<!-- Barra de seleção -->
<div class="gallery-selection-bar" x-show="selectionMode">
    <span x-text="`${selectedCount} selecionado(s)`"></span>
    <button @click="selectAll()" class="btn-text">Selecionar Todos</button>
    <button @click="clearSelection()" class="btn-text">Limpar</button>
    <button @click="confirmDeleteSelected()" class="btn-danger" :disabled="selectedCount === 0">
        Deletar Selecionados
    </button>
    <button @click="toggleSelectionMode()" class="btn-text">Cancelar</button>
</div>
```

#### Checkbox no item da galeria

```html
<div class="gallery-item" :class="{ 'selected': selectedIds.has(item.id) }">
    <!-- Checkbox de seleção -->
    <div class="gallery-checkbox"
         x-show="selectionMode"
         @click.stop="toggleSelection(item, $event)">
        <span x-show="selectedIds.has(item.id)">✓</span>
    </div>
    <!-- resto do item -->
</div>
```

#### Botão para entrar em modo de seleção

```html
<button @click="toggleSelectionMode()" class="btn-icon" title="Selecionar">
    <!-- Ícone de checkbox -->
</button>
```

---

## Acceptance Criteria

- [ ] Botão "Selecionar" entra em modo de seleção
- [ ] Click em thumbnail adiciona/remove da seleção (checkbox visual)
- [ ] "Selecionar Todos" seleciona todos os itens visíveis
- [ ] "Limpar Seleção" desmarca todos
- [ ] "Deletar Selecionados" remove com confirmação
- [ ] "Limpar Galeria" remove tudo com confirmação dupla
- [ ] Após deleção, stats são atualizados
- [ ] ESC sai do modo de seleção
- [ ] UI responsiva (barra de seleção não quebra em mobile)

---

## Implementation Phases

### Phase 1: Backend (GalleryManager)
- [ ] Adicionar `delete_items(item_ids: List[str]) -> int`
- [ ] Adicionar `delete_all() -> int`
- [ ] Testes unitários

### Phase 2: API (Router)
- [ ] Adicionar `POST /api/gallery/delete-batch`
- [ ] Adicionar `DELETE /api/gallery/all`
- [ ] Models Pydantic para request/response

### Phase 3: Frontend - Estado
- [ ] Adicionar estado de seleção (`selectionMode`, `selectedIds`)
- [ ] Adicionar getters (`selectedCount`, `allSelected`)
- [ ] Adicionar métodos de seleção

### Phase 4: Frontend - UI
- [ ] Barra de seleção (selection bar)
- [ ] Checkbox nos itens
- [ ] Botão "Selecionar" no header
- [ ] Modal de confirmação para bulk delete
- [ ] Modal com input para "Limpar Galeria"
- [ ] CSS para estados de seleção

### Phase 5: Polish
- [ ] Keyboard shortcuts (ESC para sair, Delete para deletar)
- [ ] Animações de feedback
- [ ] Loading states durante deleção

---

## Riscos e Mitigações

| Risco | Mitigação |
|-------|-----------|
| Deletar acidentalmente | Confirmação obrigatória |
| Limpar galeria por engano | Confirmação dupla (digitar "LIMPAR") |
| Performance com muitos itens | Processar em chunks no backend |

---

## Referências

- `app/services/gallery_manager.py:368-393` - Método `delete_item()` atual
- `app/routers/gallery.py:285-297` - Endpoint de delete atual
- `app/static/js/app.js:2374-2417` - Lógica de deleção no frontend
