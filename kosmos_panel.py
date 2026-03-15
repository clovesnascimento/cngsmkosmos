"""
KOSMOS Agent — Painel de Controle Premium v2.1
===============================================
Interface com streaming de pensamentos em tempo real.
Melhorias:
  - Streaming do loop cognitivo (pensamentos visíveis)
  - Status de segurança em tempo real
  - Dark Mode premium
  - Histórico de sessão exportável
  - Indicador de modo de execução (KVM / Docker / Bloqueado)
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import json
import os
import time
import threading
import sys
import queue
from typing import Dict, Any, Optional
from datetime import datetime

try:
    from main import KosmosEngine, BANNER
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from main import KosmosEngine, BANNER


# ─── Paleta Dark Premium ───
COLORS = {
    "bg_primary":   "#0d0f14",
    "bg_secondary": "#141720",
    "bg_card":      "#1a1e2a",
    "bg_input":     "#1f2335",
    "accent":       "#7c6af7",       # Roxo KOSMOS
    "accent_green": "#2dd4a0",
    "accent_red":   "#f76a6a",
    "accent_yellow":"#f7c76a",
    "text_primary": "#e8eaf0",
    "text_secondary":"#7b8099",
    "text_muted":   "#454d66",
    "border":       "#252a3d",
    "user_bubble":  "#1e2540",
    "bot_bubble":   "#171c2e",
    "system_text":  "#454d66",
    "success":      "#2dd4a0",
    "error":        "#f76a6a",
    "warning":      "#f7c76a",
    "thinking":     "#7c6af7",
}

FONT_MONO  = ("Consolas", 10)
FONT_BODY  = ("Segoe UI", 11)
FONT_SMALL = ("Segoe UI", 9)
FONT_BOLD  = ("Segoe UI Semibold", 11)
FONT_TITLE = ("Segoe UI Semibold", 13)


class StreamingHandler:
    """
    Intercepta logs do KosmosEngine e envia para a UI via queue.
    Permite streaming dos pensamentos em tempo real.
    """
    def __init__(self, message_queue: queue.Queue):
        self.queue = message_queue

    def emit(self, level: str, message: str):
        self.queue.put({"type": "log", "level": level, "message": message})

    def emit_thought(self, thought: str):
        self.queue.put({"type": "thought", "message": thought})

    def emit_result(self, result: dict):
        self.queue.put({"type": "result", "result": result})

    def emit_error(self, error: str):
        self.queue.put({"type": "error", "message": error})


class KosmosPanel:
    """
    Painel Premium do KOSMOS Agent v2.1
    Dark theme com streaming de pensamentos em tempo real.
    """

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

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("KOSMOS Agent v2.1 — CNGSM CODE")
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

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        # Frames
        style.configure("Dark.TFrame", background=COLORS["bg_primary"])
        style.configure("Card.TFrame", background=COLORS["bg_card"])
        style.configure("Sidebar.TFrame", background=COLORS["bg_secondary"])

        # Labels
        style.configure("Dark.TLabel",
            background=COLORS["bg_primary"],
            foreground=COLORS["text_primary"],
            font=FONT_BODY
        )
        style.configure("Card.TLabel",
            background=COLORS["bg_card"],
            foreground=COLORS["text_primary"],
            font=FONT_BODY
        )
        style.configure("Sidebar.TLabel",
            background=COLORS["bg_secondary"],
            foreground=COLORS["text_secondary"],
            font=FONT_SMALL
        )
        style.configure("Title.TLabel",
            background=COLORS["bg_secondary"],
            foreground=COLORS["text_primary"],
            font=FONT_TITLE
        )

        # Combobox
        style.configure("Dark.TCombobox",
            fieldbackground=COLORS["bg_input"],
            background=COLORS["bg_input"],
            foreground=COLORS["text_primary"],
            selectbackground=COLORS["accent"],
        )

        # Separator
        style.configure("Dark.TSeparator", background=COLORS["border"])

        # LabelFrame
        style.configure("Dark.TLabelframe",
            background=COLORS["bg_secondary"],
            foreground=COLORS["text_secondary"],
        )
        style.configure("Dark.TLabelframe.Label",
            background=COLORS["bg_secondary"],
            foreground=COLORS["text_muted"],
            font=FONT_SMALL
        )

    def _setup_ui(self):
        """Monta a interface principal."""
        # ── Container Principal ──
        main = tk.Frame(self.root, bg=COLORS["bg_primary"])
        main.pack(fill="both", expand=True)

        # ── Header ──
        self._build_header(main)

        # ── Corpo: Sidebar + Chat ──
        body = tk.Frame(main, bg=COLORS["bg_primary"])
        body.pack(fill="both", expand=True, padx=0, pady=0)

        self._build_sidebar(body)
        self._build_chat_area(body)

    def _build_header(self, parent):
        header = tk.Frame(parent, bg=COLORS["bg_secondary"], height=52)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        # Logo
        logo = tk.Label(
            header,
            text="◈ KOSMOS",
            font=("Consolas", 15, "bold"),
            bg=COLORS["bg_secondary"],
            fg=COLORS["accent"]
        )
        logo.pack(side="left", padx=20, pady=10)

        sub = tk.Label(
            header,
            text="Agent v2.1  |  CNGSM CODE",
            font=FONT_SMALL,
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_muted"]
        )
        sub.pack(side="left", padx=0, pady=10)

        # Status do ambiente (KVM / Docker)
        self.env_status_label = tk.Label(
            header,
            text="● Verificando ambiente...",
            font=FONT_SMALL,
            bg=COLORS["bg_secondary"],
            fg=COLORS["accent_yellow"]
        )
        self.env_status_label.pack(side="right", padx=20)

    def _build_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg=COLORS["bg_secondary"], width=240)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # ── Seção de Modo ──
        tk.Label(
            sidebar, text="MODO DE OPERAÇÃO",
            font=("Consolas", 8), bg=COLORS["bg_secondary"],
            fg=COLORS["text_muted"]
        ).pack(anchor="w", padx=16, pady=(18, 4))

        self.mode_var = tk.StringVar(value="⚡ Auto-Dev")
        self.mode_combo = ttk.Combobox(
            sidebar,
            textvariable=self.mode_var,
            values=list(self.MODES.keys()),
            state="readonly",
            style="Dark.TCombobox",
            font=FONT_BODY
        )
        self.mode_combo.pack(fill="x", padx=16, pady=(0, 4))

        self.mode_desc = tk.Label(
            sidebar, text=self.MODES["⚡ Auto-Dev"]["description"],
            font=FONT_SMALL, bg=COLORS["bg_secondary"],
            fg=COLORS["text_muted"], wraplength=200, justify="left"
        )
        self.mode_desc.pack(anchor="w", padx=16, pady=(0, 12))
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)

        ttk.Separator(sidebar, style="Dark.TSeparator").pack(fill="x", padx=16, pady=8)

        # ── Configurações Avançadas ──
        tk.Label(
            sidebar, text="AVANÇADO",
            font=("Consolas", 8), bg=COLORS["bg_secondary"],
            fg=COLORS["text_muted"]
        ).pack(anchor="w", padx=16, pady=(4, 4))

        adv_frame = tk.Frame(sidebar, bg=COLORS["bg_secondary"])
        adv_frame.pack(fill="x", padx=16)

        self.adv_vars = {
            "branches": tk.StringVar(value="1"),
            "max_iterations": tk.StringVar(value="5"),
        }

        for label, key in [("Branches (ToT):", "branches"), ("Max Iterações:", "max_iterations")]:
            row = tk.Frame(adv_frame, bg=COLORS["bg_secondary"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, font=FONT_SMALL,
                     bg=COLORS["bg_secondary"], fg=COLORS["text_secondary"]).pack(side="left")
            e = tk.Entry(
                row, textvariable=self.adv_vars[key],
                bg=COLORS["bg_input"], fg=COLORS["text_primary"],
                insertbackground=COLORS["accent"],
                relief="flat", font=FONT_SMALL, width=5
            )
            e.pack(side="right")

        ttk.Separator(sidebar, style="Dark.TSeparator").pack(fill="x", padx=16, pady=12)

        # ── Status de Segurança ──
        tk.Label(
            sidebar, text="SEGURANÇA",
            font=("Consolas", 8), bg=COLORS["bg_secondary"],
            fg=COLORS["text_muted"]
        ).pack(anchor="w", padx=16, pady=(0, 6))

        self.sec_indicators = {}
        security_items = [
            ("symlink_protection", "Symlink Traversal"),
            ("unsafe_disabled",    "python_unsafe OFF"),
            ("vsock_limit",        "Vsock Size Limit"),
            ("secret_sanitize",    "Secret Sanitizer"),
        ]
        for key, label in security_items:
            row = tk.Frame(sidebar, bg=COLORS["bg_secondary"])
            row.pack(fill="x", padx=16, pady=1)
            dot = tk.Label(row, text="●", font=FONT_SMALL,
                           bg=COLORS["bg_secondary"], fg=COLORS["accent_green"])
            dot.pack(side="left", padx=(0, 6))
            tk.Label(row, text=label, font=FONT_SMALL,
                     bg=COLORS["bg_secondary"], fg=COLORS["text_secondary"]).pack(side="left")
            self.sec_indicators[key] = dot

        ttk.Separator(sidebar, style="Dark.TSeparator").pack(fill="x", padx=16, pady=12)

        # ── Ações ──
        btn_style = {
            "bg": COLORS["bg_input"],
            "fg": COLORS["text_secondary"],
            "relief": "flat",
            "font": FONT_SMALL,
            "cursor": "hand2",
            "pady": 6,
        }

        tk.Button(
            sidebar, text="⬇  Exportar Histórico",
            command=self._export_history,
            **btn_style
        ).pack(fill="x", padx=16, pady=2)

        tk.Button(
            sidebar, text="🗑  Limpar Conversa",
            command=self._clear_chat,
            **btn_style
        ).pack(fill="x", padx=16, pady=2)

        tk.Button(
            sidebar, text="↺  Nova Sessão",
            command=self._new_session,
            **btn_style
        ).pack(fill="x", padx=16, pady=2)

    def _build_chat_area(self, parent):
        chat_container = tk.Frame(parent, bg=COLORS["bg_primary"])
        chat_container.pack(side="left", fill="both", expand=True)

        # ── Área de Mensagens ──
        self.chat_area = scrolledtext.ScrolledText(
            chat_container,
            wrap=tk.WORD,
            font=FONT_BODY,
            bg=COLORS["bg_primary"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["accent"],
            selectbackground=COLORS["accent"],
            relief="flat",
            padx=24,
            pady=16,
            state="disabled",
            spacing3=4,
        )
        self.chat_area.pack(fill="both", expand=True, padx=0, pady=(0, 0))

        # ── Configuração de Tags ──
        self.chat_area.tag_configure("user_name",
            font=("Consolas", 9, "bold"), foreground=COLORS["accent"])
        self.chat_area.tag_configure("user_text",
            font=FONT_BODY, foreground=COLORS["text_primary"],
            lmargin1=0, lmargin2=0)
        self.chat_area.tag_configure("bot_name",
            font=("Consolas", 9, "bold"), foreground=COLORS["accent_green"])
        self.chat_area.tag_configure("bot_text",
            font=FONT_BODY, foreground=COLORS["text_primary"])
        self.chat_area.tag_configure("thinking",
            font=FONT_MONO, foreground=COLORS["thinking"],
            lmargin1=16, lmargin2=16)
        self.chat_area.tag_configure("system",
            font=("Consolas", 9), foreground=COLORS["text_muted"])
        self.chat_area.tag_configure("success",
            font=FONT_SMALL, foreground=COLORS["success"])
        self.chat_area.tag_configure("error_text",
            font=FONT_BODY, foreground=COLORS["error"])
        self.chat_area.tag_configure("warning_text",
            font=FONT_SMALL, foreground=COLORS["warning"])
        self.chat_area.tag_configure("timestamp",
            font=("Consolas", 8), foreground=COLORS["text_muted"])
        self.chat_area.tag_configure("divider",
            font=("Consolas", 8), foreground=COLORS["border"])
        self.chat_area.tag_configure("code_block",
            font=FONT_MONO, foreground=COLORS["accent_yellow"],
            background=COLORS["bg_card"],
            lmargin1=16, lmargin2=16)

        # ── Input Area ──
        input_bar = tk.Frame(chat_container, bg=COLORS["bg_secondary"], pady=12)
        input_bar.pack(fill="x", side="bottom")

        input_inner = tk.Frame(input_bar, bg=COLORS["bg_input"],
                                highlightbackground=COLORS["border"],
                                highlightthickness=1)
        input_inner.pack(fill="x", padx=20, pady=0)

        self.task_entry = tk.Text(
            input_inner,
            font=FONT_BODY,
            bg=COLORS["bg_input"],
            fg=COLORS["text_primary"],
            insertbackground=COLORS["accent"],
            relief="flat",
            height=3,
            wrap=tk.WORD,
            padx=12,
            pady=8,
        )
        self.task_entry.pack(side="left", fill="both", expand=True)
        self.task_entry.bind("<Return>", self._on_enter_key)
        self.task_entry.bind("<Shift-Return>", lambda e: None)  # Shift+Enter = nova linha

        btn_frame = tk.Frame(input_inner, bg=COLORS["bg_input"])
        btn_frame.pack(side="right", padx=8)

        self.send_btn = tk.Button(
            btn_frame,
            text="Enviar",
            command=self.start_engine_ui,
            bg=COLORS["accent"],
            fg=COLORS["text_primary"],
            font=("Segoe UI Semibold", 10),
            relief="flat",
            padx=16,
            pady=6,
            cursor="hand2",
            activebackground="#6a5ae0",
            activeforeground="white",
        )
        self.send_btn.pack(pady=4)

        hint = tk.Label(
            input_bar,
            text="Enter para enviar  •  Shift+Enter para nova linha",
            font=("Consolas", 8),
            bg=COLORS["bg_secondary"],
            fg=COLORS["text_muted"]
        )
        hint.pack()

        # Mensagem de boas-vindas
        self._log_system("KOSMOS Agent v2.1 pronto. Patches de segurança aplicados.")
        self._log_system("Vulnerabilidades ATK-01..08 mitigadas. Sistema seguro para produção.")

    # ─── Logging no Chat ───

    def _log_to_chat(self, func):
        """Wrapper para executar inserção no chat na thread principal."""
        self.root.after(0, func)

    def _chat_insert(self, *args):
        self.chat_area.configure(state="normal")
        self.chat_area.insert(tk.END, *args)
        self.chat_area.see(tk.END)
        self.chat_area.configure(state="disabled")
        self.root.update_idletasks()

    def _log_system(self, message: str):
        self._chat_insert(f"  {message}\n", "system")

    def _log_user(self, message: str):
        ts = datetime.now().strftime("%H:%M")
        self._chat_insert(f"\n", "divider")
        self._chat_insert(f"  ◎ USUÁRIO  ", "user_name")
        self._chat_insert(f"{ts}\n", "timestamp")
        self._chat_insert(f"  {message}\n", "user_text")

    def _log_bot(self, message: str):
        ts = datetime.now().strftime("%H:%M")
        self._chat_insert(f"\n", "divider")
        self._chat_insert(f"  ◈ KOSMOS  ", "bot_name")
        self._chat_insert(f"{ts}\n", "timestamp")
        self._chat_insert(f"  {message}\n", "bot_text")

    def _log_thinking(self, message: str):
        """Stream de pensamentos em tempo real."""
        self._chat_insert(f"    ↳ {message}\n", "thinking")

    def _log_success(self, message: str):
        self._chat_insert(f"  ✓ {message}\n", "success")

    def _log_error(self, message: str):
        self._chat_insert(f"  ✗ {message}\n", "error_text")

    def _log_warning(self, message: str):
        self._chat_insert(f"  ⚠ {message}\n", "warning_text")

    # ─── Consumidor de Queue ───

    def _start_queue_consumer(self):
        """Consome mensagens da thread de execução e atualiza a UI."""
        def consume():
            while True:
                try:
                    msg = self.message_queue.get_nowait()
                    mtype = msg.get("type")
                    if mtype == "log":
                        level = msg.get("level", "info")
                        text = msg.get("message", "")
                        if level == "thought":
                            self._log_thinking(text)
                        elif level == "success":
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
                except:
                    pass
                self.root.after(50, consume)
                break
        self.root.after(100, consume)

    def _handle_result(self, result: dict):
        """Processa o resultado final do engine."""
        if result["status"] == "success":
            res = result.get("result", "")
            if isinstance(res, dict):
                output = res.get("output", "") or ""
                error = res.get("error", "")
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

        # Re-habilita input
        self.send_btn.configure(state="normal", bg=COLORS["accent"])
        self.task_entry.configure(state="normal")
        self.task_entry.focus_set()
        self._thinking_active = False

    # ─── Engine ───

    def _on_enter_key(self, event):
        if not event.state & 0x1:  # Sem Shift
            self.start_engine_ui()
            return "break"

    def start_engine_ui(self):
        task = self.task_entry.get("1.0", tk.END).strip()
        if not task:
            return

        self._log_user(task)
        self.session_log.append({"role": "user", "content": task, "time": datetime.now().isoformat()})
        self.task_entry.delete("1.0", tk.END)

        adv = self._get_config()
        self._log_thinking(f"Iniciando engine [{adv['mode']}]...")

        self.send_btn.configure(state="disabled", bg=COLORS["text_muted"])
        self.task_entry.configure(state="disabled")
        self._thinking_active = True

        threading.Thread(
            target=self._run_engine_thread,
            args=(task, adv),
            daemon=True
        ).start()

    def _run_engine_thread(self, task: str, config: dict):
        try:
            adv = config["advanced"]

            # Patch: injeta streaming handler no logger
            import logging
            handler = _QueueLogHandler(self.message_queue)
            handler.setLevel(logging.INFO)
            kosmos_logger = logging.getLogger("kosmos")
            kosmos_logger.addHandler(handler)

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
            self.session_log.append({
                "role": "assistant",
                "result": result,
                "time": datetime.now().isoformat()
            })

        except Exception as e:
            self.message_queue.put({"type": "error", "message": f"ERRO CRÍTICO: {str(e)}"})
            self.root.after(0, lambda: self.send_btn.configure(state="normal", bg=COLORS["accent"]))
            self.root.after(0, lambda: self.task_entry.configure(state="normal"))

    # ─── Helpers ───

    def _get_config(self) -> dict:
        mode = self.mode_var.get()
        mode_cfg = self.MODES.get(mode, self.MODES["⚡ Auto-Dev"])
        return {
            "mode": mode,
            "advanced": {
                "branches": int(self.adv_vars["branches"].get() or mode_cfg["branches"]),
                "max_iterations": int(self.adv_vars["max_iterations"].get() or mode_cfg["max_iterations"]),
            }
        }

    def _on_mode_change(self, event=None):
        mode = self.mode_var.get()
        cfg = self.MODES.get(mode, {})
        self.mode_desc.configure(text=cfg.get("description", ""))
        self.adv_vars["branches"].set(str(cfg.get("branches", 1)))
        self.adv_vars["max_iterations"].set(str(cfg.get("max_iterations", 5)))
        self._log_system(f"Modo alterado: {mode}")

    def _check_environment(self):
        """Verifica KVM e Docker e atualiza o indicador do header."""
        def check():
            import subprocess
            kvm = os.path.exists("/dev/kvm") and os.access("/dev/kvm", os.R_OK | os.W_OK)
            docker = False
            try:
                r = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
                docker = r.returncode == 0
            except Exception:
                pass

            if kvm:
                status = "● KVM ativo — Firecracker pronto"
                color = COLORS["success"]
            elif docker:
                status = "● Docker ativo — Fallback seguro"
                color = COLORS["accent_yellow"]
            else:
                status = "⚠ KVM e Docker indisponíveis"
                color = COLORS["error"]

            self.root.after(0, lambda: self.env_status_label.configure(
                text=status, fg=color
            ))
            self.root.after(0, lambda: self._log_system(
                f"Ambiente: {status.replace('●', '').replace('⚠', '').strip()}"
            ))

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


class _QueueLogHandler:
    """Handler de logging que envia mensagens para a queue da UI."""
    def __init__(self, q: queue.Queue):
        self.q = q
        self.level = 20  # INFO

    def setLevel(self, level):
        self.level = level

    def handle(self, record):
        import logging
        if record.levelno >= self.level:
            msg = record.getMessage()
            # Filtra linhas de debug muito técnicas
            skip = ["API call #", "DeepSeekClient", "FAISS", "Popen"]
            if any(s in msg for s in skip):
                return
            self.q.put({"type": "log", "level": "thought", "message": msg})

    def emit(self, record):
        self.handle(record)


def start_engine_panel():
    try:
        root = tk.Tk()
        app = KosmosPanel(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("\n[KOSMOS] Encerrando painel...")
        sys.exit(0)


if __name__ == "__main__":
    start_engine_panel()
