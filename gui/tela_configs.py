import ttkbootstrap as ttk
from tkinter import messagebox, filedialog
from core.config_manager import load_config, save_config, validate_config


class TelaConfigs(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        
        # Carregar configurações salvas
        self.config = load_config()
        
        # ===== TÍTULO =====
        ttk.Label(self, text="Configurações do Programa", font=("Arial", 16, "bold")).pack(pady=20)
        
        # ===== FRAME PRINCIPAL =====
        frame_main = ttk.Frame(self)
        frame_main.pack(pady=10, padx=20, fill="both", expand=True)
        
        # ===== LABELS =====
        ttk.Label(frame_main, text="Labels (separados por vírgula):", font=("Arial", 10)).pack(anchor="w", pady=(10, 0))
        self.entrada_labels = ttk.Entry(frame_main, font=("Arial", 10))
        self.entrada_labels.pack(fill="x", pady=(0, 10))
        self.entrada_labels.insert(0, ", ".join(self.config["labels"]))
        
        # ===== CONFIDENCE =====
        ttk.Label(frame_main, text="Confiança (0.0 - 1.0):", font=("Arial", 10)).pack(anchor="w", pady=(10, 0))
        self.entrada_confidence = ttk.Entry(frame_main, font=("Arial", 10))
        self.entrada_confidence.pack(fill="x", pady=(0, 10))
        self.entrada_confidence.insert(0, str(self.config["confidence"]))
        
        # ===== INFERENCE SIZE =====
        ttk.Label(frame_main, text="Tamanho de Inferência (formato: 640,640):", font=("Arial", 10)).pack(anchor="w", pady=(10, 0))
        self.entrada_size = ttk.Entry(frame_main, font=("Arial", 10))
        self.entrada_size.pack(fill="x", pady=(0, 10))
        self.entrada_size.insert(0, f"{self.config['inference_size'][0]},{self.config['inference_size'][1]}")
        
        # ===== OUTPUT FOLDER =====
        ttk.Label(frame_main, text="Pasta de Saída:", font=("Arial", 10)).pack(anchor="w", pady=(10, 0))
        
        frame_output = ttk.Frame(frame_main)
        frame_output.pack(fill="x", pady=(0, 10))
        
        self.entrada_output = ttk.Entry(frame_output, font=("Arial", 10))
        self.entrada_output.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.entrada_output.insert(0, self.config.get("output_folder", ""))
        
        ttk.Button(
            frame_output,
            text="Selecionar pasta",
            command=self.selecionar_output_folder,
            bootstyle="primary",
            width=15
        ).pack(side="left")

        # ===== MODEL WEIGHTS =====
        ttk.Label(frame_main, text="Caminho do Modelo (YOLO):", font=("Arial", 10)).pack(anchor="w", pady=(10, 0))
        
        frame_model = ttk.Frame(frame_main)
        frame_model.pack(fill="x", pady=(0, 10))
        
        self.entrada_model = ttk.Entry(frame_model, font=("Arial", 10))
        self.entrada_model.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.entrada_model.insert(0, self.config.get("model_weights", ""))
        
        ttk.Button(
            frame_model,
            text="Selecionar",
            command=self.selecionar_modelo,
            bootstyle="primary",
            width=15
        ).pack(side="left")

        # ===== OVERWRITE OUTPUT =====
        self.var_overwrite = ttk.BooleanVar(value=self.config.get("overwrite_output", True))
        ttk.Checkbutton(
            frame_main,
            text="Sobrescrever saída se pasta já existir",
            variable=self.var_overwrite
        ).pack(anchor="w", pady=(10, 10))
        
        # Frame para os botões
        ttk.Label(frame_main, text="").pack(pady=10)
        
        # ===== FRAME DE BOTÕES =====
        frame_buttons = ttk.Frame(self)
        frame_buttons.pack(pady=10)
        
        ttk.Button(
            frame_buttons,
            text="Salvar",
            command=self.salvar_configs,
            bootstyle="success"
        ).pack(side="left", padx=10)
        
        ttk.Button(
            frame_buttons,
            text="Voltar",
            command=self.voltar,
            bootstyle="secondary"
        ).pack(side="left", padx=10)
    
    def salvar_configs(self):
        """Salva as configurações após validação"""
        try:
            # Obter valores dos campos
            labels_str = self.entrada_labels.get().strip()
            confidence_str = self.entrada_confidence.get().strip()
            size_str = self.entrada_size.get().strip()
            output_folder = self.entrada_output.get().strip()
            model_weights = self.entrada_model.get().strip()
            overwrite_output = self.var_overwrite.get()
            
            # Processar labels
            labels = [label.strip() for label in labels_str.split(",") if label.strip()]
            
            # Processar tamanho
            size_parts = size_str.split(",")
            inference_size = [int(s.strip()) for s in size_parts]
            
            # Validar
            errors = validate_config(labels, confidence_str, inference_size)
            
            if errors:
                messagebox.showerror("Erro de Validação", "\n".join(errors))
                return
            
            # Salvar
            success, message = save_config(
                labels=labels,
                confidence=confidence_str,
                inference_size=inference_size,
                frames_to_extract=self.config.get("frames_to_extract", 10),
                model_weights=model_weights,
                output_folder=output_folder,
                video_path=self.config.get("video_path", ""),
                overwrite_output=overwrite_output
            )
            
            if success:
                messagebox.showinfo("Sucesso", message)
                self.config = load_config()  # Recarregar as configurações
            else:
                messagebox.showerror("Erro", message)
                
        except Exception as e:
            messagebox.showerror("Erro", f"Erro inesperado: {str(e)}")
    
    def selecionar_output_folder(self):
        """Abre o diálogo para selecionar pasta de saída"""
        pasta = filedialog.askdirectory(title="Selecione a pasta de saída")
        if pasta:
            self.entrada_output.delete(0, "end")
            self.entrada_output.insert(0, pasta)

    def selecionar_modelo(self):
        """Abre o diálogo para selecionar modelo YOLO"""
        arquivo = filedialog.askopenfilename(
            title="Selecione o modelo YOLO (.pt)",
            filetypes=[
                ("Modelo YOLO", "*.pt"),
                ("Todos os arquivos", "*.*")
            ]
        )
        if arquivo:
            self.entrada_model.delete(0, "end")
            self.entrada_model.insert(0, arquivo)
    
    def selecionar_pasta(self):
        """Abre o diálogo para selecionar uma pasta (mantido para compatibilidade)"""
        self.selecionar_output_folder()
    
    def voltar(self):
        """Volta para a tela do menu"""
        self.master.mostrar_tela_menu()
