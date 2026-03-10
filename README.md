# KOSMOS Agent — Firecracker MicroVM Sandbox

Motor cognitivo autônomo com execução isolada em microVMs Firecracker.

## Arquitetura

```
USUÁRIO
   ↓
┌──────────────────────────┐
│  Tree of Thoughts (ToT)  │  ← 4 branches paralelos
│  ┌────────┐ ┌────────┐   │
│  │Proposer│ │Proposer│   │  ← Mixture of Agents
│  └────┬───┘ └───┬────┘   │
│       └─────┬───┘        │
│       ┌─────┴─────┐      │
│       │  Reviewer  │     │  ← Score + Ranking
│       └─────┬─────┘      │
└─────────────┼────────────┘
              ↓
┌──────────────────────────┐
│      Tool Router         │
│   python → MicroVM       │  ← Firecracker Sandbox
│   python_local → Jupyter │  ← Kernel local
└─────────────┬────────────┘
              ↓
┌──────────────────────────┐
│  Firecracker MicroVM     │
│  ┌──────────────────┐    │
│  │ KVM Isolation    │    │
│  │ Seccomp Filters  │    │
│  │ Jailer (cgroups) │    │
│  │ Vsock I/O        │    │
│  └──────────────────┘    │
└─────────────┬────────────┘
              ↓
┌──────────────────────────┐
│      Reflexion           │
│  retry → refine →        │  ← Escalação de estratégia
│  decompose → pivot →     │
│  abort                   │
└─────────────┬────────────┘
              ↓
┌──────────────────────────┐
│  Memória Episódica       │
│  FAISS IndexFlatL2(128)  │  ← Busca por similaridade  
└──────────────────────────┘
```

## Pré-requisitos

### Para sandbox completo (Firecracker)
- Linux com KVM habilitado (`/dev/kvm`)
- Binário Firecracker compilado
- Kernel image + rootfs ext4
- Python 3.10+ no guest

### Para modo local (fallback)
- Python 3.10+
- Dependências: `pip install -r requirements.txt`

## Setup

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar com tarefa
python main.py --task "Calcular fibonacci de 10"

# Executar com opções
python main.py --task "Ordenar lista" --max-iter 8 --branches 6

# Modo silencioso
python main.py --task "2 + 2" --quiet
```

## Módulos

| Módulo | Função |
|--------|--------|
| `main.py` | Motor cognitivo KosmosEngine |
| `planner_tot.py` | Tree of Thoughts paralelo |
| `agents.py` | Proposer + Reviewer (Mixture of Agents) |
| `tool_router.py` | Roteador de ferramentas |
| `microvm_sandbox.py` | Sandbox Firecracker (API + vsock) |
| `microvm_config.py` | Configuração de microVMs |
| `jupyter_executor.py` | Executor Jupyter real |
| `reflexion.py` | Crítico multi-passo |
| `memory.py` | Memória episódica FAISS |

## Comunicação Host ↔ Guest (Vsock)

```
Host (AF_UNIX)          Firecracker          Guest (AF_VSOCK)
    │                       │                       │
    ├── connect(v.sock) ───►│                       │
    ├── "CONNECT 5005\n" ──►│──► forward ──────────►│
    │◄── "OK 1073741824\n" ─┤                       │
    ├── [4 bytes len] ─────►│──► forward ──────────►│ execute(code)
    ├── [JSON payload] ────►│──► forward ──────────►│
    │◄── [4 bytes len] ─────┤◄── forward ◄──────────┤
    │◄── [JSON result] ─────┤◄── forward ◄──────────┤ return(result)
```

## Segurança (Defense in Depth)

1. **KVM** — isolamento de hardware
2. **Seccomp** — whitelist de syscalls
3. **Jailer** — cgroups + namespaces + chroot
4. **Rate Limiting** — controle de I/O
5. **Vsock** — canal dedicado (sem rede compartilhada)
