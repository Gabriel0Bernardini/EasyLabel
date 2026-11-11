import ttkbootstrap as ttk
from tkinter import filedialog, messagebox, Toplevel
from core.config_manager import update_config_fields, load_config
from core.utils import prepare_from_video

class TelaConfigVideos(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        # ===== TÍTULO =====
        ttk.Label(self, text="Configuração de Vídeo", font=("Arial", 16, "bold")).pack(pady=20)

        # ===== FRAME PARA INPUT =====
        frame_input = ttk.Frame(self)
        frame_input.pack(pady=10, padx=20, fill="x")

        # Label
        ttk.Label(frame_input, text="Caminho do vídeo:").pack(anchor="w")

        # Entry (campo de texto)
        self.entrada_caminho = ttk.Entry(frame_input)
        self.entrada_caminho.pack(fill="x", pady=5)

        # Botão para abrir explorador
        ttk.Button(
            frame_input,
            text="Selecionar vídeo",
            command=self.selecionar_video,
            bootstyle="primary"
        ).pack(pady=5)

        # ===== FRAME PARA FRAMES =====
        frame_frames = ttk.Frame(self)
        frame_frames.pack(pady=10, padx=20, fill="x")

        ttk.Label(frame_frames, text="Quantidade de frames a extrair:").pack(anchor="w")

        self.entrada_frames = ttk.Entry(frame_frames)
        self.entrada_frames.pack(fill="x", pady=5)

        # ===== CHECKBOX USAR MODELO YOLO =====
        frame_modelo = ttk.Frame(self)
        frame_modelo.pack(pady=10, padx=20, fill="x")

        self.var_usar_modelo = ttk.BooleanVar(value=bool(load_config().get("model_weights", "")))
        self.check_modelo = ttk.Checkbutton(
            frame_modelo,
            text="Usar modelo YOLO para pré-rotular as imagens",
            variable=self.var_usar_modelo,
            bootstyle="round-toggle"
        )
        self.check_modelo.pack(anchor="w")

        # ===== FRAME DE BOTÕES =====
        frame_buttons = ttk.Frame(self)
        frame_buttons.pack(pady=20)

        ttk.Button(
            frame_buttons,
            text="Voltar",
            command=master.mostrar_tela_menu,
            bootstyle="secondary"
        ).pack(side="left", padx=10)

        ttk.Button(
            frame_buttons,
            text="Rotular",
            command=self.rotular_video,
            bootstyle="success"
        ).pack(side="left", padx=10)

    # ===== FUNÇÃO =====
    def selecionar_video(self):
        caminho = filedialog.askopenfilename(
            title="Selecione um vídeo",
            filetypes=[
                ("Arquivos de vídeo", "*.mp4 *.avi *.mov *.mkv"),
                ("Todos os arquivos", "*.*")
            ]
        )

        if caminho:
            self.entrada_caminho.delete(0, "end")
            self.entrada_caminho.insert(0, caminho)

    def rotular_video(self):
        from gui.tela_rotulagem import LabelingGUI
        """Inicia o processo de rotulagem do vídeo"""

        caminho_video = self.entrada_caminho.get().strip()
        frames_str = self.entrada_frames.get().strip()
        usar_modelo = self.var_usar_modelo.get()

        # Validações
        if not caminho_video:
            messagebox.showerror("Erro", "Por favor, selecione um vídeo!")
            return

        try:
            frames_int = int(frames_str)
            if frames_int <= 0:
                messagebox.showerror("Erro", "Número de frames deve ser maior que 0!")
                return
        except ValueError:
            messagebox.showerror("Erro", "Número de frames deve ser um número inteiro!")
            return

        # Validar modelo se o checkbox estiver marcado
        if usar_modelo:
            config = load_config()
            if not config.get("model_weights", ""):
                messagebox.showerror("Erro", "Para usar o modelo YOLO, configure o caminho do modelo nas Configurações!")
                return

        messagebox.showinfo(
            "Processando",
            f"Iniciando extração de {frames_int} frames do vídeo:\n{caminho_video}"
        )

        #salvando as informacoes no arquivo de config
        update_config_fields(video_path=caminho_video, 
                             frames_to_extract=frames_int)
        
        #chamar a função de preparação do dataset a partir do vídeo
        images_dir, labels_dir = prepare_from_video(use_model=usar_modelo)
        print(images_dir)

        config = load_config()
        labels = config["labels"]

        top = Toplevel(self.master) # self.master é a instância App/ttk.Window
        top.title("AutoLabeler - revisão manual")

        LabelingGUI(top, images_dir, labels_dir, labels, autosave=True)

