import ttkbootstrap as ttk
from tkinter import filedialog, messagebox, Toplevel
from pathlib import Path
from core.config_manager import load_config, update_config_fields
from core.utils import prepare_from_folder


class TelaContinuar(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master

        # Carregar configurações salvas
        self.config = load_config()

        # ===== TÍTULO =====
        ttk.Label(self, text="Continuar Trabalho", font=("Arial", 16, "bold")).pack(pady=20)

        # ===== FRAME PARA INPUT =====
        frame_input = ttk.Frame(self)
        frame_input.pack(pady=10, padx=20, fill="x")

        # Label
        ttk.Label(frame_input, text="Caminho da pasta com imagens e labels:").pack(anchor="w")

        # Entry (campo de texto)
        self.entrada_pasta = ttk.Entry(frame_input)
        self.entrada_pasta.pack(fill="x", pady=5)
        self.entrada_pasta.insert(0, self.config.get("input_folder", ""))

        # Botão para abrir explorador
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
            text="Continuar",
            command=self.continuar,
            bootstyle="success"
        ).pack(side="left", padx=10)

    # ===== FUNÇÕES =====
    def selecionar_pasta(self):
        """Abre o diálogo para selecionar a pasta"""
        pasta = filedialog.askdirectory(
            title="Selecione a pasta com imagens e labels"
        )

        if pasta:
            self.entrada_pasta.delete(0, "end")
            self.entrada_pasta.insert(0, pasta)

    def continuar(self):
        from gui.tela_rotulagem import LabelingGUI

        """Salva a pasta e continua o trabalho"""
        caminho_pasta = self.entrada_pasta.get().strip()

        # Validações
        if not caminho_pasta:
            messagebox.showerror("Erro", "Por favor, selecione uma pasta!")
            return

        # Verificar se o caminho é uma pasta válida
        pasta_path = Path(caminho_pasta)
        if not pasta_path.is_dir():
            messagebox.showerror("Erro", "O caminho selecionado não é uma pasta válida!")
            return

        # Verificar se contém as subpastas necessárias
        subpasta_images = pasta_path / "images"
        subpasta_labels = pasta_path / "labels"

        if not subpasta_images.is_dir():
            messagebox.showerror(
                "Erro",
                f"A pasta deve conter uma subpasta 'images'!\n\nCaminho esperado: {subpasta_images}"
            )
            return

        if not subpasta_labels.is_dir():
            messagebox.showerror(
                "Erro",
                f"A pasta deve conter uma subpasta 'labels'!\n\nCaminho esperado: {subpasta_labels}"
            )
            return

        # Salvar a pasta no config
        
        messagebox.showinfo(
            "Sucesso",
            f"Iniciando trabalho com a pasta:\n{caminho_pasta}"
        )

        update_config_fields(input_folder = caminho_pasta)

        config = load_config()
        labels = config["labels"]

        images_dir, labels_dir = prepare_from_folder()

        top = Toplevel(self.master) # self.master é a instância App/ttk.Window
        top.title("AutoLabeler - revisão manual")

        LabelingGUI(top, images_dir, labels_dir, labels, autosave=True)