---
module: Pixoo Manager
date: 2025-12-15
problem_type: runtime_error
component: service_object
symptoms:
  - "Race condition when multiple requests access shared state"
  - "Inconsistent connection status between requests"
  - "Memory leak from orphaned upload entries without cleanup"
root_cause: thread_violation
resolution_type: code_fix
severity: critical
tags: [singleton, thread-safety, fastapi, rlock, ttl, state-management]
---

# Troubleshooting: Thread-safe Singleton para FastAPI com Estado Compartilhado

## Problem

Aplicações FastAPI que mantêm estado compartilhado (conexões, uploads em andamento, cache) sofrem race conditions quando múltiplas requests acessam o singleton simultaneamente, causando comportamento inconsistente e memory leaks.

## Environment

- Module: Pixoo Manager (FastAPI application)
- Python Version: 3.10+
- Affected Component: PixooConnection singleton, UploadManager
- Date: 2025-12-15

## Symptoms

- Race condition durante inicialização do singleton (duas instâncias criadas)
- Estado de conexão inconsistente entre requests (`is_connected` retorna valores diferentes)
- Uploads órfãos acumulando em memória indefinidamente
- Arquivos temporários nunca limpos quando usuário abandona operação

## What Didn't Work

**Attempted Solution 1:** Singleton simples sem locks
- **Why it failed:** FastAPI usa thread pool para requests síncronos. Múltiplas threads podem passar pelo `if _instance is None` simultaneamente.

**Attempted Solution 2:** Lock simples no `__new__`
- **Why it failed:** Protege criação mas não protege leitura/escrita de estado. Properties como `is_connected` ainda têm race conditions.

**Attempted Solution 3:** Dict simples para uploads
- **Why it failed:** Sem TTL, entradas crescem indefinidamente. Usuários que abandonam uploads deixam lixo em memória.

## Solution

Combinar três técnicas: Double-Check Locking + RLock para estado + TTL para cleanup automático.

**1. Singleton com Double-Check Locking:**

```python
# Before (broken):
class PixooConnection:
    _instance = None

    def __new__(cls):
        if cls._instance is None:  # Race condition!
            cls._instance = super().__new__(cls)
        return cls._instance

# After (fixed):
import threading

class PixooConnection:
    _instance: Optional["PixooConnection"] = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "PixooConnection":
        if cls._instance is None:
            with cls._instance_lock:
                # Double-check dentro do lock
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._state_lock = threading.RLock()  # RLock para estado
        self._ip: Optional[str] = None
        self._connected: bool = False
```

**2. Properties thread-safe com RLock:**

```python
# Before (broken):
@property
def is_connected(self) -> bool:
    return self._connected  # Leitura não-atômica!

# After (fixed):
@property
def is_connected(self) -> bool:
    with self._state_lock:
        return self._connected

@property
def current_ip(self) -> Optional[str]:
    with self._state_lock:
        return self._ip if self._connected else None
```

**3. UploadManager com TTL automático:**

```python
from dataclasses import dataclass, field
from time import time
from typing import Dict, Any

DEFAULT_TTL = 3600  # 1 hora

@dataclass
class UploadEntry:
    data: Dict[str, Any]
    created_at: float = field(default_factory=time)

    def is_expired(self, ttl: int = DEFAULT_TTL) -> bool:
        return time() - self.created_at > ttl

class UploadManager:
    def __init__(self, ttl: int = DEFAULT_TTL):
        self.ttl = ttl
        self._entries: Dict[str, UploadEntry] = {}
        self._lock = threading.RLock()

    def get(self, upload_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            entry = self._entries.get(upload_id)
            if entry is None:
                return None
            # Auto-cleanup de expirados
            if entry.is_expired(self.ttl):
                self._delete_entry(upload_id, entry)
                return None
            return entry.data

    def cleanup_expired(self) -> int:
        """Remove todas as entradas expiradas."""
        with self._lock:
            expired = [uid for uid, e in self._entries.items()
                      if e.is_expired(self.ttl)]
            for uid in expired:
                self._delete_entry(uid, self._entries[uid])
            return len(expired)
```

**4. Cleanup no shutdown via lifespan:**

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield  # Startup

    # Shutdown cleanup
    conn = get_pixoo_connection()
    if conn.is_connected:
        conn.disconnect()

    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
```

## Why This Works

1. **Double-check locking** garante que apenas uma instância é criada mesmo com múltiplas threads tentando simultaneamente. O primeiro check evita overhead do lock no caso comum.

2. **RLock (reentrant lock)** permite que o mesmo thread adquira o lock múltiplas vezes - necessário quando um método thread-safe chama outro método thread-safe da mesma classe.

3. **TTL automático** garante que entradas abandonadas são limpas eventualmente. O check acontece no `get()`, então entradas expiradas são removidas sob demanda.

4. **Lifespan cleanup** garante que recursos são liberados quando a aplicação termina, evitando arquivos órfãos e conexões abertas.

## Prevention

- **Sempre use locks em singletons FastAPI** - mesmo que pareça "apenas leitura", FastAPI usa threads
- **RLock > Lock** para classes com múltiplos métodos que se chamam
- **TTL obrigatório** para qualquer estado in-memory que cresce com uso
- **Lifespan para cleanup** - nunca confie que o usuário vai limpar recursos
- **Cópia local fora do lock** - para operações longas (ex: HTTP requests), copie o valor e libere o lock antes

```python
def send_command(self, command: dict) -> dict:
    with self._state_lock:
        if not self._connected:
            raise Error("Not connected")
        ip = self._ip  # Cópia local

    # HTTP request FORA do lock
    return requests.post(f"http://{ip}/post", json=command)
```

## Related Issues

- GitHub Issue #8: Race condition in file cleanup
- GitHub Issue #9: Thread safety issues in PixooConnection singleton
- GitHub Issue #13: In-memory upload state has no TTL cleanup

Todos os três foram resolvidos com este padrão combinado.
