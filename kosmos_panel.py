"""
KOSMOS Agent — Painel de Controle Premium v2.5
===============================================
Melhorias v2.5:
  - Input responsivo (Enter envia, Shift+Enter nova linha)
  - 3 temas: Dark Premium, Clear Apple, Dourado Galáxia
  - Detecção de hardware na inicialização (CPU, RAM, modo recomendado)
  - Boot Panel com presets detalhados
  - Identidade CNGSM KOSMOS
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import json
import os
import time
import threading
import sys
import queue
import platform
import subprocess
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from main import KosmosEngine, BANNER
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from main import KosmosEngine, BANNER


# ══════════════════════════════════════════════════════════════════
# TEMAS
# ══════════════════════════════════════════════════════════════════

THEMES = {
    "🌑 Dark Premium": {
        "bg_primary":    "#0d0f14",
        "bg_secondary":  "#141720",
        "bg_card":       "#1a1e2a",
        "bg_input":      "#1f2335",
        "accent":        "#7c6af7",
        "accent_green":  "#2dd4a0",
        "accent_red":    "#f76a6a",
        "accent_yellow": "#f7c76a",
        "text_primary":  "#e8eaf0",
        "text_secondary":"#7b8099",
        "text_muted":    "#454d66",
        "border":        "#252a3d",
        "user_bubble":   "#1e2540",
        "bot_bubble":    "#171c2e",
        "system_text":   "#454d66",
        "success":       "#2dd4a0",
        "error":         "#f76a6a",
        "warning":       "#f7c76a",
        "thinking":      "#7c6af7",
        "send_btn":      "#7c6af7",
        "send_fg":       "#ffffff",
    },
    "☀️ Clear Apple": {
        "bg_primary":    "#f5f5f7",
        "bg_secondary":  "#ffffff",
        "bg_card":       "#fafafa",
        "bg_input":      "#ffffff",
        "accent":        "#0071e3",
        "accent_green":  "#28a745",
        "accent_red":    "#dc3545",
        "accent_yellow": "#fd7e14",
        "text_primary":  "#1d1d1f",
        "text_secondary":"#6e6e73",
        "text_muted":    "#aeaeb2",
        "border":        "#d2d2d7",
        "user_bubble":   "#e8f0fe",
        "bot_bubble":    "#f0f0f5",
        "system_text":   "#aeaeb2",
        "success":       "#28a745",
        "error":         "#dc3545",
        "warning":       "#fd7e14",
        "thinking":      "#0071e3",
        "send_btn":      "#0071e3",
        "send_fg":       "#ffffff",
    },
    "✨ Dourado Galáxia": {
        "bg_primary":    "#0a0806",
        "bg_secondary":  "#120e09",
        "bg_card":       "#1a1510",
        "bg_input":      "#211a12",
        "accent":        "#d4a017",
        "accent_green":  "#c8b560",
        "accent_red":    "#e05c3a",
        "accent_yellow": "#f0c040",
        "text_primary":  "#f5e6c8",
        "text_secondary":"#a08050",
        "text_muted":    "#5a4020",
        "border":        "#2e2010",
        "user_bubble":   "#1e1608",
        "bot_bubble":    "#160e04",
        "system_text":   "#5a4020",
        "success":       "#c8b560",
        "error":         "#e05c3a",
        "warning":       "#f0c040",
        "thinking":      "#d4a017",
        "send_btn":      "#d4a017",
        "send_fg":       "#0a0806",
    },
}

ACTIVE_THEME = "🌑 Dark Premium"
COLORS = THEMES[ACTIVE_THEME]

FONT_MONO  = ("Consolas", 10)
FONT_BODY  = ("Segoe UI", 11)
FONT_SMALL = ("Segoe UI", 9)
FONT_BOLD  = ("Segoe UI Semibold", 11)
FONT_TITLE = ("Segoe UI Semibold", 13)


# ══════════════════════════════════════════════════════════════════
# HARDWARE DETECTION
# ══════════════════════════════════════════════════════════════════

def detect_hardware() -> dict:
    """Detecta specs do PC e retorna recomendação de modo."""
    info = {
        "cpu": "Desconhecido",
        "ram_gb": 4,
        "cores": 2,
        "platform": platform.system(),
        "python": platform.python_version(),
        "kvm": os.path.exists("/dev/kvm"),
        "docker": False,
        "recommended_mode": "💰 Econômico",
        "recommended_branches": 1,
        "recommended_iterations": 2,
        "alert": "",
    }

    # CPU
    try:
        if platform.system() == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            info["cpu"] = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
        else:
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        info["cpu"] = line.split(":")[1].strip()
                        break
    except Exception:
        pass

    # RAM
    try:
        import psutil
        info["ram_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)
        info["cores"]  = psutil.cpu_count(logical=False) or 2
    except ImportError:
        try:
            if platform.system() == "Windows":
                out = subprocess.check_output(
                    ["wmic", "computersystem", "get", "TotalPhysicalMemory"],
                    capture_output=False, text=True
                )
                lines = [l.strip() for l in out.strip().split('\n') if l.strip().isdigit()]
                if lines:
                    info["ram_gb"] = round(int(lines[0]) / (1024**3), 1)
        except Exception:
            pass

    # Docker
    try:
        r = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
        info["docker"] = r.returncode == 0
    except Exception:
        pass

    # Recomendação baseada em RAM e cores
    ram = info["ram_gb"]
    cores = info["cores"]

    if ram >= 16 and cores >= 6:
        info["recommended_mode"] = "🚀 Turbo"
        info["recommended_branches"] = 4
        info["recommended_iterations"] = 6
        info["alert"] = "Hardware excelente — Turbo recomendado"
    elif ram >= 8 and cores >= 4:
        info["recommended_mode"] = "🔬 Cientista"
        info["recommended_branches"] = 2
        info["recommended_iterations"] = 4
        info["alert"] = "Hardware bom — Cientista recomendado"
    elif ram >= 6:
        info["recommended_mode"] = "⚡ Auto-Dev"
        info["recommended_branches"] = 1
        info["recommended_iterations"] = 5
        info["alert"] = "Hardware médio — Auto-Dev recomendado"
    else:
        info["recommended_mode"] = "💰 Econômico"
        info["recommended_branches"] = 1
        info["recommended_iterations"] = 2
        info["alert"] = f"RAM limitada ({ram}GB) — Econômico recomendado para estabilidade"

    return info


# ══════════════════════════════════════════════════════════════════
# BOOT PANEL
# ══════════════════════════════════════════════════════════════════

class BootPanel:
    """
    Painel de inicialização — detecta hardware e permite configurar
    parâmetros antes de abrir o chat principal.
    """

    BOOT_MODES = {
        "⚡ Auto-Dev": {
            "description": "Desenvolvimento autônomo e correção de código. Ideal para tarefas técnicas do dia a dia.",
            "branches": 1, "max_iterations": 5,
            "tot": False, "reflexion": True, "economy": False,
        },
        "🔬 Cientista": {
            "description": "O agente age como pesquisador: Hipótese → Experimento → Análise → Relatório.",
            "branches": 2, "max_iterations": 4,
            "tot": True, "reflexion": True, "economy": False,
        },
        "🚀 Turbo": {
            "description": "Máxima capacidade de raciocínio. Múltiplos caminhos paralelos. Requer hardware bom.",
            "branches": 4, "max_iterations": 6,
            "tot": True, "reflexion": True, "economy": False,
        },
        "💰 Econômico": {
            "description": "Minimiza custo de API e uso de RAM. Raciocínio linear. Ideal para PCs mais modestos.",
            "branches": 1, "max_iterations": 2,
            "tot": False, "reflexion": False, "economy": True,
        },
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.result = None
        self.hw = {}

        self.root.title("KOSMOS KOSMOS v2.5 — Inicialização")
        self.root.geometry("680x620")
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg_primary"])

        self._build_ui()
        threading.Thread(target=self._load_hardware, daemon=True).start()

    def _build_ui(self):
        C = COLORS

        # Header
        hdr = tk.Frame(self.root, bg=C["bg_secondary"], height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="◈ KOSMOS KOSMOS", font=("Consolas", 16, "bold"),
                 bg=C["bg_secondary"], fg=C["accent"]).pack(side="left", padx=20, pady=12)
        tk.Label(hdr, text="v2.5  |  CNGSM — Cloves Nascimento",
                 font=FONT_SMALL, bg=C["bg_secondary"], fg=C["text_muted"]).pack(side="left")

        body = tk.Frame(self.root, bg=C["bg_primary"])
        body.pack(fill="both", expand=True, padx=24, pady=16)

        # Hardware info
        hw_frame = tk.LabelFrame(body, text=" Configuração do Sistema Detectada ",
                                  bg=C["bg_secondary"], fg=C["text_muted"],
                                  font=FONT_SMALL, bd=1, relief="flat")
        hw_frame.pack(fill="x", pady=(0, 12))

        self.hw_cpu_lbl    = tk.Label(hw_frame, text="CPU: detectando...", font=FONT_SMALL,
                                      bg=C["bg_secondary"], fg=C["text_secondary"], anchor="w")
        self.hw_cpu_lbl.pack(fill="x", padx=12, pady=(8, 2))
        self.hw_ram_lbl    = tk.Label(hw_frame, text="RAM: detectando...", font=FONT_SMALL,
                                      bg=C["bg_secondary"], fg=C["text_secondary"], anchor="w")
        self.hw_ram_lbl.pack(fill="x", padx=12, pady=2)
        self.hw_alert_lbl  = tk.Label(hw_frame, text="Analisando...", font=FONT_SMALL,
                                       bg=C["bg_secondary"], fg=C["accent_yellow"], anchor="w")
        self.hw_alert_lbl.pack(fill="x", padx=12, pady=(2, 8))

        # Modo
        mode_frame = tk.LabelFrame(body, text=" Modo de Operação ",
                                    bg=C["bg_secondary"], fg=C["text_muted"],
                                    font=FONT_SMALL, bd=1, relief="flat")
        mode_frame.pack(fill="x", pady=(0, 12))

        self.mode_var = tk.StringVar(value="⚡ Auto-Dev")
        btn_row = tk.Frame(mode_frame, bg=C["bg_secondary"])
        btn_row.pack(fill="x", padx=12, pady=8)

        for m in self.BOOT_MODES:
            rb = tk.Radiobutton(btn_row, text=m, variable=self.mode_var,
                                value=m, command=self._on_mode,
                                bg=C["bg_secondary"], fg=C["text_primary"],
                                selectcolor=C["bg_card"], activebackground=C["bg_secondary"],
                                font=FONT_BODY)
            rb.pack(side="left", padx=8)

        self.mode_desc = tk.Label(mode_frame, text=self.BOOT_MODES["⚡ Auto-Dev"]["description"],
                                   font=FONT_SMALL, bg=C["bg_secondary"], fg=C["text_secondary"],
                                   wraplength=600, anchor="w", justify="left")
        self.mode_desc.pack(fill="x", padx=12, pady=(0, 8))

        # Configurações avançadas
        adv_frame = tk.LabelFrame(body, text=" Configurações Avançadas (opcional) ",
                                   bg=C["bg_secondary"], fg=C["text_muted"],
                                   font=FONT_SMALL, bd=1, relief="flat")
        adv_frame.pack(fill="x", pady=(0, 12))

        adv_grid = tk.Frame(adv_frame, bg=C["bg_secondary"])
        adv_grid.pack(fill="x", padx=12, pady=8)

        self.adv_vars = {
            "branches":       tk.StringVar(value="1"),
            "max_iterations": tk.StringVar(value="5"),
        }

        labels = [("Branches (ToT):", "branches"), ("Max Iterações:", "max_iterations")]
        for i, (lbl, key) in enumerate(labels):
            tk.Label(adv_grid, text=lbl, font=FONT_SMALL,
                     bg=C["bg_secondary"], fg=C["text_secondary"]).grid(
                row=0, column=i*2, sticky="e", padx=(0, 6))
            e = tk.Entry(adv_grid, textvariable=self.adv_vars[key], width=6,
                         font=FONT_MONO, bg=C["bg_input"],
                         fg=C["text_primary"], insertbackground=C["accent"], bd=0,
                         highlightthickness=1, highlightcolor=C["accent"],
                         highlightbackground=C["border"])
            e.grid(row=0, column=i*2+1, sticky="w", padx=(0, 24))

        # Tema
        theme_frame = tk.LabelFrame(body, text=" Tema Visual ",
                                     bg=C["bg_secondary"], fg=C["text_muted"],
                                     font=FONT_SMALL, bd=1, relief="flat")
        theme_frame.pack(fill="x", pady=(0, 12))

        self.theme_var = tk.StringVar(value="🌑 Dark Premium")
        th_row = tk.Frame(theme_frame, bg=C["bg_secondary"])
        th_row.pack(fill="x", padx=12, pady=8)
        for t in THEMES:
            rb = tk.Radiobutton(th_row, text=t, variable=self.theme_var, value=t,
                                bg=C["bg_secondary"], fg=C["text_primary"],
                                selectcolor=C["bg_card"], activebackground=C["bg_secondary"],
                                font=FONT_BODY)
            rb.pack(side="left", padx=8)

        # Botão iniciar
        self.start_btn = tk.Button(
            body, text="▶  INICIAR KOSMOS",
            font=("Segoe UI Semibold", 12),
            bg=C["accent"], fg=C["send_fg"],
            activebackground=C["thinking"],
            relief="flat", bd=0, cursor="hand2",
            command=self._start
        )
        self.start_btn.pack(fill="x", ipady=12, pady=(8, 0))

    def _on_mode(self):
        m = self.mode_var.get()
        cfg = self.BOOT_MODES.get(m, {})
        self.mode_desc.configure(text=cfg.get("description", ""))
        self.adv_vars["branches"].set(str(cfg.get("branches", 1)))
        self.adv_vars["max_iterations"].set(str(cfg.get("max_iterations", 5)))

    def _load_hardware(self):
        self.hw = detect_hardware()
        self.root.after(0, self._update_hw_ui)

    def _update_hw_ui(self):
        hw = self.hw
        self.hw_cpu_lbl.configure(text=f"CPU: {hw['cpu']}  |  {hw['cores']} núcleos")
        self.hw_ram_lbl.configure(
            text=f"RAM: {hw['ram_gb']} GB  |  Python {hw['python']}  |  "
                 f"{'KVM ✓' if hw['kvm'] else 'Docker ✓' if hw['docker'] else '⚠ sem sandbox'}"
        )
        self.hw_alert_lbl.configure(text=f"⚡ Recomendado: {hw['alert']}")
        # Aplica modo recomendado
        self.mode_var.set(hw["recommended_mode"])
        self.adv_vars["branches"].set(str(hw["recommended_branches"]))
        self.adv_vars["max_iterations"].set(str(hw["recommended_iterations"]))
        self._on_mode()

    def _start(self):
        global ACTIVE_THEME, COLORS
        ACTIVE_THEME = self.theme_var.get()
        COLORS = THEMES[ACTIVE_THEME]

        self.result = {
            "mode": self.mode_var.get(),
            "theme": self.theme_var.get(),
            "advanced": {
                "branches":       int(self.adv_vars["branches"].get() or 1),
                "max_iterations": int(self.adv_vars["max_iterations"].get() or 5),
            },
            "hw": self.hw,
        }
        self.root.destroy()


# ══════════════════════════════════════════════════════════════════
# PAINEL PRINCIPAL
# ══════════════════════════════════════════════════════════════════

class KosmosPanel:
    """Painel de Chat Premium do KOSMOS v2.5."""

    MODES = {
        "⚡ Auto-Dev": {
            "description": "Desenvolvimento autônomo e correção de código",
            "branches": 1, "max_iterations": 5,
            "tot": False, "reflexion": True,
        },
        "🔬 Cientista": {
            "description": "Hipótese → Experimento → Análise",
            "branches": 2, "max_iterations": 4,
            "tot": True, "reflexion": True,
        },
        "🚀 Turbo": {
            "description": "Máximo raciocínio. Múltiplos caminhos paralelos.",
            "branches": 4, "max_iterations": 6,
            "tot": True, "reflexion": True,
        },
        "💰 Econômico": {
            "description": "Baixo custo de API. Raciocínio linear.",
            "branches": 1, "max_iterations": 2,
            "tot": False, "reflexion": False,
        },
    }

    def __init__(self, root: tk.Tk, boot_config: dict = None):
        self.root = root
        self.boot_config = boot_config or {}
        self.root.title("KOSMOS KOSMOS v2.5 — CNGSM")
        self.root.geometry("1100x720")
        self.root.minsize(900, 600)
        self.root.configure(bg=COLORS["bg_primary"])

        self.engine_instance: Optional[KosmosEngine] = None
        self.current_engine_config = None
        self.message_queue: queue.Queue = queue.Queue()
        self.session_log: list = []
        self._thinking_active = False

        self._setup_styles()
        self._setup_ui()
        self._start_queue_consumer()
        self._check_environment()

        # Aplica config do boot panel
        if boot_config:
            mode = boot_config.get("mode", "⚡ Auto-Dev")
            if mode in self.MODES:
                self.mode_var.set(mode)
                self._on_mode_change()
            adv = boot_config.get("advanced", {})
            if adv.get("branches"):
                self.adv_vars["branches"].set(str(adv["branches"]))
            if adv.get("max_iterations"):
                self.adv_vars["max_iterations"].set(str(adv["max_iterations"]))

    def _setup_styles(self):
        C = COLORS
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TFrame",   background=C["bg_primary"])
        style.configure("Card.TFrame",   background=C["bg_card"])
        style.configure("Sidebar.TFrame",background=C["bg_secondary"])
        style.configure("Dark.TLabel",   background=C["bg_primary"],   foreground=C["text_primary"],   font=FONT_BODY)
        style.configure("Card.TLabel",   background=C["bg_card"],      foreground=C["text_primary"],   font=FONT_BODY)
        style.configure("Sidebar.TLabel",background=C["bg_secondary"], foreground=C["text_secondary"], font=FONT_SMALL)
        style.configure("Title.TLabel",  background=C["bg_secondary"], foreground=C["text_primary"],   font=FONT_TITLE)
        style.configure("Dark.TCombobox",
            fieldbackground=C["bg_input"], background=C["bg_input"],
            foreground=C["text_primary"],  selectbackground=C["accent"])
        style.configure("Dark.TSeparator",  background=C["border"])
        style.configure("Dark.TLabelframe", background=C["bg_secondary"], foreground=C["text_secondary"])
        style.configure("Dark.TLabelframe.Label", background=C["bg_secondary"], foreground=C["text_muted"], font=FONT_SMALL)

    def _setup_ui(self):
        C = COLORS
        main = tk.Frame(self.root, bg=C["bg_primary"])
        main.pack(fill="both", expand=True)
        self._build_header(main)
        body = tk.Frame(main, bg=C["bg_primary"])
        body.pack(fill="both", expand=True)
        self._build_sidebar(body)
        self._build_chat_area(body)

    def _build_header(self, parent):
        C = COLORS
        header = tk.Frame(parent, bg=C["bg_secondary"], height=52)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        tk.Label(header, text="◈ KOSMOS KOSMOS",
                 font=("Consolas", 15, "bold"), bg=C["bg_secondary"], fg=C["accent"]).pack(side="left", padx=20, pady=10)
        tk.Label(header, text="v2.5  |  CNGSM — Cloves Nascimento",
                 font=FONT_SMALL, bg=C["bg_secondary"], fg=C["text_muted"]).pack(side="left")
        self.env_status_label = tk.Label(header, text="● Verificando ambiente...",
                                          font=FONT_SMALL, bg=C["bg_secondary"], fg=C["accent_yellow"])
        self.env_status_label.pack(side="right", padx=20)

    def _build_sidebar(self, parent):
        C = COLORS
        sidebar = tk.Frame(parent, bg=C["bg_secondary"], width=240)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="MODO", font=("Segoe UI", 8, "bold"),
                 bg=C["bg_secondary"], fg=C["text_muted"]).pack(anchor="w", padx=16, pady=(16, 4))

        self.mode_var = tk.StringVar(value="⚡ Auto-Dev")
        self.mode_combo = ttk.Combobox(sidebar,
            textvariable=self.mode_var,
            values=list(self.MODES.keys()),
            state="readonly", style="Dark.TCombobox", width=22)
        self.mode_combo.pack(padx=12, pady=(0, 4))
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)

        self.mode_desc = tk.Label(sidebar, text=self.MODES["⚡ Auto-Dev"]["description"],
                                   font=FONT_SMALL, bg=C["bg_secondary"], fg=C["text_secondary"],
                                   wraplength=210, justify="left")
        self.mode_desc.pack(anchor="w", padx=14, pady=(0, 12))

        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", padx=12, pady=4)

        tk.Label(sidebar, text="AVANÇADO", font=("Segoe UI", 8, "bold"),
                 bg=C["bg_secondary"], fg=C["text_muted"]).pack(anchor="w", padx=16, pady=(8, 4))

        self.adv_vars = {
            "branches":       tk.StringVar(value="1"),
            "max_iterations": tk.StringVar(value="5"),
        }
        for lbl, key in [("Branches (ToT):", "branches"), ("Max Iterações:", "max_iterations")]:
            row = tk.Frame(sidebar, bg=C["bg_secondary"])
            row.pack(fill="x", padx=12, pady=2)
            tk.Label(row, text=lbl, font=FONT_SMALL, bg=C["bg_secondary"],
                     fg=C["text_secondary"], width=16, anchor="w").pack(side="left")
            e = tk.Entry(row, textvariable=self.adv_vars[key], width=5,
                         font=FONT_MONO, bg=C["bg_input"], fg=C["text_primary"],
                         insertbackground=C["accent"], bd=0,
                         highlightthickness=1, highlightcolor=C["accent"],
                         highlightbackground=C["border"])
            e.pack(side="left", padx=4)

        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", padx=12, pady=8)

        # Botões de sessão
        for lbl, cmd in [("↺ Nova Sessão", self._new_session),
                          ("⬜ Limpar Chat",  self._clear_chat),
                          ("↓ Exportar",     self._export_history)]:
            btn = tk.Button(sidebar, text=lbl, font=FONT_SMALL,
                            bg=C["bg_card"], fg=C["text_secondary"],
                            activebackground=C["bg_input"], relief="flat", bd=0,
                            cursor="hand2", command=cmd, anchor="w")
            btn.pack(fill="x", padx=12, pady=2, ipady=4)

        # Info hardware
        hw = self.boot_config.get("hw", {})
        if hw:
            ttk.Separator(sidebar, orient="horizontal").pack(fill="x", padx=12, pady=8)
            ram = hw.get("ram_gb", "?")
            cores = hw.get("cores", "?")
            mode_hw = "KVM" if hw.get("kvm") else "Docker" if hw.get("docker") else "offline"
            for txt in [f"RAM: {ram}GB  Cores: {cores}", f"Sandbox: {mode_hw}"]:
                tk.Label(sidebar, text=txt, font=("Segoe UI", 8),
                         bg=C["bg_secondary"], fg=C["text_muted"]).pack(anchor="w", padx=16, pady=1)

    def _build_chat_area(self, parent):
        C = COLORS
        chat_frame = tk.Frame(parent, bg=C["bg_primary"])
        chat_frame.pack(side="left", fill="both", expand=True)

        # Área de mensagens
        self.chat_area = tk.Text(
            chat_frame,
            font=FONT_BODY, wrap="word",
            bg=C["bg_primary"], fg=C["text_primary"],
            insertbackground=C["accent"],
            selectbackground=C["accent"],
            relief="flat", bd=0,
            padx=20, pady=16,
            state="disabled",
            cursor="arrow",
        )
        self.chat_area.pack(fill="both", expand=True)

        scroll = tk.Scrollbar(chat_frame, command=self.chat_area.yview,
                               bg=C["bg_secondary"], troughcolor=C["bg_primary"],
                               activebackground=C["accent"], relief="flat", bd=0, width=8)
        self.chat_area.configure(yscrollcommand=scroll.set)
        scroll.place(relx=1, rely=0, relheight=1, anchor="ne", width=8)

        # Tags de texto
        self.chat_area.tag_configure("user",    foreground=C["accent"],        font=FONT_BOLD)
        self.chat_area.tag_configure("bot",     foreground=C["text_primary"],  font=FONT_BODY)
        self.chat_area.tag_configure("system",  foreground=C["system_text"],   font=FONT_SMALL)
        self.chat_area.tag_configure("thinking",foreground=C["thinking"],      font=FONT_SMALL)
        self.chat_area.tag_configure("success", foreground=C["success"],       font=FONT_SMALL)
        self.chat_area.tag_configure("error",   foreground=C["error"],         font=FONT_SMALL)
        self.chat_area.tag_configure("warning", foreground=C["warning"],       font=FONT_SMALL)

        # ── Barra de input ─────────────────────────────────────
        input_bar = tk.Frame(chat_frame, bg=C["bg_secondary"], pady=10)
        input_bar.pack(fill="x", side="bottom")

        input_inner = tk.Frame(input_bar, bg=C["bg_input"],
                                highlightthickness=1,
                                highlightcolor=C["accent"],
                                highlightbackground=C["border"])
        input_inner.pack(fill="x", padx=16, pady=0)

        # Hint de atalho
        hint = tk.Label(input_bar, text="Enter → enviar  |  Shift+Enter → nova linha",
                        font=("Segoe UI", 8), bg=C["bg_secondary"], fg=C["text_muted"])
        hint.pack(anchor="e", padx=20, pady=(0, 2))

        # ── Text widget responsivo ──────────────────────────────
        self.task_entry = tk.Text(
            input_inner,
            font=FONT_BODY,
            bg=C["bg_input"], fg=C["text_primary"],
            insertbackground=C["accent"],
            relief="flat", bd=0,
            height=3,           # altura inicial em linhas
            wrap="word",
            padx=12, pady=10,
        )
        self.task_entry.pack(fill="both", expand=True, side="left")
        self.task_entry.focus_set()

        # Placeholder
        self._placeholder_text = "Digite sua tarefa... (Enter para enviar)"
        self._placeholder_active = True
        self.task_entry.insert("1.0", self._placeholder_text)
        self.task_entry.configure(fg=C["text_muted"])

        self.task_entry.bind("<FocusIn>",  self._on_focus_in)
        self.task_entry.bind("<FocusOut>", self._on_focus_out)

        # ── Bind de teclado responsivo ──────────────────────────
        self.task_entry.bind("<Return>",       self._on_enter_key)
        self.task_entry.bind("<KP_Enter>",     self._on_enter_key)
        # Shift+Enter → insere \n (comportamento padrão do Text widget)
        self.task_entry.bind("<Shift-Return>", lambda e: None)

        # Botão enviar
        self.send_btn = tk.Button(
            input_inner,
            text="↑",
            font=("Segoe UI Semibold", 14),
            bg=C["send_btn"], fg=C["send_fg"],
            activebackground=C["thinking"],
            relief="flat", bd=0,
            width=4,
            cursor="hand2",
            command=self.start_engine_ui
        )
        self.send_btn.pack(side="right", padx=8, pady=8, fill="y")

        self._log_system("KOSMOS KOSMOS v2.5 pronto. Digite uma tarefa.")

    # ── Placeholder ─────────────────────────────────────────────

    def _on_focus_in(self, event):
        if self._placeholder_active:
            self.task_entry.delete("1.0", tk.END)
            self.task_entry.configure(fg=COLORS["text_primary"])
            self._placeholder_active = False

    def _on_focus_out(self, event):
        if not self.task_entry.get("1.0", tk.END).strip():
            self.task_entry.insert("1.0", self._placeholder_text)
            self.task_entry.configure(fg=COLORS["text_muted"])
            self._placeholder_active = True

    # ── Chat log ─────────────────────────────────────────────────

    def _append(self, text: str, tag: str, prefix: str = ""):
        self.chat_area.configure(state="normal")
        if prefix:
            self.chat_area.insert(tk.END, prefix, tag)
        self.chat_area.insert(tk.END, text + "\n", tag)
        self.chat_area.see(tk.END)
        self.chat_area.configure(state="disabled")

    def _log_user(self, text):
        self._append(text, "user", "  ◎ USUÁRIO  " + datetime.now().strftime("%H:%M") + "\n  ")

    def _log_bot(self, text):
        self._append(text, "bot", "  ◈ KOSMOS  " + datetime.now().strftime("%H:%M") + "\n  ")

    def _log_thinking(self, text):
        self._append("    ↳ " + text, "thinking")

    def _log_system(self, text):
        self._append("  " + text, "system")

    def _log_success(self, text):
        self._append("  ✓ " + text, "success")

    def _log_error(self, text):
        self._append("  ✗ " + text, "error")

    def _log_warning(self, text):
        self._append("  ⚠ " + text, "warning")

    # ── Queue consumer ───────────────────────────────────────────

    def _start_queue_consumer(self):
        def consume():
            while True:
                try:
                    msg = self.message_queue.get_nowait()
                    mtype = msg.get("type")
                    if mtype == "log":
                        level = msg.get("level", "info")
                        text  = msg.get("message", "")
                        if level == "success":
                            self._log_success(text)
                        elif level == "error":
                            self._log_error(text)
                        else:
                            self._log_thinking(text)
                    elif mtype == "thought":
                        self._log_thinking(msg["message"])
                    elif mtype == "result":
                        self._handle_result(msg["result"])
                    elif mtype == "error":
                        self._log_error(msg["message"])
                except Exception:
                    pass
                self.root.after(50, consume)
                break
        self.root.after(100, consume)

    def _handle_result(self, result: dict):
        if result["status"] == "success":
            res = result.get("result", "")
            if isinstance(res, dict):
                output = res.get("output", "") or ""
                error  = res.get("error", "")
                if error and not output:
                    self._log_error(error)
                else:
                    self._log_bot(output or "Tarefa concluída com sucesso.")
            else:
                self._log_bot(str(res))
            iters = result.get("iterations", "?")
            total = result.get("total_time", 0)
            self._log_success(f"Concluído em {total:.1f}s • {iters} iteração(ões)")
        else:
            self._log_warning("Agente não completou a tarefa dentro do limite de iterações.")

        self.send_btn.configure(state="normal", bg=COLORS["send_btn"])
        self.task_entry.configure(state="normal")
        self.task_entry.focus_set()
        self._thinking_active = False

    # ── Engine ───────────────────────────────────────────────────

    def _on_enter_key(self, event):
        # Shift+Enter → nova linha (deixa o Text widget lidar)
        if event.state & 0x1:
            return None
        # Enter → envia
        self.start_engine_ui()
        return "break"

    def start_engine_ui(self):
        if self._placeholder_active:
            return
        task = self.task_entry.get("1.0", tk.END).strip()
        if not task:
            return

        self._log_user(task)
        self.session_log.append({"role": "user", "content": task, "time": datetime.now().isoformat()})
        self.task_entry.delete("1.0", tk.END)
        self._placeholder_active = False

        adv = self._get_config()
        self._log_thinking(f"Iniciando engine [{adv['mode']}]...")

        self.send_btn.configure(state="disabled", bg=COLORS["text_muted"])
        self.task_entry.configure(state="disabled")
        self._thinking_active = True

        threading.Thread(target=self._run_engine_thread, args=(task, adv), daemon=True).start()

    def _run_engine_thread(self, task: str, config: dict):
        try:
            import logging
            handler = _QueueLogHandler(self.message_queue)
            handler.setLevel(logging.INFO)
            kosmos_logger = logging.getLogger("kosmos")
            kosmos_logger.addHandler(handler)

            adv = config["advanced"]
            if self.engine_instance is None or self.current_engine_config != config:
                self.engine_instance = KosmosEngine(
                    max_iterations=adv["max_iterations"],
                    branches=adv["branches"],
                    verbose=True,
                    api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
                )
                self.current_engine_config = config

            result = self.engine_instance.run(task)
            kosmos_logger.removeHandler(handler)
            self.message_queue.put({"type": "result", "result": result})
            self.session_log.append({"role": "assistant", "result": result, "time": datetime.now().isoformat()})

        except Exception as e:
            self.message_queue.put({"type": "error", "message": f"ERRO CRÍTICO: {str(e)}"})
            self.root.after(0, lambda: self.send_btn.configure(state="normal", bg=COLORS["send_btn"]))
            self.root.after(0, lambda: self.task_entry.configure(state="normal"))

    def _get_config(self) -> dict:
        mode     = self.mode_var.get()
        mode_cfg = self.MODES.get(mode, self.MODES["⚡ Auto-Dev"])
        return {
            "mode": mode,
            "advanced": {
                "branches":       int(self.adv_vars["branches"].get() or mode_cfg["branches"]),
                "max_iterations": int(self.adv_vars["max_iterations"].get() or mode_cfg["max_iterations"]),
            }
        }

    def _on_mode_change(self, event=None):
        mode = self.mode_var.get()
        cfg  = self.MODES.get(mode, {})
        self.mode_desc.configure(text=cfg.get("description", ""))
        self.adv_vars["branches"].set(str(cfg.get("branches", 1)))
        self.adv_vars["max_iterations"].set(str(cfg.get("max_iterations", 5)))
        self._log_system(f"Modo alterado: {mode}")

    def _check_environment(self):
        def check():
            kvm = os.path.exists("/dev/kvm") and os.access("/dev/kvm", os.R_OK | os.W_OK)
            docker = False
            try:
                r = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
                docker = r.returncode == 0
            except Exception:
                pass
            if kvm:
                status, color = "● KVM ativo — Firecracker pronto", COLORS["success"]
            elif docker:
                status, color = "● Docker ativo — Fallback seguro", COLORS["accent_yellow"]
            else:
                status, color = "⚠ KVM e Docker indisponíveis", COLORS["error"]
            self.root.after(0, lambda: self.env_status_label.configure(text=status, fg=color))
            self.root.after(0, lambda: self._log_system(status.replace("●","").replace("⚠","").strip()))
        threading.Thread(target=check, daemon=True).start()

    def _clear_chat(self):
        self.chat_area.configure(state="normal")
        self.chat_area.delete("1.0", tk.END)
        self.chat_area.configure(state="disabled")
        self._log_system("Conversa limpa.")

    def _new_session(self):
        self._clear_chat()
        self.engine_instance = None
        self.current_engine_config = None
        self.session_log = []
        self._log_system("Nova sessão iniciada.")

    def _export_history(self):
        if not self.session_log:
            messagebox.showinfo("Exportar", "Nenhuma conversa para exportar.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Todos", "*.*")],
            initialfile=f"kosmos_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.session_log, f, ensure_ascii=False, indent=2, default=str)
            self._log_system(f"Histórico exportado: {os.path.basename(path)}")


# ══════════════════════════════════════════════════════════════════
# LOG HANDLER
# ══════════════════════════════════════════════════════════════════

class _QueueLogHandler:
    def __init__(self, q: queue.Queue):
        self.q = q
        self.level = 20

    def setLevel(self, level):
        self.level = level

    def handle(self, record):
        import logging
        if record.levelno >= self.level:
            msg = record.getMessage()
            skip = ["API call #", "DeepSeekClient", "FAISS", "Popen"]
            if any(s in msg for s in skip):
                return
            self.q.put({"type": "log", "level": "thought", "message": msg})

    def emit(self, record):
        self.handle(record)


# ══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════

def start_engine_panel():
    try:
        # 1. Boot panel
        boot_root = tk.Tk()
        boot_app  = BootPanel(boot_root)
        boot_root.mainloop()

        if boot_app.result is None:
            print("[KOSMOS] Boot cancelado.")
            sys.exit(0)

        boot_config = boot_app.result

        # 2. Chat principal
        main_root = tk.Tk()
        KosmosPanel(main_root, boot_config=boot_config)
        main_root.mainloop()

    except KeyboardInterrupt:
        print("\n[KOSMOS] Encerrando painel...")
        sys.exit(0)


if __name__ == "__main__":
    start_engine_panel()
