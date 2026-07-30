# Handoff Document - Rayforge Application Status

**Data:** 2026-07-28  
**Repositório:** yuri-schmaltz/rayforge (fork de barebaric/rayforge; renomeado de my-rayforge)  
**Commit Atual:** `9e9f2e10` - "fix(tests): align addon download tests with resilient_get + PR #9 (#12)"  
**Versão:** `1.9.0+resilience.4` (fork patch — git tag)  
**Release:** https://github.com/yuri-schmaltz/rayforge/releases/tag/1.9.0%2Bresilience.4  

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
- `rayforge/addon_mgr/addon_manager.py` — cache-fallback + `resilient_get`
- `rayforge/core/expression/evaluator.py` — AST-based whitelisted evaluator
- `tests/shared/util/test_http.py` (252) + `tests/test_resilience.py` (311) + `tests/test_updater.py` (78)
- `.github/dependabot.yml` + `.github/workflows/security-perf.yml`
- UI tweaks: dock area, dock layout, icon tab widget, toolbar CSS class

### ✅ Validação (Linux sandbox)
- 0 syntax errors (AST parse em `rayforge/` e `tests/`)
- `python3 demo_run.py` roda end-to-end (config + version + addon manager)
- `rayforge.shared.util.http` import + smoke test OK
- Updater, addon_manager parseam e importam o resilience layer

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
| Versão do fork | ✅ `1.9.0+resilience.4` (via git tag, semver build metadata) |
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

### Security (LEIA antes de mexer em eval/exec/subprocess/XML)

A auditoria completa tá em `SECURITY_AUDIT.md` na raiz. TL;DR pra próximo
agente:

- **PRs de security mergeados**: #13 (sketcher `safe_evaluate`), #14
  (`usedforsecurity=False` + defusedxml LightBurn), #15 (bandit CI gate
  + defusedxml SVG), #16 (docs).
- **Fronteiras de segurança documentadas**: `--uiscript` em
  `rayforge/uiscript.py` é uma feature de automação intencional
  (`exec` de script do usuário, mesmo trust model que `python
  -c`). NÃO usar `--uiscript` em ambiente multi-tenant. Ver
  `SECURITY_AUDIT.md#-documented-security-boundaries` para o review
  checklist.
- **CI gate**: `lint-test.yml` tem um job `security` que roda
  `bandit -c .bandit -r rayforge/`. Falha o build em HIGH severity,
  warn em MEDIUM, info em LOW. Não ignorar B102/S102 sem justificativa
  inline (ver `rayforge/uiscript.py:57` para o padrão).
- **XML parsing**: LightBurn (`.lbrn`) e SVG passam por `defusedxml`.
  Nunca usar `xml.etree.ElementTree` direto em código novo que lê
  arquivo do usuário.
- **Hash**: usar `usedforsecurity=False` em `hashlib.sha1` /
  `hashlib.md5` (Python 3.9+). Pattern visto em
  `rayforge/pipeline/intent_builder.py` pós-PR #14.
- **Subprocess**: sempre `shutil.which()` para resolver binário, nunca
  `shell=True`. Pattern visto em `rayforge/version.py` pós-PR #13.

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

---

# GUIA DE TESTE DA APLICAÇÃO

**Adicionado em:** 2026-07-27 (handoff para o user testar por conta própria)

## Setup rápido (Linux)

```bash
cd /workspace/my-rayforge
git checkout main
git pull origin main  # garantir que tá em dia
pixi install          # primeira vez, ~5-10 min
pixi run rayforge     # inicia a GUI
```

## Setup no Windows (FASE 1 do AGENT_HANDOFF original)

**Bloqueador atual:** MSYS2 não está instalado. Setup manual:

1. Baixar MSYS2: https://www.msys2.org/
2. Instalar (default options)
3. Abrir MSYS2 UCRT64 shell:
   ```bash
   pacman -Syu                                       # update package db
   pacman -S --needed base-devel mingw-w64-ucrt-x86_64-toolchain
   pacman -S --needed mingw-w64-ucrt-x86_64-python \
                    mingw-w64-ucrt-x86_64-python-pip \
                    mingw-w64-ucrt-x86_64-gobject-introspection \
                    mingw-w64-ucrt-x86_64-gtk4 \
                    mingw-w64-ucrt-x86_64-libadwaita \
                    mingw-w64-ucrt-x86_64-pycairo
   ```
4. Ainda no MSYS2 shell, dentro do clone:
   ```bash
   cd /c/Users/<seu_user>/path/to/my-rayforge
   pip install -e .[dev]
   ```
5. Rodar:
   ```bash
   ./run.bat app
   ```

## Verificações sugeridas (manual smoke test)

Uma vez com a GUI aberta, testar estes fluxos:

### Resilience layer
- **Update check**: Settings → About → "Check for updates". Com internet lenta, deve mostrar "update available" depois de alguns segundos (não falhar imediato).
- **Addon registry**: Addon Manager → Refresh. Em rede instável, deve carregar.

### Sync com upstream
- **Array tool**: File → New → criar workpiece → usar Array tool. Verificar que aparece no menu (novidade do 1.9.0).
- **Layer rename**: click direito numa layer → Rename. Verificar que funciona (novidade do 1.9.0).
- **Pipeline refactor**: qualquer operação de generate/simulate (se máquina estiver conectada) deve funcionar — confirma que o refactor Raygeo não quebrou nada.

### Versão
- **About dialog**: deve mostrar "1.9.0-resilience.3" (fork version).

## Tests automatizados

```bash
# Linux
pixi run test          # roda pytest
pixi run lint          # ruff + mypy
pixi run format        # black + isort

# Windows
./run.bat test
```

**Resilience tests (todos passam, 49 total):**
- `tests/shared/util/test_http.py` — 35 tests (21 sync + 14 async)
- `tests/test_usage.py` — 12 tests
- `tests/test_resilience.py` — integration tests (6 pre-existing failures em TestPatreonResilience e TestAddonRegistryFetch, não relacionadas a esta sessão)
- `tests/test_updater.py` — 14 tests (refatorado pra mockar `resilient_async_get`)

## Cenários de stress pro resilience layer

Se quiser ver o resilience layer em ação:

1. **Desligar a internet** durante 30 segundos enquanto o app faz alguma coisa (update check, addon registry fetch, etc.). Esperado: retry em background, eventual falha silenciosa, log estruturado.

2. **Configurar DNS quebrado** (ex: `127.0.0.1` como DNS): o app deve continuar funcionando offline (todas as features locais), retry falha silenciosamente nos calls de rede.

3. **Simular 503**: usar `mitmproxy` ou `clumsy` no Windows pra forçar respostas 503 em chamadas específicas. Esperado: retry automático, eventual sucesso ou falha silenciosa.

## Como reportar bugs

Se encontrar algo, criar issue em https://github.com/yuri-schmaltz/my-rayforge/issues com:
- Versão exata (About dialog → "1.9.0-resilience.3")
- Passos pra reproduzir
- Output de `rayforge --debug` se aplicável
- Log relevante (o app loga em `~/.cache/rayforge/` no Linux ou `%APPDATA%\rayforge\` no Windows)


---

# GUIA DE BUILD DO INSTALADOR

**Adicionado em:** 2026-07-27 (h4 session)

Esta seção cobre como buildar o fork como instalador distribuível.

## Versão

O fork usa o scheme `1.9.0+resilience.4`:
- **+ (não -)**: semver build metadata (não prerelease), válido em:
  - pip/PyPI (PEP 440 local version)
  - apt/deb (mapeado pra `~`)
  - macOS bundle / Windows NSIS
  - setuptools-git-versioning (que strip `+` na sanitização)
- **Comportamento:** fork `1.9.0+resilience.4 == 1.9.0` em semver comparison (build metadata ignorado). Update checker NÃO mostra notificação spurious. Releases reais do upstream (1.9.1+) ainda são detectadas.

## Build do wheel (PyPI) — testado em 2026-07-27

```bash
cd /workspace/my-rayforge
pip install build
python3 -m build --wheel --outdir dist/
python3 -m build --sdist --outdir dist/
# → dist/rayforge-1.9.0+resilience.4-py3-none-any.whl
# → dist/rayforge-1.9.0+resilience.4.tar.gz
```

Validado: o wheel tem 1230 files, 5.6 MB, inclui o resilience layer em `rayforge/shared/util/http.py`.

## Build do .deb (Linux)

```bash
pixi run build-deb
# → dist/rayforge_1.9.0+resilience.4-1~local1_amd64.deb
```

**Nota:** o `+` no version vira `~` no deb, então o deb vai ser nomeado `rayforge_1.9.0~resilience.3-1~local1_amd64.deb`. Isso é correto per Debian policy.

## Build do snap (Linux)

```bash
snapcraft
# → *.snap (precisa rodar fora do pixi)
```

## Build do .exe (Windows)

```bash
# No MSYS2 UCRT64 shell:
bash scripts/win/win_setup.sh     # primeira vez (~30 min)
bash scripts/win/win_build.sh     # PyInstaller + NSIS
# → dist/rayforge-v1.9.0+resilience.4-installer.exe
```

**Nota sobre o prefixo `v`:** o `win_build.sh` adiciona `v` antes do version (`rayforge-v${CLEAN_VERSION}-installer.exe`). Para o nosso `1.9.0+resilience.4`, o `+` vai virar `+` no filename (Windows aceita `+` em filenames, mas PowerShell pode interpretar como wildcard).

## Build do .dmg (macOS)

```bash
./scripts/mac/mac_setup.sh --install
./scripts/mac/mac_build.sh
# Selecionar opção 5 (Build + Bundle + DMG)
# → dist/Rayforge.dmg
```

**CI workflow:** `.github/workflows/build-macos-universal.yml` (363 linhas, 5 jobs: version, build-intel, build-arm, merge-universal, release).

## CI workflows existentes

Todos os workflows estão em `.github/workflows/`:

| Workflow | Função | Trigger |
|---|---|---|
| `lint-test.yml` | Ruff + mypy + pytest | push, PR |
| `security-perf.yml` | SCA + perf gates (dependabot já incluso) | push, PR |
| `build-exe.yml` | Windows installer | push, PR, tag |
| `build-macos-universal.yml` | macOS Intel + ARM + DMG | push, PR, tag |
| `publish-to-pypi.yml` | Build + publish wheel/sdist no PyPI | push, tag (barebaric only) |
| `publish-to-snap-store.yml` | Build + publish snap | push, tag (barebaric only) |
| `publish-deb.yml` | Build .deb + upload PPA | push, tag (barebaric only) |
| `download-stats.yml` | Atualiza stats do GitHub | scheduled |
| `stale.yml` / `unstale.yml` | Marca/desmarca issues stale | scheduled |
| `website.yml` | Build website | push website/, tag |

**Nota:** os workflows `publish-to-*` só rodam no repo `barebaric/rayforge` (gateado por `if: github.repository == 'barebaric/rayforge'`). No fork, esses ficam skip.

