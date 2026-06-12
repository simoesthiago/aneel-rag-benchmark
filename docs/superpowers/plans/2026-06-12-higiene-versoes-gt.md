# Higiene De Versoes E Ground Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolver de forma principista o pacote de 8/9 residuais do Grupo A: versoes antigas de PRORET, aliases da mesma versao, fontes relacionadas legitimas e documentacao honesta do residual gt-0017.

**Architecture:** A solucao fica dividida em tres fronteiras. O retriever limpa e restringe o espaco de busca quando a pergunta cita explicitamente um submodulo PRORET. O ground truth aceita apenas fontes juridicamente defensaveis: versao vigente para PRORET 6.8 e REN 1059 como norma alteradora da REN 1000. A auditoria documenta o que a medicao comprova e o que ainda depende de LLM/Cohere.

**Tech Stack:** Python, pytest, pandas, FAISS metadata in-memory, HuggingFace Hub artifacts, OpenAI/Cohere para medicao RAG quando houver quota.

---

## File Structure

- Modify `src/rag/version_hygiene.py`: manter funcoes existentes e adicionar identificacao de alias nao canonico da versao vigente.
- Modify `src/rag/retriever.py`: usar ids nao correntes na higiene de versao e adicionar restricao opt-in para perguntas que citam submodulo exato.
- Modify `src/evaluation/benchmark.py`: expor flag de comparacao para a restricao por submodulo e registrar campos no resultado.
- Modify `tests/test_version_hygiene.py`: cobrir alias de mesma versao e preferencia por id oficial com `aren`/`adsp`.
- Modify `tests/test_rag.py`: cobrir filtro por versao, filtro por submodulo exato e injecao de chunks do submodulo antes do rerank.
- Modify `scripts/apply_gt_version_fixes.py`: manter edicoes limitadas a `gt-0002` e `gt-0004`; validar schema/corpus quando Hub estiver acessivel.
- Modify `scripts/diagnostics/diagnose_version_hygiene.py`: comparar pipeline sem/com higiene expandida.
- Modify `data/evaluation/audit/ROADMAP.md`: registrar F1.5 como fase propria, com criterio de promocao e limites.
- Modify `PROGRESS.md`: registrar estado resumido apos F1.5.

## Task 1: Version Hygiene Canonical IDs

**Files:**
- Modify: `src/rag/version_hygiene.py`
- Test: `tests/test_version_hygiene.py`

- [ ] **Step 1: Write failing tests**

Add tests proving that, when two ids represent the same latest version of a submodule, the id with an official normative suffix is kept and the alias without suffix is excluded.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_version_hygiene.py -q`

Expected: fail because `non_current_document_ids` does not exist yet.

- [ ] **Step 3: Implement minimal canonical-id selection**

Add a function that groups by submodule key, chooses the latest version tuple, then keeps canonical ids for that latest tuple. Prefer ids containing `-aren` or `-adsp`; if none exist, keep all latest ids to avoid arbitrary deletion.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_version_hygiene.py -q`

Expected: all tests pass.

## Task 2: Retriever Source Constraint For Explicit Submodule Queries

**Files:**
- Modify: `src/rag/retriever.py`
- Test: `tests/test_rag.py`

- [ ] **Step 1: Write failing tests**

Add tests showing that a query mentioning `Submodulo 2.1` excludes `2.1A`, excludes older versions, and can inject exact-submodule chunks into the rerank pool.

- [ ] **Step 2: Run tests and verify RED**

Run: `.venv/bin/python -m pytest tests/test_rag.py::test_retriever_restringe_submodulo_explicito -q`

Expected: fail because the flag does not exist yet.

- [ ] **Step 3: Implement minimal retriever behavior**

Add `restrict_to_query_submodulo: bool = False`. When enabled and the query contains a submodule id, keep only candidates whose `document_id` matches that exact id. Before rerank, inject matching metadata rows not already in the pool, respecting `exclude_situacoes` and version hygiene.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `.venv/bin/python -m pytest tests/test_rag.py tests/test_version_hygiene.py -q`

Expected: all tests pass.

## Task 3: Benchmark Wiring And Diagnostics

**Files:**
- Modify: `src/evaluation/benchmark.py`
- Modify: `scripts/diagnostics/diagnose_version_hygiene.py`

- [ ] **Step 1: Add config fields**

Add `restrict_to_query_submodulo` to `StoreConfig`, labels, exclusive comparison modes, retriever factory and result payload.

- [ ] **Step 2: Test config wiring**

Run: `.venv/bin/python -m pytest tests/test_benchmark_rag.py -q`

Expected: existing tests remain green.

## Task 4: Ground Truth Fixes For Legitimate Sources

**Files:**
- Modify: `data/evaluation/ground_truth/aneel_retrieval_50.jsonl`
- Modify: `scripts/apply_gt_version_fixes.py`
- Test: schema validation when possible.

- [ ] **Step 1: Apply only two GT edits**

Apply `gt-0002`: replace PRORET 6.8 v1.9c with v1.10c. Apply `gt-0004`: add REN 1059 as same-group alternative to REN 1000.

- [ ] **Step 2: Validate schema locally**

Run: `.venv/bin/python -m pytest tests/test_ground_truth.py tests/test_matching.py tests/test_metrics.py -q`

Expected: all tests pass.

- [ ] **Step 3: Validate against corpus if Hub access works**

Run: `.venv/bin/python scripts/apply_gt_version_fixes.py`

Expected: GT validado contra corpus. If blocked by network/quota, document blocker and keep schema-local validation.

## Task 5: End-To-End Measurement And Documentation

**Files:**
- Modify: `data/evaluation/audit/ROADMAP.md`
- Modify: `PROGRESS.md`
- Create/update: `data/evaluation/results/rag-50/version_hygiene_pairing.json`

- [ ] **Step 1: Run deterministic unit tests**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: all tests pass.

- [ ] **Step 2: Run paired diagnostic if Cohere/OpenAI quota works**

Run: `.venv/bin/python scripts/diagnostics/diagnose_version_hygiene.py`

Expected: produce saved/broken/hard_broken for the 9 Grupo A cases.

- [ ] **Step 3: Document measured truth**

Update ROADMAP/PROGRESS with the exact status: which of the 9 are resolved, which are improved but still fail, and why `gt-0017` remains residual if still not fixed.

## Self-Review

- Spec coverage: covers the 7 version cases, the `gt-0004` related-norm case, and documents `gt-0017` as residual unless measurement proves otherwise.
- Placeholder scan: no placeholder task is left; each task has files and verification commands.
- Type consistency: new flags are named `restrict_to_query_submodulo` everywhere.
