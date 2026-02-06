---
status: resolved
priority: p3
issue_id: "002"
tags: [code-review, performance, quality]
dependencies: []
---

# Eliminar re-parsing de arquivos no validate_imports.py

## Problem Statement

No bloco de reporting de pacotes faltantes, `extract_imports_from_file()` e chamada novamente para cada arquivo Python, para cada pacote faltante. Isso re-parseia o AST de todos os arquivos quando os dados ja foram coletados na primeira passagem.

## Findings

- `scripts/validate_imports.py:115-124` - loop aninhado que re-parseia todos os .py
- Complexidade: O(N*M) onde N = arquivos e M = pacotes faltantes
- Na primeira passagem (linhas 83-91), os imports ja sao coletados mas descartados sem mapear para os arquivos de origem
- Para o tamanho atual do projeto (~20 arquivos .py), o impacto em performance e negligivel
- O problema e mais de design/legibilidade do que de performance

## Proposed Solutions

### Option 1: Coletar mapeamento import->arquivos na 1a passagem

**Approach:** Construir `dict[str, set[Path]]` mapeando cada import para os arquivos que o usam, na mesma iteracao que ja coleta `all_imports`.

**Pros:**
- Elimina re-parsing completamente
- Codigo mais claro e direto
- ~8 linhas removidas

**Cons:**
- Nenhum significativo

**Effort:** 15 min

**Risk:** Low

## Recommended Action

## Technical Details

**Affected files:**
- `scripts/validate_imports.py:83-91` - primeira passagem (adicionar coleta)
- `scripts/validate_imports.py:110-125` - bloco de reporting (simplificar)

## Resources

- **PR:** #156
- **Review agents:** code-simplicity-reviewer, kieran-python-reviewer

## Acceptance Criteria

- [ ] `extract_imports_from_file()` chamada apenas 1x por arquivo
- [ ] Output do script identico ao anterior
- [ ] Script continua passando quando executado

## Work Log

### 2026-02-06 - Identificado na review do PR #156

**By:** Claude Code

**Actions:**
- Identificado por code-simplicity-reviewer e kieran-python-reviewer
- Estimativa de reducao: ~8 LOC
