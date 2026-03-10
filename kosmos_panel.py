import tkinter as tk
from tkinter import ttk, scrolledtext
import json
import os
import time
import threading
import sys
from typing import Dict, Any

# Importa o motor real
try:
    from main import KosmosEngine, BANNER
except ImportError:
    # Caso rodado de fora do diretório
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from main import KosmosEngine, BANNER

class KosmosPanel:
    """
    Interface Premium estilo ChatGPT para o CNGSM CODE.
    """
    
    MODES = {
        "Modo Econômico": {
            "description": "Baixo custo de API. Raciocínio linear.",
            "branches": 1,
            "max_iterations": 2,
            "tot": False,
            "reflexion": False,
        },
        "Modo Cientista": {
            "description": "Hipótese -> Experimento -> Análise.",
            "branches": 2,
            "max_iterations": 4,
            "tot": True,
            "reflexion": True,
        },
        "Modo Turbo": {
            "description": "Máximo raciocínio. Múltiplos caminhos.",
            "branches": 4,
            "max_iterations": 6,
            "tot": True,
            "reflexion": True,
        },
        "Cngsm Auto-Dev": {
            "description": "Focado em desenvolvimento autônomo e correção de código.",
            "branches": 1,
            "max_iterations": 5,
            "tot": False,
            "reflexion": True,
        }
    }

    def __init__(self, root):
        self.root = root
        self.root.title("CNGSM CODE — Conversational AI")
        self.root.geometry("900x700")
        self.root.configure(bg="#f0f2f5")
        
        # Estilo
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("Sidebar.TFrame", background="#ffffff")
        self.style.configure("Chat.TFrame", background="#f0f2f5")
        self.style.configure("Header.TLabel", font=("Segoe UI Semibold", 12), background="#ffffff")
        self.style.configure("TButton", font=("Segoe UI Semibold", 10))
        
        self.engine_instance = None
        self.current_engine_config = None
        self._setup_ui()
        
        # Inicializa o motor em background para poupar tempo no primeiro clique
        self.log_chat("Sistema", "CNGSM CODE pronto. Como posso ajudar você hoje?")

    def _setup_ui(self):
        # PanedWindow para separar Sidebar e Chat
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill="both", expand=True)

        # --- SIDEBAR (CONFIGURAÇÕES) ---
        self.sidebar = ttk.Frame(self.paned, style="Sidebar.TFrame", width=250)
        self.paned.add(self.sidebar, weight=1)

        ttk.Label(self.sidebar, text="Configurações", style="Header.TLabel").pack(pady=10, padx=10, anchor="w")

        # Modo do Agente
        ttk.Label(self.sidebar, text="Modo da Engine:", background="#ffffff").pack(padx=10, anchor="w")
        self.mode_var = tk.StringVar(value="Cngsm Auto-Dev")
        self.mode_combo = ttk.Combobox(self.sidebar, textvariable=self.mode_var, values=list(self.MODES.keys()), state="readonly")
        self.mode_combo.pack(fill="x", padx=10, pady=5)
        self.mode_combo.bind("<<ComboboxSelected>>", lambda e: self.log_chat("Sistema", f"Modo alterado para: {self.mode_var.get()}"))

        # Configurações Avançadas (Compacto)
        adv_frame = ttk.LabelFrame(self.sidebar, text=" Avançado ", padding=5)
        adv_frame.pack(fill="x", padx=10, pady=10)

        self.adv_vars = {
            "branches": tk.StringVar(value="1"),
            "max_iterations": tk.StringVar(value="5"),
        }
        ttk.Label(adv_frame, text="Branches (ToT):").pack(anchor="w")
        ttk.Entry(adv_frame, textvariable=self.adv_vars["branches"]).pack(fill="x", pady=2)
        ttk.Label(adv_frame, text="Max Iterations:").pack(anchor="w")
        ttk.Entry(adv_frame, textvariable=self.adv_vars["max_iterations"]).pack(fill="x", pady=2)

        # Botão Limpar Chat
        ttk.Button(self.sidebar, text="Limpar Conversa", command=self._clear_chat).pack(side="bottom", fill="x", padx=10, pady=10)

        # --- CHAT AREA ---
        self.chat_frame = ttk.Frame(self.paned, style="Chat.TFrame")
        self.paned.add(self.chat_frame, weight=4)

        # Chat History
        self.chat_area = scrolledtext.ScrolledText(
            self.chat_frame, 
            wrap=tk.WORD, 
            font=("Segoe UI", 11), 
            bg="#ffffff", 
            fg="#2c3e50",
            padx=10, 
            pady=10,
            state="disabled"
        )
        self.chat_area.pack(fill="both", expand=True, padx=20, pady=(20, 10))

        # Input Area (Estilo ChatGPT)
        input_container = ttk.Frame(self.chat_frame, style="Chat.TFrame")
        input_container.pack(fill="x", side="bottom", padx=20, pady=(0, 20))

        self.task_entry = tk.Entry(
            input_container, 
            font=("Segoe UI", 12), 
            bd=1, 
            relief="flat",
            highlightthickness=1,
            highlightcolor="#007bff",
            highlightbackground="#cccccc"
        )
        self.task_entry.pack(side="left", fill="both", expand=True, ipady=8, padx=(0, 10))
        self.task_entry.bind("<Return>", lambda e: self.start_engine_ui())

        self.send_btn = tk.Button(
            input_container, 
            text="Enviar", 
            command=self.start_engine_ui, 
            bg="#007bff", 
            fg="white", 
            font=("Segoe UI Semibold", 10),
            bd=0,
            padx=20,
            cursor="hand2"
        )
        self.send_btn.pack(side="right", fill="y")

    def log_chat(self, sender: str, message: str):
        self.chat_area.configure(state="normal")
        
        # Estilos de tag
        self.chat_area.tag_configure("user", font=("Segoe UI Bold", 11), foreground="#2c3e50")
        self.chat_area.tag_configure("bot", font=("Segoe UI Bold", 11), foreground="#007bff")
        self.chat_area.tag_configure("system", font=("Segoe UI Italic", 9), foreground="#7f8c8d")
        
        timestamp = time.strftime('%H:%M')
        
        if sender == "Usuário":
            self.chat_area.insert(tk.END, f"\n👤 {sender} ({timestamp}):\n", "user")
            self.chat_area.insert(tk.END, f"{message}\n")
        elif sender == "Sistema":
            self.chat_area.insert(tk.END, f"\n⚙️ {message}\n", "system")
        else:
            self.chat_area.insert(tk.END, f"\n🤖 {sender} ({timestamp}):\n", "bot")
            self.chat_area.insert(tk.END, f"{message}\n")
            
        self.chat_area.see(tk.END)
        self.chat_area.configure(state="disabled")
        self.root.update()

    def _clear_chat(self):
        self.chat_area.configure(state="normal")
        self.chat_area.delete(1.0, tk.END)
        self.chat_area.configure(state="disabled")
        self.log_chat("Sistema", "Memória de conversa limpa.")

    def get_config(self) -> Dict[str, Any]:
        return {
            "mode": self.mode_var.get(),
            "advanced": {
                "branches": int(self.adv_vars["branches"].get()),
                "max_iterations": int(self.adv_vars["max_iterations"].get()),
            }
        }

    def start_engine_ui(self):
        task = self.task_entry.get().strip()
        if not task:
            return

        self.log_chat("Usuário", task)
        self.task_entry.delete(0, tk.END)
        
        config = self.get_config()
        
        # Feedback visual de processamento
        self.log_chat("Sistema", "Processando tarefa... (Isso pode levar alguns minutos para tarefas complexas)")
        
        # Desabilita botões para evitar cliques múltiplos
        self.send_btn.configure(state="disabled", bg="#cccccc")
        self.task_entry.configure(state="disabled")

        # Inicia o motor em uma thread
        threading.Thread(target=self._run_engine_thread, args=(task, config), daemon=True).start()

    def _run_engine_thread(self, task: str, config: Dict[str, Any]):
        try:
            # Redireciona logs apenas para o terminal (nao poluir o chat UI com logs de debug)
            # Mas podemos capturar se houver erro
            adv = config["advanced"]
            
            if self.engine_instance is None or self.current_engine_config != config:
                self.engine_instance = KosmosEngine(
                    max_iterations=adv["max_iterations"],
                    branches=adv["branches"],
                    verbose=True,
                    api_key=os.environ.get("DEEPSEEK_API_KEY", "")
                )
                self.current_engine_config = config
            
            result = self.engine_instance.run(task)
            
            if result["status"] == "success":
                res_text = result['result'] if isinstance(result['result'], str) else result['result'].get('output', 'Tarefa concluída')
                self.log_chat("CNGSM CODE", res_text)
            else:
                self.log_chat("Sistema", "Erro ao processar a tarefa.")

        except Exception as e:
            self.log_chat("Sistema", f"ERRO CRÍTICO: {str(e)}")
        finally:
            self.root.after(0, lambda: self.send_btn.configure(state="normal", bg="#007bff"))
            self.root.after(0, lambda: self.task_entry.configure(state="normal"))
            self.root.after(0, lambda: self.task_entry.focus_set())

def start_engine_panel():
    try:
        root = tk.Tk()
        app = KosmosPanel(root)
        root.mainloop()
    except KeyboardInterrupt:
        print("\n[CNGSM CODE] Encerrando painel...")
        sys.exit(0)

if __name__ == "__main__":
    start_engine_panel()
