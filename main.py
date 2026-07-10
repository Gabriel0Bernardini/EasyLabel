import ttkbootstrap as ttk
from gui.tela_config_images import TelaConfigImagens
from gui.tela_menu import TelaMenu
from gui.tela_config_videos import TelaConfigVideos
from gui.tela_configs import TelaConfigs
from gui.tela_continuar import TelaContinuar
from core.config_manager import update_mode


class App(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly")

        self.title("App de Rotulagem")
        self.geometry("800x600")

        self.frame_atual = None
        self.mostrar_tela_menu()

    def trocar_frame(self, novo_frame):
        if self.frame_atual is not None:
            self.frame_atual.destroy()

        self.frame_atual = novo_frame
        self.frame_atual.pack(fill="both", expand=True)

    def mostrar_tela_menu(self):
        self.trocar_frame(TelaMenu(self))

    def mostrar_tela_video(self):
        update_mode("video")
        self.trocar_frame(TelaConfigVideos(self))

    def mostrar_tela_configs(self):
        self.trocar_frame(TelaConfigs(self))

    def mostrar_tela_continuar(self):
        update_mode("folder")
        self.trocar_frame(TelaContinuar(self))

    def mostrar_tela_imagens(self):
        update_mode("image")
        self.trocar_frame(TelaConfigImagens(self))


if __name__ == "__main__":
    app = App()
    app.mainloop()