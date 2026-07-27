# Handoff Document - Rayforge Application Status

**Data:** 2026-07-27  
**Repositório:** yuri-schmaltz/my-rayforge (fork de barebaric/rayforge)  
**Commit Atual:** `18dd174f` - "Sync upstream 1.9.0 → 1.9.0+target-architecture (2026-07-27) (#4)"  
**Versão:** `1.9.0-resilience.3` (fork patch — git tag)  

---

## O QUE FOI FEITO (atualizado em 2026-07-27)

### ✅ Sync upstream 1.9.0 → 1.9.0+target-architecture (FASE 6)
- **Merge de 14 commits do upstream**, incluindo o `target-architecture` PR #319 (refactor massivo do pipeline pra raygeo intent orchestration)
- 157 files: +5673 / -21125 (majoritariamente testes reescritos contra a nova arquitetura)
- **Zero conflitos** — áreas ortogonais (resilience layer não toca pipeline)
- PR: https://github.com/yuri-schmaltz/my-rayforge/pull/4
- SHA: `18dd174f`
- Tudo do upstream novo no fork: pipeline refactor, raygeo 1.25.0, removido SHM-era, etc.
- Tag bumped: `1.9.0-resilience.1` → `.2` → `.3` (cada PR de resilience marca nova tag)

### ✅ Async resilience layer (PR #3 — merged)
- **`rayforge/shared/util/http.py` agora tem 4 helpers** (não 2):
  - `resilient_get` / `resilient_post` (sync, urllib)
  - `resilient_async_get` / `resilient_async_post` (async, aiohttp)
- **`rayforge/updater.py` refatorado**: usa `resilient_async_get` em vez de retry loop inline do aiohttp
- 11 testes novos pra async helpers (test_total 35 = 21 sync http + 14 async http + 14 updater)
- Removido: `MAX_FETCH_ATTEMPTS`, `FETCH_BACKOFF_SECONDS`, `RETRYABLE_HTTP_STATUSES` do updater (concentrados no util)
- PR: https://github.com/yuri-schmaltz/my-rayforge/pull/3

### ✅ Sync com upstream 1.8.4 → 1.9.0 (FASE 5)
- **Merge de `barebaric/rayforge` 1.8.4 → 1.9.0**
  - 31 commits do upstream integrados (138 files, +8228 / -2471)
  - **Zero conflitos** — áreas de mudança ortogonais
  - PR: https://github.com/yuri-schmaltz/my-rayforge/pull/1
  - SHA: `d92dab6a`
  - Local main fast-forwarded para `d92dab6a`
- **Tudo do 1.9.0 já no fork:**
  - Array / Pattern tool (Grid, Point Rotation, Circular) + 3 screenshots
  - Layer/step rename dialog, drag-and-drop reorder fix
  - Dot width correction (LightBurn import)
  - V4L camera module + persistent /dev/v4l/by-id/
  - G-code encoder migration pra Raygeo
  - Raygeo 1.24.0, GitPython 3.1.51, pypdf 6.13.3
  - 16 outros bugfixes

### ✅ Resilience layer preservado no merge
Todos os arquivos do commit `ec792907` ("Enhance UI and Resilience Features") sobreviveram o merge intactos:
- `rayforge/shared/util/http.py` (226 linhas) — `resilient_get`/`resilient_post` com retry+backoff
- `rayforge/updater.py` — retry logic no AppUpdateChecker (3 tentativas, 0.75s backoff)
- `rayforge/license/gumroad_provider.py` + `patreon_provider.py` — usam `resilient_get`
- `rayforge/addon_mgr/addon_manager.py` — cache-fallback + `resilient_get`
- `rayforge/core/expression/evaluator.py` — AST-based whitelisted evaluator
- `tests/shared/util/test_http.py` (252) + `tests/test_resilience.py` (311) + `tests/test_updater.py` (78)
- `.github/dependabot.yml` + `.github/workflows/security-perf.yml`
- UI tweaks: dock area, dock layout, icon tab widget, toolbar CSS class

### ✅ Validação (Linux sandbox)
- 0 syntax errors (AST parse em `rayforge/` e `tests/`)
- `python3 demo_run.py` roda end-to-end (config + version + addon manager)
- `rayforge.shared.util.http` import + smoke test OK
- Updater, license providers, addon_manager parseam e importam o resilience layer

### ✅ Git & Versionamento (resolvido anteriormente)
- Push via HTTPS com `GITHUB_PUSH_TOKEN` (sandbox Linux)
- Push via SSH porta 443 + ed25519 (Windows do usuário — porta 22 bloqueada)
- PAT ativo: `<configurado em env GITHUB_PUSH_TOKEN>`

### ✅ Demo / Handoff (commit `b0f3ac7a`)
- `AGENT_HANDOFF.md` (este arquivo)
- `demo_run.py` — smoke test sem precisar de GTK/raygeo compilado

---

## ESTADO ATUAL

| Item | Estado |
|------|--------|
| Sincronização com upstream | ✅ Em dia (1.9.0+target-architecture, 2026-07-27) |
| Versão do fork | ✅ `1.9.0-resilience.3` (via git tag, semver prerelease) |
| Resilience layer | ✅ HTTP util (sync+async) + 4 call sites refatorados + 35 tests |
| PRs upstream em flight | `barebaric/rayforge#321` (resilient http util — OPEN) |
| Resilience layer local | ✅ Preservado, testado |
| Code syntax | ✅ Limpo |
| Smoke test (`demo_run.py`) | ✅ Passa |
| GUI em Linux | ✅ Roda (precisa GTK4 + raygeo via pixi) |
| GUI em Windows | ❌ Bloqueado (MSYS2 não instalado) |
| Suite de tests completa | ⚠️ Não rodada pós-merge (35 resilience tests OK local) |

---

## O QUE PRECISA SER FEITO

### FASE 1: Resolver GUI em Windows (CRÍTICO se quiser testar localmente)

**Tarefa 1.1 - Instalar MSYS2 (Admin Required)**
- Status: BLOQUEADO — requer privilégios administrativos
- Comando: `winget install -e --id MSYS2.MSYS2` (falhou com erro 0x8a15000f)
- Alternativa manual: Download de https://www.msys2.org/ e execução do instalador
- **Impacto:** Desbloqueará compilação de todas as extensões nativas (PyGObject, pycairo, raygeo)

**Tarefa 1.2 - Compilar e Instalar Dependências**
- Pré-requisito: MSYS2 instalado
- Comandos:
  ```powershell
  .\run.bat setup      # Configura ambiente MSYS2
  .\run.bat build      # Compila PyGObject, raygeo, pycairo, etc.
  ```
- **Tempo estimado:** 15-30 minutos (primeira execução)
- **Validação:** `pip list | findstr PyGObject raygeo`

### FASE 2: Execução da Aplicação (depende da Fase 1)

**Tarefa 2.1 - Iniciar Aplicação GUI**
- Comando: `.\run.bat app`
- Esperado: Janela GTK4 abre com interface completa do 1.9.0
- **Validação:** GUI renderiza sem erros; Array tool aparece no menu

**Tarefa 2.2 - Validação de Funcionalidades**
- Testar workflows principais:
  - [ ] Carregamento de projetos (.ryp)
  - [ ] Edição de workpieces
  - [ ] Array tool (novidade 1.9.0)
  - [ ] Layer/step rename (novidade 1.9.0)
  - [ ] Renderização de máquinas
  - [ ] Simulação de corte
  - [ ] Resiliência de rede (desligar internet e tentar update check)

### FASE 3: Testes & Qualidade (Linux-first)

**Tarefa 3.1 - Rodar suite de tests em Linux (sandbox)**
```bash
# No Linux sandbox
cd /workspace/my-rayforge
pixi install          # primeira vez, pode demorar
pixi run test         # roda pytest
pixi run lint         # ruff/flake8
pixi run format       # black
```
- Se algum teste falhar especificamente por causa do merge, investigar e corrigir
- Esperado: ~1200+ tests (com os novos test_array_cmd, test_array_strategies, test_v4l, test_array_dialog etc.)

**Tarefa 3.2 - Rodar suite em Windows (pós-Fase 1)**
- Comando: `.\run.bat test`
- Esperado: mesma cobertura que Linux

### FASE 4: Versioning (Opcional)

**Tarefa 4.1 - Decidir estratégia de versão**
- O fork tá em 1.9.0 (em sync com upstream)
- Se quiser marcar o fork com release próprio: `python scripts/bump_version.py small`
- Mas como o fork é só sync + resilience layer (não um release independente), talvez pular

### FASE 5: PR pro upstream (OPCIONAL mas recomendado) — ✅ FEITO

**Tarefa 5.1 - Submeter resilience layer pro `barebaric/rayforge`** ✅ ENVIADO
- PR #320 (sync only) foi criado e depois **fechado em favor de #321** (consolidação)
- PR #321 aberto: https://github.com/barebaric/rayforge/pull/321
  - Conteúdo: `rayforge/shared/util/http.py` (4 helpers sync+async) + tests + refactor do `updater.py`
  - Status: open, mergeable, sem reviewers ainda
  - Reviewer: @barebaric (mantenedor upstream)
- Próximos passos quando aprovar:
  1. Cherry-pick do upstream `feature/resilient-async-http` branch pro fork
  2. Rebase linear do fork's `main` (stack: 1 → 2 → 3 → 4)
  3. Bump da tag pra `1.9.0-resilience.4`

### FASE 6: Sync com upstream (RECORRENTE) — ✅ FEITO

**Tarefa 6.1 - Sincronizar com upstream periodicamente**
- Workflow: criar worktree `feature/sync-upstream-YYYY-MM-DD` → `git merge upstream/main` → push → abrir PR → merge
- Último sync: 2026-07-27 (PR #4) — 14 commits do upstream, incluindo `target-architecture` (refactor massivo do pipeline)
- Resultado: fork tá em 1.9.0+target-architecture com resilience layer preservado

---

## BLOCKERS ATUAIS

| Blocker | Severidade | Solução |
|---------|-----------|---------|
| MSYS2 não instalado (Windows) | 🟡 MÉDIA (apenas pra GUI local) | Requer admin ou download manual |
| PyGObject não compilado (Windows) | 🟡 MÉDIA | Depende de MSYS2 |
| raygeo não compilado (Windows) | 🟡 MÉDIA | Depende de MSYS2 + Rust |
| conftest.py importa gi | 🟢 BAIXA | Será resolvido com PyGObject |
| SSH porta 22 bloqueada (Windows) | ✅ RESOLVIDO | Git usa SSH porta 443 + ed25519 |
| Push no sandbox Linux | ✅ RESOLVIDO | `GITHUB_PUSH_TOKEN` via HTTPS |
| Fork atrás do upstream | ✅ RESOLVIDO | Sync 1.8.4 → 1.9.0 (PR #1 merged) |

---

## CHECKLIST PARA PRÓXIMO AGENTE

**Antes de começar:**
- [ ] `git fetch origin && git status` — confirmar que main está em `d92dab6a`
- [ ] `python3 demo_run.py` — confirmar smoke test passa
- [ ] Se for trabalhar em feature: criar worktree em `.worktrees/feature-xxx/` (nunca commitar direto em main)
- [ ] Se for no Windows: confirmar SSH config (porta 443) está ativo

**Executar conforme necessário:**
- [ ] (Windows) FASE 1: Resolver MSYS2
- [ ] (Windows) FASE 2: `.\run.bat app` e validar GUI do 1.9.0
- [ ] (Linux ou Windows) FASE 3: `pixi run test` ou `.\run.bat test`
- [ ] (Opcional) FASE 5: PR do resilience layer pro upstream

---

## NOTAS TÉCNICAS

### Estrutura do Projeto (atualizada 1.9.0)
```
rayforge/
  ├── app.py                       # Entry point GUI
  ├── config.py                    # ✓ Loads sem deps
  ├── version.py                   # ✓ Loads sem deps
  ├── core/                        # Doc, WorkPiece, Step, Layer, Stock, Material
  │   ├── expression/              # AST-based whitelisted evaluator (resilience patch)
  │   ├── step.py                  # Workflow step definitions
  │   ├── doc.py
  │   └── ...
  ├── machine/                     # Drivers + transport
  │   ├── driver/                  # grbl, marlin, octoprint, ruida, smoothie
  │   ├── transport/               # serial, http, telnet, udp, websocket
  │   ├── models/                  # machine, laser, kinematics
  │   └── device/                  # profiles + manager
  ├── pipeline/                    # DAG de estágios
  │   ├── stage/                   # step/workpiece/job runners
  │   ├── assembler/               # registry (substituiu OpsProducer)
  │   ├── encoder/                 # gcode, cairo, rust_helpers
  │   └── transformer/
  ├── addon_mgr/                   # Plugin system (com cache-fallback)
  ├── camera/                      # v4l.py novo em 1.9.0
  ├── doceditor/                   # editor + array/ (novo 1.9.0)
  ├── license/                     # Gumroad, Patreon (resilientes)
  ├── shared/util/                 # http.py (resilience), localized, versioning
  └── ui_gtk/                      # GTK4 GUI
```

### Comandos Úteis

**Windows (PowerShell):**
```powershell
# Verificar environment Python
& "C:/Program Files/Python312/python.exe" --version

# Listar packages instalados
& "C:/Program Files/Python312/python.exe" -m pip list

# Smoke test (sem deps nativas)
& "C:/Program Files/Python312/python.exe" demo_run.py

# Build + GUI (requer MSYS2)
.\run.bat setup
.\run.bat build
.\run.bat app
.\run.bat test
```

**Linux (sandbox):**
```bash
cd /workspace/my-rayforge
python3 demo_run.py                    # smoke test
pixi install                           # primeira vez
pixi run test                          # pytest
pixi run lint                          # ruff + mypy
pixi run format                        # black + isort
pixi run rayforge                      # roda GUI (precisa GTK4)
```

### Build System
- **Linux:** `pixi.toml` (ambiente conda) — funciona no sandbox
- **Windows:** `run.bat` (dispatcher MSYS2 bash) — bloqueado
- **Geral:** `pyproject.toml` (setuptools + dynamic versioning)

### Git Remotes
```bash
origin    = https://github.com/yuri-schmaltz/my-rayforge.git  (seu fork)
upstream  = https://github.com/barebaric/rayforge.git          (original)
```

### Auth (Sandbox Linux)
```bash
# Push via HTTPS com PAT
TOKEN=$(env | grep "^GITHUB_PUSH_TOKEN=" | cut -d= -f2)
git remote set-url origin "https://x-access-token:${TOKEN}@github.com/yuri-schmaltz/my-rayforge.git"
git push -u origin <branch>
```
> ⚠️ Sempre rodar `git remote set-url origin "https://x-access-token:..."` antes de push, ou configurar cleanup pós-push. O memory_append tem o padrão completo.

### Auth (Windows User)
- SSH config em `~/.ssh/config` mapeia `github.com` → `ssh.github.com:443`
- Chave: ed25519
- Git global: `core.sshCommand = "C:/Windows/System32/OpenSSH/ssh.exe -F C:/Users/u60897/.ssh/config"`
- Motivo: porta 22 bloqueada na rede do usuário

---

## CONTEXTO PARA DECISÕES

**Por que MSYS2 é necessário?**
- Windows não tem compilador C por padrão
- PyGObject, pycairo, raygeo precisam compilar extensões nativas
- Alternativas: Visual Studio Build Tools (mais pesado) ou MSYS2 (mais leve)

**Por que o resilience layer é "puro"?**
- `rayforge/shared/util/http.py` só usa `urllib.request` (stdlib) + `time.sleep`
- Zero deps externas, sync, retry puro com backoff exponencial
- Ideal pra contribuir pro upstream (zero risco de conflito de dependências)

**Por que o merge foi tão limpo?**
- Upstream 1.9.0 foca em features (Array tool, layer rename, V4L, etc.)
- Patch local foca em resiliência (HTTP retry, AST eval, CI)
- Áreas ortogonais → auto-merge sem conflitos

**Status de Conhecimento do Agente Anterior (2026-07-26):**
- ✅ Git authentication (Linux + Windows)
- ✅ Code structure validada
- ✅ Sincronização com upstream 1.9.0
- ✅ Merge limpo sem conflitos
- ❌ GUI em Windows ainda não testada (MSYS2 blocker)
- ⚠️ Próxima tarefa opcional: PR do resilience layer pro upstream

---

**Gerado por:** Session 2026-07-26 (Mavis agent)  
**Para:** Próximo agente ou continuação direta do user  
**Leitura recomendada antes de:**
- Trabalhar em feature nova (criar worktree)
- Mexer em build/deps (validar Phase 1)
- Submeter PR pro upstream
- Fazer push (validar auth setup)
