import ttkbootstrap as ttk
from tkinter import filedialog, messagebox, Toplevel
from core.config_manager import update_config_fields, load_config
from core.utils import prepare_from_images


class TelaConfigImagens(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        # ===== TÍTULO =====
        ttk.Label(self, text="Configuração de Pasta de Imagens", font=("Arial", 16, "bold")).pack(pady=20)

        # ===== FRAME PARA INPUT =====
        frame_input = ttk.Frame(self)
        frame_input.pack(pady=10, padx=20, fill="x")

        # Label
        ttk.Label(frame_input, text="Pasta de imagens:").pack(anchor="w")

        # Entry (campo de texto)
        self.entrada_pasta = ttk.Entry(frame_input)
        self.entrada_pasta.pack(fill="x", pady=5)

        # Botão para abrir explorador de pastas
        ttk.Button(
            frame_input,
            text="Selecionar pasta",
            command=self.selecionar_pasta,
            bootstyle="primary"
        ).pack(pady=5)

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
            command=self.rotular_imagens,
            bootstyle="success"
        ).pack(side="left", padx=10)

    # ===== FUNÇÃO =====
    def selecionar_pasta(self):
        caminho = filedialog.askdirectory(
            title="Selecione a pasta de imagens"
        )

        if caminho:
            self.entrada_pasta.delete(0, "end")
            self.entrada_pasta.insert(0, caminho)

    def rotular_imagens(self):
        from gui.tela_rotulagem import LabelingGUI
        """Inicia o processo de rotulagem a partir de uma pasta de imagens"""

        caminho_pasta = self.entrada_pasta.get().strip()

        # Validações
        if not caminho_pasta:
            messagebox.showerror("Erro", "Por favor, selecione uma pasta de imagens!")
            return

        messagebox.showinfo(
            "Processando",
            f"Iniciando rotulagem das imagens da pasta:\n{caminho_pasta}"
        )

        # salvando as informações no arquivo de config
        update_config_fields(input_folder=caminho_pasta)

        # chamar a função de preparação do dataset a partir da pasta de imagens
        images_dir, labels_dir = prepare_from_images()
        print(images_dir)

        config = load_config()
        labels = config["labels"]

        top = Toplevel(self.master)  # self.master é a instância App/ttk.Window
        top.title("AutoLabeler - revisão manual")

        LabelingGUI(top, images_dir, labels_dir, labels, autosave=True)