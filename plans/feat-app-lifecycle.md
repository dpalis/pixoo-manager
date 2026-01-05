# feat: App Lifecycle Management

> Gerenciamento do ciclo de vida do app: atualização, desinstalação e distribuição via DMG

## Overview

Adicionar três funcionalidades relacionadas ao ciclo de vida do Pixoo Manager:

1. **Verificar Atualizações** - Checar GitHub Releases e notificar o usuário
2. **Desinstalar** - Remover dados do usuário com instruções para remoção completa
3. **Distribuição DMG** - Criar DMG profissional para publicação no GitHub

**Motivação:** Atualmente não há forma integrada de atualizar o app, desinstalar limpa o sistema, ou distribuir para novos usuários de forma profissional.

---

## Decisions Made

| Decisão | Opção Escolhida | Justificativa |
|---------|-----------------|---------------|
| Framework de update | GitHub API customizado | Sparkle é complexo para py2app; solução simples é suficiente |
| Comparação de versão | Semantic versioning (packaging lib) | Já disponível, robusto |
| Download de update | Abrir browser na release page | Mais simples, transparente, evita problemas com Gatekeeper |
| Diálogos | Web-based (Alpine.js modals) | Consistência com UI existente |
| Versão atual | Ler de `app/__version__.py` (dev) ou `Info.plist` (bundle) | Já existe padrão no código |
| Code signing | Não (documentar workaround) | Requer Apple Developer Account ($99/ano) |
| Throttling de API | Não implementar | Complexidade desnecessária; rate limit é 60/hora |
| Auto-check on launch | Não (apenas manual) | Simplicidade; pode adicionar depois |
| Changelog | GitHub release body, plain text | Simples, sem dependência de markdown parser |
| Menubar vs dropdown | Espelhar itens idênticos | Consistência |
| DMG architecture | Universal (arm64 + x64) | py2app suporta universal2 |
| DMG visual | create-dmg padrão com background | Profissional sem complexidade |

---

## Technical Approach

### Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Menu Dropdown │  │   Menubar    │  │  Modals      │       │
│  │ (base.html)   │  │ (menubar.py) │  │ (Alpine.js)  │       │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘       │
│         │                  │                                 │
│         ▼                  ▼                                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              API Endpoints (routers/)                │    │
│  │  POST /api/system/check-update                       │    │
│  │  POST /api/system/uninstall                          │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Backend                               │
│  ┌──────────────────────┐  ┌──────────────────────┐         │
│  │ services/updater.py  │  │ services/uninstaller │         │
│  │ - check_for_update() │  │ - cleanup_user_data()│         │
│  │ - get_current_version│  └──────────────────────┘         │
│  └──────────────────────┘                                   │
│              │                                               │
│              ▼                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              External                                 │   │
│  │  GitHub API: GET /repos/dpalis/pixoo-manager/...      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Fluxos Principais

#### Flow 1: Verificar Atualizações
```
User clica "Verificar Atualizações"
    │
    ▼
Modal loading: "Verificando..."
    │
    ▼
API: POST /api/system/check-update
    │
    ├─► 200 + update_available: true
    │       │
    │       ▼
    │   Modal: "Nova versão disponível!"
    │   - Versão atual: 1.3.0
    │   - Nova versão: 1.4.0
    │   - Changelog (primeiros 500 chars)
    │   - [Baixar] [Fechar]
    │       │
    │       ▼ (click Baixar)
    │   webbrowser.open(release_url)
    │
    ├─► 200 + update_available: false
    │       │
    │       ▼
    │   Modal: "Você está usando a versão mais recente (1.3.0)"
    │   - [OK]
    │
    └─► error
            │
            ▼
        Modal: "Erro ao verificar atualizações"
        - Mensagem de erro específica
        - [OK]
```

#### Flow 2: Desinstalar
```
User clica "Desinstalar"
    │
    ▼
Modal confirmação:
"Isso vai deletar todos os GIFs salvos na galeria
e outros dados em ~/.pixoo_manager/

Esta ação não pode ser desfeita."
- [Cancelar] [Desinstalar]
    │
    ▼ (click Desinstalar)
API: POST /api/system/uninstall
    │
    ├─► 200 + success: true
    │       │
    │       ▼
    │   Modal sucesso:
    │   "Dados removidos com sucesso!
    │
    │   Para completar a desinstalação:
    │   1. Feche este app
    │   2. Arraste 'Pixoo Manager' para a Lixeira
    │   3. Esvazie a Lixeira"
    │   - [OK]
    │
    └─► 200 + success: false
            │
            ▼
        Modal erro:
        "Não foi possível remover alguns arquivos:
        - {lista de arquivos}

        Tente remover manualmente."
        - [OK]
```

---

## Proposed Solution

### Componentes

| Componente | Arquivo | Responsabilidade |
|------------|---------|------------------|
| UpdateChecker | `services/updater.py` | GitHub API, comparação de versão |
| Uninstaller | `services/uninstaller.py` | Remoção de ~/.pixoo_manager/ |
| System Router | `routers/system.py` | Endpoints check-update e uninstall |
| Update Modal | `templates/base.html` | UI para resultado do check |
| Uninstall Modal | `templates/base.html` | UI para confirmação e resultado |
| Menu Items | `templates/base.html` | Novos itens no dropdown |
| Menubar Items | `menubar.py` | Novos itens no menu macOS |
| DMG Builder | `scripts/build_dmg.sh` | Criação do DMG |

### API Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/system/check-update` | Verifica updates no GitHub |
| POST | `/api/system/uninstall` | Remove dados do usuário |

### Estrutura de Resposta

```python
# POST /api/system/check-update
{
    "update_available": bool,
    "current_version": "1.3.0",
    "latest_version": "1.4.0",      # se disponível
    "changelog": "### Changes...",   # primeiros 500 chars
    "release_url": "https://...",    # para abrir no browser
    "error": None | "mensagem"
}

# POST /api/system/uninstall
{
    "success": bool,
    "deleted_path": "~/.pixoo_manager/",
    "deleted_size_bytes": 12345678,  # opcional
    "failed_files": [],              # lista de arquivos que falharam
    "error": None | "mensagem"
}
```

---

## Acceptance Criteria

### Functional Requirements

#### Check for Updates
- [ ] Menu dropdown tem item "Verificar Atualizações" entre "Sobre" e divisor
- [ ] Menu bar (rumps) tem item "Verificar Atualizações"
- [ ] Click mostra modal de loading durante verificação
- [ ] Se update disponível: mostra versão atual, nova, changelog (500 chars max)
- [ ] Botão "Baixar" abre browser na página de release do GitHub
- [ ] Se não há update: mostra "Você está na versão mais recente"
- [ ] Se erro (offline, rate limit, etc): mostra mensagem apropriada
- [ ] Funciona tanto rodando como .app quanto em desenvolvimento

#### Uninstall
- [ ] Menu dropdown tem item "Desinstalar" antes de "Encerrar" (com divisor)
- [ ] Menu bar (rumps) tem item "Desinstalar"
- [ ] Click mostra modal de confirmação com warning
- [ ] Confirmação remove `~/.pixoo_manager/` recursivamente
- [ ] Se diretório não existe: trata como sucesso
- [ ] Se falha parcial: lista arquivos que não foram removidos
- [ ] Sucesso mostra instruções para arrastar app para Lixeira
- [ ] Desconecta do Pixoo antes de deletar (se conectado)

#### DMG Distribution
- [ ] Script `scripts/build_dmg.sh` cria DMG com create-dmg
- [ ] DMG contém app + symlink para Applications
- [ ] DMG tem nome `Pixoo-Manager-{version}.dmg`
- [ ] Janela do DMG tem tamanho 600x400
- [ ] Instruções no README para instalação (workaround Gatekeeper)

### Non-Functional Requirements

- [ ] API call para GitHub tem timeout de 10 segundos
- [ ] Versão é comparada usando semantic versioning (packaging lib)
- [ ] Remoção de arquivos usa shutil.rmtree com error handling
- [ ] Código Python segue patterns existentes (async, typing, docstrings)
- [ ] Modals usam Alpine.js consistente com modals existentes

### Error Messages (Portuguese)

| Situação | Mensagem |
|----------|----------|
| Sem internet | "Sem conexão com a internet. Verifique sua rede." |
| Rate limit | "Limite de verificações atingido. Tente novamente em 1 hora." |
| GitHub down | "Não foi possível conectar ao GitHub. Tente mais tarde." |
| Timeout | "A verificação demorou muito. Tente novamente." |
| Permissão negada | "Sem permissão para remover alguns arquivos." |
| Diretório não existe | (tratar como sucesso, não mostrar erro) |

---

## Implementation Phases

### Phase 1: Backend - Update Checker
**Arquivos:** `services/updater.py`, `config.py`

```
app/services/updater.py (novo)
  class UpdateChecker:
    - GITHUB_OWNER = "dpalis"
    - GITHUB_REPO = "pixoo-manager"
    - get_current_version() -> str
    - check_for_update() -> UpdateResult
    - _fetch_latest_release() -> dict
    - _compare_versions(current, latest) -> bool

app/config.py (modificar)
  + GITHUB_OWNER = "dpalis"
  + GITHUB_REPO = "pixoo-manager"
  + UPDATE_CHECK_TIMEOUT = 10
```

- [ ] Criar `UpdateChecker` class
- [ ] Implementar `get_current_version()` (Info.plist em bundle, __version__.py em dev)
- [ ] Implementar `check_for_update()` com GitHub API
- [ ] Usar `packaging.version` para comparação semântica
- [ ] Tratar erros: timeout, rate limit, offline, JSON inválido
- [ ] Truncar changelog em 500 caracteres

### Phase 2: Backend - Uninstaller
**Arquivos:** `services/uninstaller.py`

```
app/services/uninstaller.py (novo)
  class Uninstaller:
    - cleanup_user_data() -> UninstallResult
    - _get_data_dir() -> Path
    - _calculate_size(path) -> int
    - _safe_rmtree(path) -> (bool, list[str])
```

- [ ] Criar `Uninstaller` class
- [ ] Implementar `cleanup_user_data()` que remove ~/.pixoo_manager/
- [ ] Desconectar do Pixoo antes de remover (usar get_pixoo_connection())
- [ ] Calcular tamanho antes de remover (opcional, para feedback)
- [ ] Tratar diretório inexistente como sucesso
- [ ] Coletar lista de arquivos que falharam

### Phase 3: API Router
**Arquivos:** `routers/system.py`, `main.py`

```
app/routers/system.py (novo ou mover de heartbeat.py)
  router = APIRouter(prefix="/api/system", tags=["system"])

  class CheckUpdateResponse(BaseModel): ...
  class UninstallResponse(BaseModel): ...

  POST /check-update - verifica updates
  POST /uninstall - remove dados
```

- [ ] Criar router `/api/system` (ou expandir heartbeat.py)
- [ ] Implementar POST `/check-update`
- [ ] Implementar POST `/uninstall`
- [ ] Mover `/shutdown` existente para este router (opcional, refactor)
- [ ] Registrar router em main.py

### Phase 4: Frontend - Modals
**Arquivos:** `templates/base.html`, `static/js/app.js`, `static/css/styles.css`

```
app/templates/base.html (modificar)
  + Modal de update (loading, result, error states)
  + Modal de uninstall (confirm, success, error states)

app/static/js/app.js (modificar)
  + checkForUpdates() - chama API, gerencia modal states
  + openUpdatePage(url) - abre browser via window.open
  + confirmUninstall() - mostra confirm, chama API
  + Novos states no connectionStatus(): updateModal, uninstallModal
```

- [ ] Criar modal de update com 3 states (loading, result, error)
- [ ] Criar modal de uninstall com 2 states (confirm, result)
- [ ] Implementar `checkForUpdates()` em app.js
- [ ] Implementar `confirmUninstall()` em app.js
- [ ] Adicionar CSS para novos modals (seguir padrão existente)

### Phase 5: Menu Items
**Arquivos:** `templates/base.html`, `menubar.py`

```
app/templates/base.html (modificar)
  Menu dropdown:
    - Sobre
    - Verificar Atualizações  ← novo
    - <hr>                    ← novo divisor
    - Desinstalar             ← novo
    - <hr>
    - Encerrar

app/menubar.py (modificar)
  Menu items:
    - Abrir no navegador
    - Verificar Atualizações  ← novo
    - None (separator)
    - Desinstalar             ← novo
    - None (separator)
    - Encerrar
```

- [ ] Adicionar "Verificar Atualizações" no dropdown (base.html)
- [ ] Adicionar "Desinstalar" no dropdown (base.html)
- [ ] Adicionar separadores apropriados
- [ ] Adicionar itens equivalentes no menubar.py
- [ ] Implementar callbacks no rumps para novos itens

### Phase 6: DMG Builder
**Arquivos:** `scripts/build_dmg.sh`, `.github/workflows/release.yml` (opcional)

```
scripts/build_dmg.sh (novo)
  #!/bin/bash
  - Verifica se dist/Pixoo.app existe
  - Lê versão de app/__version__.py
  - Chama create-dmg com opções
  - Output: Pixoo-Manager-{version}.dmg
```

- [ ] Instalar create-dmg (brew install create-dmg)
- [ ] Criar script build_dmg.sh
- [ ] Configurar window size 600x400
- [ ] Configurar icon positions (app left, Applications right)
- [ ] Testar DMG criado (montar, arrastar, verificar)
- [ ] Documentar processo de release no README

### Phase 7: Documentation
**Arquivos:** `README.md`

- [ ] Documentar como instalar via DMG
- [ ] Documentar workaround do Gatekeeper (Control+Click → Abrir)
- [ ] Documentar como verificar atualizações
- [ ] Documentar como desinstalar completamente

---

## File Structure

```
app/
├── config.py                    # + GITHUB_OWNER, GITHUB_REPO, UPDATE_CHECK_TIMEOUT
├── main.py                      # + include_router(system_router)
├── menubar.py                   # + "Verificar Atualizações", "Desinstalar"
├── routers/
│   ├── heartbeat.py             # (manter shutdown aqui ou mover)
│   └── system.py                # NEW: check-update, uninstall endpoints
├── services/
│   ├── updater.py               # NEW: UpdateChecker class
│   └── uninstaller.py           # NEW: Uninstaller class
├── static/
│   ├── css/
│   │   └── styles.css           # + modal styles para update/uninstall
│   └── js/
│       └── app.js               # + checkForUpdates(), confirmUninstall()
└── templates/
    └── base.html                # + menu items, modals

scripts/
└── build_dmg.sh                 # NEW: script para criar DMG

README.md                        # + installation, update, uninstall docs
```

---

## Risk Analysis & Mitigation

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| GitHub API rate limit | Média | Baixo | Mensagem clara, usuário pode esperar 1h |
| App não assinado bloqueia instalação | Alta | Alto | Documentar workaround no README |
| Usuário perde dados sem querer | Baixa | Alto | Modal de confirmação com warning claro |
| Permissão negada ao deletar | Baixa | Médio | Listar arquivos que falharam |
| Versão incorreta no bundle | Baixa | Médio | Testar em dev e prod separadamente |
| create-dmg não instalado | Baixa | Baixo | Verificar no script, instruir instalação |

---

## Dependencies & Prerequisites

### Novas Dependências Python
- `packaging` - já instalado (usado por pip)

### Ferramentas de Build
- `create-dmg` - instalar via `brew install create-dmg`

### Requisitos
- [x] py2app configurado e funcionando
- [x] Menu dropdown existente (base.html)
- [x] Menubar existente (menubar.py)
- [x] Alpine.js para modals
- [x] Patterns de router/service estabelecidos

---

## References & Research

### Internal References
- `app/__version__.py:1` - versão atual "1.3.0"
- `app/config.py:39` - GALLERY_DIR = `~/.pixoo_manager/gallery`
- `app/templates/base.html:37-63` - menu dropdown existente
- `app/menubar.py:1-30` - menu bar com rumps
- `app/routers/heartbeat.py:40-50` - endpoint /api/system/shutdown existente
- `setup.py:78-84` - configuração py2app com CFBundleVersion

### External References
- [GitHub REST API - Releases](https://docs.github.com/en/rest/releases/releases)
- [create-dmg](https://github.com/create-dmg/create-dmg)
- [py2app Documentation](https://py2app.readthedocs.io/en/latest/)
- [packaging library](https://packaging.pypa.io/en/stable/)
- [Gatekeeper workaround](https://support.apple.com/en-us/HT202491)

### Related Work
- PR #134 - Shutdown button (menu dropdown pattern)
- Issue #133 - Menu dropdown design decisions

---

## Success Metrics

| Métrica | Target |
|---------|--------|
| Tempo para verificar update | < 3 segundos (com internet) |
| Tempo para desinstalar dados | < 2 segundos (galeria típica) |
| Tamanho do DMG | ~400 MB (similar ao .app) |
| Taxa de erro em check-update | < 5% (exceto offline) |

---

## AI-Era Notes

- Pesquisa realizada com 3 agentes paralelos (repo-analyst, best-practices, framework-docs)
- SpecFlow Analyzer identificou 27 questões → todas resolvidas neste plano
- Decisões priorizaram simplicidade sobre features avançadas (ex: sem auto-update)
- Implementação estimada: 1 sessão de desenvolvimento com Claude Code
- Testes manuais críticos: check update offline, uninstall com galeria vazia/cheia, DMG em Mac limpo
