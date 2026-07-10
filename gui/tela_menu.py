import ttkbootstrap as ttk
from core.config_manager import load_config

class TelaMenu(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)

        # ===== TÍTULO =====
        ttk.Label(
            self,
            text="Menu Principal",
            font=("Arial", 18, "bold")
        ).pack(pady=30)

        # ===== Estilo =====

        style = ttk.Style() 
        style.configure("botao.TButton", 
                        font=("Arial", 12, "bold"),
                        width=30,)

        # ===== BOTÕES =====

        ttk.Button(
            self,
            text="Rotular imagens a partir de vídeo",
            command=master.mostrar_tela_video,  
            style="botao.TButton",
        ).pack(pady=15, fill="x", padx=80)

        # ttk.Button(
        #     self,
        #     text="Rotular imagens a partir de uma pasta",
        #     command=master.mostrar_tela_imagens,  
        #     style="botao.TButton",
        # ).pack(pady=15, fill="x", padx=80)

        ttk.Button(
            self,
            text="Retomar trabalho em andamento",
            command=master.mostrar_tela_continuar,  
            style="botao.TButton",
        ).pack(pady=15, fill="x", padx=80)

        ttk.Button(
            self,
            text="Configurações",
            command=master.mostrar_tela_configs,  
            style="botao.TButton",
            bootstyle="info"
        ).pack(pady=15, fill="x", padx=80)


        # ttk.Button(
        #     self,
        #     text="Debug:",
        #     command=self.debug_print,
        #     style="botao.TButton",
        #     bootstyle="secondary"
        # ).pack(pady=15, fill="x", padx=80)

    def debug_print(self):
        config = load_config()
        print("DEBUG:")
        print("Configurações atuais:")
        for key, value in config.items():
            print(f"{key}: {value}")
        print("==============================")