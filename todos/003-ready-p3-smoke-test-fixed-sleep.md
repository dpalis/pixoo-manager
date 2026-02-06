---
status: resolved
priority: p3
issue_id: "003"
tags: [code-review, quality, testing]
dependencies: []
---

# Substituir sleep fixo por polling no smoke_test.sh

## Problem Statement

O smoke test espera 15 segundos fixos (`sleep $TIMEOUT`) antes de verificar se o app esta rodando. Em maquinas lentas pode nao ser suficiente; em maquinas rapidas, desperdica ~14 segundos. O proprio `app/main.py` ja tem `_wait_for_server()` com polling — o smoke test deveria seguir o mesmo padrao.

## Findings

- `scripts/smoke_test.sh:68` - `sleep "$TIMEOUT"` com TIMEOUT=15
- O app tipicamente inicia em 1-3 segundos
- Em CI ou maquinas mais lentas, 15s pode nao ser suficiente
- `app/main.py:255-270` - `_wait_for_server()` ja implementa polling com curl/socket

## Proposed Solutions

### Option 1: Polling com curl em loop

**Approach:** Substituir `sleep 15` por um loop que faz `curl` a cada 0.5s ate obter resposta HTTP ou atingir timeout.

```bash
ELAPSED=0
while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
    if curl -s -o /dev/null "http://127.0.0.1:$PORT/" 2>/dev/null; then
        break
    fi
    sleep 0.5
    ELAPSED=$((ELAPSED + 1))
done
```

**Pros:**
- Teste termina assim que o app esta pronto (~2s em vez de 15s)
- Mais robusto em ambientes lentos (espera ate o timeout real)
- Consistente com o padrao do _wait_for_server()

**Cons:**
- Ligeiramente mais complexo que um sleep

**Effort:** 10 min

**Risk:** Low

## Recommended Action

## Technical Details

**Affected files:**
- `scripts/smoke_test.sh:66-81` - bloco de startup e verificacao

## Resources

- **PR:** #156
- **Review agents:** architecture-strategist, performance-oracle

## Acceptance Criteria

- [ ] Smoke test usa polling em vez de sleep fixo
- [ ] Timeout maximo mantido (15s)
- [ ] Teste passa em maquina local
- [ ] Output do teste continua claro e informativo

## Work Log

### 2026-02-06 - Identificado na review do PR #156

**By:** Claude Code

**Actions:**
- Identificado por architecture-strategist e performance-oracle
- Comparado com _wait_for_server() em app/main.py como referencia
