# tela_rotulagem.py
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw
from core.utils import list_images, load_yolo_label, yolo_to_pixel, pixel_to_yolo
from core.inference import save_yolo_label
from pathlib import Path

#classe inteiramente responsavel por criar a interface grafica
class LabelingGUI:
    #quando criamos a gui, chamamos o construtor init
    def __init__(self, root, images_dir, labels_dir, labels_list, autosave=True):
        self.root = root #seria a janela do tkinter 
        self.images_dir = images_dir
        self.labels_dir = labels_dir
        self.labels_list = labels_list #uma lista com os nomes das classes (apenas "goat" por enquanto)
        self.autosave = autosave #se true, salva automaticamente ao mudar de imagem

        self.img_files = list_images(images_dir) # lista todas as imagens da pasta
        if not self.img_files: #se a pasta tiver vazia, retorna erro
            raise RuntimeError("Nenhuma imagem encontrada em " + str(images_dir))

        self.index = 0 #indice da imagem atual
        self.current_image = None  #referência à imagem PIL atual
        self.tkimg = None #referência à imagem Tkinter atual, um objeto ImageTk.PhotoImage que é mostrado no canvas
        self.boxes = []  # lista de boxes: tuples (x1,y1,x2,y2,class_id)
        self.selected_box = None #indice da box selecionada na listbox acima
        self.modo = "criacao" # ou "edicao"
        self.acao = None  #pode ser "movendo", "redimensionando", "desenhando", etc.
        self.drawing = False  #flag para indicar se estamos desenhando uma nova caixa(clicou e ainda nao soltou o mouse)
        self.moving = False  #flag para representar se estamos movendo uma bounding box 
        self.start_x = self.start_y = 0 #armazena a posição inicial do mouse ao começar a desenhar uma nova caixa
        self.zoom_factor = 1.0
        self.display_offset = [0, 0]  # [x, y]
        self.pan_start = None

        # ===================== SETUP UI (REFATORADO) =====================

        # Configurar janela principal
        self.root.title("AutoLabeler")
        self.root.minsize(800, 600)

        # Detecta tamanho da tela e ajusta janela inicial
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"{int(screen_w*0.8)}x{int(screen_h*0.8)}")

        # GRID PRINCIPAL RESPONSIVO
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=0)

        # FRAME ESQUERDO (canvas + controles)
        self.left_frame = tk.Frame(root)
        self.left_frame.grid(row=0, column=0, sticky="nsew")

        self.left_frame.rowconfigure(0, weight=1)  # canvas cresce
        self.left_frame.rowconfigure(1, weight=0)  # controles fixos
        self.left_frame.columnconfigure(0, weight=1)

        # FRAME DIREITO (lista de boxes)
        self.right_frame = tk.Frame(root)
        self.right_frame.grid(row=0, column=1, sticky="ns")

        # ===================== CANVAS =====================
        self.canvas = tk.Canvas(self.left_frame, bg="black")
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # ===================== CONTROLES =====================
        self.controls_frame = tk.Frame(self.left_frame)
        self.controls_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)

        # Faz os botões se ajustarem
        for i in range(6):
            self.controls_frame.columnconfigure(i, weight=1)

        # Botões
        tk.Button(self.controls_frame, text="Prev", command=self.prev_image)\
            .grid(row=0, column=0, sticky="ew", padx=2)

        tk.Button(self.controls_frame, text="Next", command=self.next_image)\
            .grid(row=0, column=1, sticky="ew", padx=2)

        tk.Button(self.controls_frame, text="Save", command=self.save_current)\
            .grid(row=0, column=2, sticky="ew", padx=2)

        self.botao_modo = tk.Button(self.controls_frame, text="Modo: Criação", command=self.alternar_modo)
        self.botao_modo.grid(row=0, column=3, sticky="ew", padx=2)

        # Combobox (label)
        self.label_var = tk.StringVar(value=self.labels_list[0])
        self.label_selector = ttk.Combobox(
            self.controls_frame,
            textvariable=self.label_var,
            values=self.labels_list,
            state="readonly"
        )
        self.label_selector.grid(row=0, column=4, sticky="ew", padx=2)

        # Contador
        self.counter_label = tk.Label(self.controls_frame, text="")
        self.counter_label.grid(row=0, column=5, sticky="e", padx=5)

        # ===================== LISTBOX (LATERAL) =====================
        self.box_listbox = tk.Listbox(self.right_frame, width=30)
        self.box_listbox.pack(side="left", fill="y", expand=False)

        scrollbar = tk.Scrollbar(self.right_frame, orient="vertical")
        scrollbar.config(command=self.box_listbox.yview)
        scrollbar.pack(side="right", fill="y")

        self.box_listbox.config(yscrollcommand=scrollbar.set)

        self.box_listbox.bind("<<ListboxSelect>>", self.on_select_listbox)

        # ===================== BINDS =====================
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        self.root.bind_all("<Delete>", self.delete_selected_box)

        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", self.on_zoom)
        self.canvas.bind("<Button-5>", self.on_zoom)

        self.canvas.bind("<ButtonPress-3>", self.on_pan_start)
        self.canvas.bind("<B3-Motion>", self.on_pan_move)

        self.root.bind_all('<Left>', self._on_left_arrow)
        self.root.bind_all('<Right>', self._on_right_arrow)

        self.load_image() #carrega a primeira imagem e seus labels
        self.update_counter()  # Atualiza o contador ao iniciar
    def _on_left_arrow(self, event=None):
        """
        Handler para seta para a esquerda: volta para a imagem anterior.
        """
        self.prev_image()

    def _on_right_arrow(self, event=None):
        """
        Handler para seta para a direita: avança para a próxima imagem.
        """
        self.next_image()


    def alternar_modo(self):
        """
        Alterna entre o modo de criação e o modo de edição.
        Atualiza o texto do botão e o estado atual.
        """
        if self.modo == "criacao":
            self.modo = "edicao"
        else:
            self.modo = "criacao"

        # Atualiza o texto do botão
        self.botao_modo.config(text=f"Modo: {self.modo.capitalize()}")

        # Feedback no terminal (opcional)
        print(f"Modo alterado para: {self.modo}")



    def load_image(self):
        #função para carregar a imagem atual e seus labels
        #essa função é chamada ao iniciar a GUI e ao mudar de imagem (próxima/anterior)

        #constroi o caminho completo da imagem atual
        img_fp = Path(self.images_dir) / self.img_files[self.index]

        #cria uma imagem PIL a partir do arquivo da imagem atual(não é recomendado usar ImageTk diretamente da memoria)
        pil = Image.open(img_fp).convert("RGB") 
        self.current_image = pil

        #cria o caminho do arquivo de labels correspondente à imagem atual
        label_fp = Path(self.labels_dir) / (Path(self.img_files[self.index]).stem + ".txt")
        
        #chama a função load_yolo_label do utils.py para carregar as caixas do arquivo de labels
        yolo_boxes = load_yolo_label(label_fp)
        self.boxes = [] #apenas limpa a lista atual de boxes antes de carregar as novas
        W, H = pil.size #pega a largura e altura da imagem atual

        #converte as caixas do formato YOLO(normalizado) para coordenadas de pixel absolutas e armazena na lista self.boxes
        for b in yolo_boxes:
            cid, x1, y1, x2, y2 = yolo_to_pixel(b, W, H)
            self.boxes.append((x1, y1, x2, y2, b[0]))
        
        self.root.title(f"AutoLabeler – Editando: {self.img_files[self.index]}")
        self.draw_image()
        self.update_counter()  # Garante atualização ao carregar imagem


    def detectar_regiao_box(self, ix, iy, x1, y1, x2, y2, margem=10):
        """
        Retorna qual região da caixa foi clicada:
        - 'inside' se dentro
        - 'left', 'right', 'top', 'bottom' se na borda
        - 'corner' se num canto
        - None se fora
        """
        dentro_x = x1 <= ix <= x2
        dentro_y = y1 <= iy <= y2

        if not (dentro_x and dentro_y):
            return None

        nas_bordas = {
            'left': abs(ix - x1) <= margem,
            'right': abs(ix - x2) <= margem,
            'top': abs(iy - y1) <= margem,
            'bottom': abs(iy - y2) <= margem
        }

        cantos = [(nas_bordas['left'] and nas_bordas['top']),
                (nas_bordas['left'] and nas_bordas['bottom']),
                (nas_bordas['right'] and nas_bordas['top']),
                (nas_bordas['right'] and nas_bordas['bottom'])]

        if any(cantos):
            return 'corner'
        for k, v in nas_bordas.items():
            if v:
                return k
        return 'inside'



    def draw_image(self):
        # Corrige bug de pil não definida e lógica de escala/offset
        pil_img = self.current_image.copy()
        draw = ImageDraw.Draw(pil_img)

        for i, (x1, y1, x2, y2, cid) in enumerate(self.boxes):
            x1, x2 = sorted([x1, x2])
            y1, y2 = sorted([y1, y2])
            draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
            draw.text((x1+4, y1+4), f"{self.labels_list[cid]} ({i})", fill="yellow")

        w, h = pil_img.size
        canvas_w = self.canvas.winfo_width() or 800
        canvas_h = self.canvas.winfo_height() or 800
        scale_base = min(canvas_w / w, canvas_h / h)
        scale = scale_base * self.zoom_factor
        new_w = int(w * scale)
        new_h = int(h * scale)
        pil_resized = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.display_size = pil_resized.size
        self.scale_x = scale
        self.scale_y = scale
        # Centralizar a imagem no canvas
        offset_x = max((canvas_w - new_w) // 2, 0)
        offset_y = max((canvas_h - new_h) // 2, 0)
        self.display_offset = [offset_x, offset_y]
        self.tkimg = ImageTk.PhotoImage(pil_resized)
        self.canvas.delete("all")
        self.canvas.create_image(
            self.display_offset[0],
            self.display_offset[1],
            anchor="nw",
            image=self.tkimg,
            tags="fundo"
        )
        # Desenha as bounding boxes na escala correta
        for i, (x1, y1, x2, y2, cid) in enumerate(self.boxes):
            sx1 = int(x1 * self.scale_x) + self.display_offset[0]
            sy1 = int(y1 * self.scale_y) + self.display_offset[1]
            sx2 = int(x2 * self.scale_x) + self.display_offset[0]
            sy2 = int(y2 * self.scale_y) + self.display_offset[1]
            color = "red"
            if self.selected_box == i:
                color = "cyan"
            self.canvas.create_rectangle(sx1, sy1, sx2, sy2, outline=color, width=3, tags=f"box_{i}")
        self.refresh_listbox()
    def draw_boxes_overlay(self):
        """
        Redesenha a imagem e as caixas no canvas, mantendo o zoom, escala e centralização atuais,
        sem recalcular escala ou offset. Usa exatamente os mesmos parâmetros de draw_image.
        """
        pil_img = self.current_image.copy()
        draw = ImageDraw.Draw(pil_img)
        for i, (x1, y1, x2, y2, cid) in enumerate(self.boxes):
            x1, x2 = sorted([x1, x2])
            y1, y2 = sorted([y1, y2])
            draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
            draw.text((x1+4, y1+4), f"{self.labels_list[cid]} ({i})", fill="yellow")

        # Usa o mesmo tamanho já calculado
        new_w, new_h = self.display_size
        pil_resized = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tkimg = ImageTk.PhotoImage(pil_resized)

        # limpa tudo no canvas e desenha o fundo
        self.canvas.delete("all")
        self.canvas.create_image(
            self.display_offset[0],
            self.display_offset[1],
            anchor="nw",
            image=self.tkimg,
            tags="fundo"
        )

        # redesenha todas as bounding boxes
        for i, (x1, y1, x2, y2, cid) in enumerate(self.boxes):
            sx1 = int(x1 * self.scale_x) + self.display_offset[0]
            sy1 = int(y1 * self.scale_y) + self.display_offset[1]
            sx2 = int(x2 * self.scale_x) + self.display_offset[0]
            sy2 = int(y2 * self.scale_y) + self.display_offset[1]
            color = "red"
            if self.selected_box == i:
                color = "cyan"
            self.canvas.create_rectangle(sx1, sy1, sx2, sy2, outline=color, width=3, tags="box")


    def refresh_listbox(self):
        self.box_listbox.delete(0, tk.END)
        for i, (x1, y1, x2, y2, class_id) in enumerate(self.boxes):
            label_name = self.labels_list[class_id]
            self.box_listbox.insert(tk.END, f"{i+1}: {label_name} ({x1},{y1})-({x2},{y2})")
        
        try:
        # reseta estilos (pode falhar em alguns temas, por isso try/except)
            for i in range(len(self.boxes)):
                self.box_listbox.itemconfig(i, bg="white", fg="black")
        except Exception:
            pass

        if self.selected_box is not None and 0 <= self.selected_box < len(self.boxes):
            self.box_listbox.selection_clear(0, tk.END)
            self.box_listbox.selection_set(self.selected_box)
            # itemconfig para destacar com cor mais acinzentada
            try:
                self.box_listbox.itemconfig(self.selected_box, bg="#d9d9d9")
            except Exception:
                # alguns temas não permitem itemconfig; a selection já dá um destaque padrão
                pass
        else:
            # limpa seleção se nada estiver selecionado
            self.box_listbox.selection_clear(0, tk.END)

    
    def on_button_press(self, event):
        # converte coordenadas do clique
        cx = event.x - self.display_offset[0]
        cy = event.y - self.display_offset[1]

        if cx < 0 or cy < 0 or cx > self.display_size[0] or cy > self.display_size[1]:
            return

        ix = int(cx / self.scale_x)
        iy = int(cy / self.scale_y)

        if self.modo == "edicao":
            self.start_x, self.start_y = ix, iy  # salva posição inicial para comparar com movimento

            # percorre as caixas em ordem inversa (topo primeiro)
            clicked_box = None
            for i, (x1, y1, x2, y2, cid) in enumerate(reversed(self.boxes)):
                margem = 10
                if self.selected_box == len(self.boxes) - 1 - i:
                    margem = 10

                regiao = self.detectar_regiao_box(ix, iy, x1, y1, x2, y2, margem=margem)

                if regiao:
                    clicked_box = len(self.boxes) - 1 - i
                    self.regiao = regiao
                    break

            if clicked_box is not None:
                self.selected_box = clicked_box

                # sincronia com listbox
                self.box_listbox.selection_clear(0, tk.END)
                self.box_listbox.selection_set(clicked_box)
                self.refresh_listbox()

                # ainda não estamos movendo, apenas selecionamos — o arrasto ativará o movimento
                self.acao = None
            else:
                # clicou fora de qualquer box → limpa seleção
                self.selected_box = None
                self.box_listbox.selection_clear(0, tk.END)
                self.refresh_listbox()
                self.acao = None

            self.draw_image()

        elif self.modo == "criacao":
            self.drawing = True
            self.start_x = ix
            self.start_y = iy
            self.temp_rect = None


    def on_drag(self, event):
        cx = event.x - self.display_offset[0]
        cy = event.y - self.display_offset[1]

        cx = max(0, min(self.display_size[0], cx))
        cy = max(0, min(self.display_size[1], cy))

        ix = int(cx / self.scale_x)
        iy = int(cy / self.scale_y)

        # Se estamos no modo de edição e há uma box selecionada
        if self.modo == "edicao" and self.selected_box is not None:
            # detecta se o mouse se moveu o suficiente para considerar um arrasto (>3 px)
            if self.acao is None:
                if abs(ix - self.start_x) > 3 or abs(iy - self.start_y) > 3:
                    # começa a mover ou redimensionar dependendo da região clicada
                    if self.regiao == "inside":
                        self.acao = "movendo"
                        x1, y1, x2, y2, cid = self.boxes[self.selected_box]
                        self.offset_x = ix - x1
                        self.offset_y = iy - y1
                    else:
                        self.acao = "redimensionando"

            # se já está movendo ou redimensionando, continua comportamento normal
            if self.acao == "movendo":
                x1, y1, x2, y2, cid = self.boxes[self.selected_box]
                largura = x2 - x1
                altura = y2 - y1
                novo_x1 = ix - self.offset_x
                novo_y1 = iy - self.offset_y
                novo_x2 = novo_x1 + largura
                novo_y2 = novo_y1 + altura
                self.boxes[self.selected_box] = (novo_x1, novo_y1, novo_x2, novo_y2, cid)
                self.draw_boxes_overlay()
                return

            elif self.acao == "redimensionando":
                x1, y1, x2, y2, cid = self.boxes[self.selected_box]
                if self.regiao == "left":
                    x1 = ix
                elif self.regiao == "right":
                    x2 = ix
                elif self.regiao == "top":
                    y1 = iy
                elif self.regiao == "bottom":
                    y2 = iy
                elif self.regiao == "corner":
                    if abs(ix - x1) < abs(ix - x2):
                        x1 = ix  # clicou no canto esquerdo
                    else:
                        x2 = ix  # clicou no canto direito
                    if abs(iy - y1) < abs(iy - y2):
                        y1 = iy  # clicou no canto superior
                    else:
                        y2 = iy  # clicou no canto inferior

                if x1 > x2: x1, x2 = x2, x1
                if y1 > y2: y1, y2 = y2, y1
                self.boxes[self.selected_box] = (x1, y1, x2, y2, cid)
                self.draw_boxes_overlay()
                return

        if self.modo == "criacao" and self.drawing:
            # Garante que estamos desenhando uma nova caixa (flag self.drawing = True)

            # Converte as coordenadas finais (atuais) e iniciais do desenho
            x2 = ix
            y2 = iy

            # Apaga o retângulo temporário anterior, para atualizar visualmente o traçado
            self.canvas.delete("temp")

            # Converte coordenadas para a escala exibida (em pixels do canvas)
            sx1 = int(self.start_x * self.scale_x) + self.display_offset[0]
            sy1 = int(self.start_y * self.scale_y) + self.display_offset[1]
            sx2 = int(x2 * self.scale_x) + self.display_offset[0]
            sy2 = int(y2 * self.scale_y) + self.display_offset[1]

            # Desenha o retângulo azul temporário no canvas, dando feedback ao usuário
            self.canvas.create_rectangle(sx1, sy1, sx2, sy2, outline="blue", width=2, tags="temp")



    def on_button_release(self, event):
        """
        Essa função é chamada quando o botão esquerdo do mouse é solto.
        Ela finaliza as ações iniciadas por um clique e arrasto (<ButtonPress> + <B1-Motion>).
        Dependendo do modo ativo, ela conclui o desenho, movimento ou redimensionamento das caixas.
        """

        if self.modo == "criacao" and self.drawing:
            # Indica que a fase de desenho terminou
            self.drawing = False

            # Pega as coordenadas do ponto onde o mouse foi solto
            cx = event.x - self.display_offset[0]
            cy = event.y - self.display_offset[1]

            # Se o ponto final estiver fora da área da imagem, cancela o desenho
            if cx < 0 or cy < 0 or cx > self.display_size[0] or cy > self.display_size[1]:
                self.canvas.delete("temp")  # apaga o retângulo temporário azul
                return

            # Converte as coordenadas de exibição para coordenadas da imagem original
            end_x = int(cx / self.scale_x)
            end_y = int(cy / self.scale_y)

            # Garante que (x1, y1) seja o canto superior esquerdo e (x2, y2) o inferior direito
            x1, y1 = min(self.start_x, end_x), min(self.start_y, end_y)
            x2, y2 = max(self.start_x, end_x), max(self.start_y, end_y)

            # Adiciona a nova bounding box à lista de caixas existentes
            # Formato: (x1, y1, x2, y2, classe_id)
            class_id = self.labels_list.index(self.label_var.get())
            self.boxes.append((x1, y1, x2, y2, class_id))
            self.refresh_listbox()
            self.drawing = False
            self.draw_image()

            # Se o modo de salvamento automático estiver ativado, salva o progresso
            if self.autosave:
                self.save_current()

        elif self.modo == "edicao":
            # Se estivermos movendo uma caixa, finaliza o movimento
            if self.acao == "movendo":
                self.moving = False
                self.canvas.delete("temp")  # remove visual temporário (se houver)
                self.refresh_listbox()      # atualiza a lista lateral com as novas coordenadas
                if self.autosave:
                    self.save_current()

            # Se estivermos redimensionando uma caixa, finaliza a ação
            elif self.acao == "redimensionando":
                self.canvas.delete("temp")
                self.refresh_listbox()
                if self.autosave:
                    self.save_current()

            self.acao = None
            self.regiao = None
            self.selected_box = None
            self.moving = False



    def prev_image(self):
        #função para carregar a imagem anterior da lista (se houver)
        if self.index > 0:  #verifica se não estamos na primeira imagem
            if self.autosave:
                #se o autosave estiver ativo, salva as caixas da imagem atual antes de trocar
                self.save_current()
            
            #decrementa o índice da imagem atual para ir à anterior
            self.index -= 1

            #carrega a nova imagem e seus labels correspondentes
            self.load_image()
            self.update_counter()

    def next_image(self):
        #função para avançar para a próxima imagem na lista
        if self.index < len(self.img_files) - 1:  #verifica se não estamos na última
            if self.autosave:
                #salva automaticamente ao trocar de imagem
                self.save_current()
            
            #incrementa o índice da imagem atual
            self.index += 1

            #carrega a nova imagem e seus labels correspondentes
            self.load_image()
            self.update_counter()


    def save_current(self):
        #essa função salva as bounding boxes atuais no formato YOLO (normalizado)
        #é chamada manualmente pelo botão "Save" ou automaticamente se autosave=True

        #pega o nome e caminho da imagem atual
        img_name = self.img_files[self.index]

        #obtém o tamanho original da imagem (necessário para converter pixels → YOLO)
        pil = self.current_image
        W, H = pil.size

        #lista que vai armazenar as caixas convertidas para o formato YOLO
        label_list = []

        #para cada caixa desenhada na imagem:
        for (x1, y1, x2, y2, cid) in self.boxes:
            #converte as coordenadas absolutas (pixels) para normalizadas YOLO (entre 0 e 1)
            yolo = pixel_to_yolo(x1, y1, x2, y2, W, H, class_id=cid)
            label_list.append(yolo)

        #cria o caminho do arquivo .txt correspondente
        label_fp = Path(self.labels_dir) / (Path(img_name).stem + ".txt")


        #salva as caixas no arquivo de texto usando a função save_yolo_label (definida em inference.py)
        save_yolo_label(label_fp, label_list)

        #atualiza a listbox para refletir qualquer modificação nas caixas
        self.refresh_listbox()


    def on_select_listbox(self, event):
        #essa função é chamada quando o usuário seleciona uma caixa na listbox da direita

        #obtém a seleção atual (pode ter mais de uma, mas normalmente é uma só)
        sel = self.box_listbox.curselection()
        if not sel:
            #se não houver seleção, não faz nada
            return
        
        #pega o índice da caixa selecionada
        idx = sel[0]
        self.selected_box = idx  #armazena a referência para uso posterior (ex: exclusão)
        self.draw_image()


    def delete_selected_box(self, event=None):
        """
        Remove a bounding box selecionada. Funciona tanto se a seleção
        vem da listbox quanto se a seleção veio do canvas (self.selected_box).
        Pode ser chamada por tecla Delete (event) ou por botão.
        """
        # 1) tenta pegar a seleção da listbox (se o usuário clicou nela)
        sel = self.box_listbox.curselection()
        if sel:
            idx = sel[0]
        elif self.selected_box is not None:
            # 2) se não há seleção na listbox, usa a seleção do canvas
            idx = self.selected_box
        else:
            # nada selecionado → nada a fazer
            return

        # valida índice
        if not (0 <= idx < len(self.boxes)):
            return

        # remove a caixa
        self.boxes.pop(idx)

        # se a caixa removida era anterior à seleção, ajustar selected_box
        if self.selected_box is not None:
            if self.selected_box == idx:
                # removemos a própria seleção → limpar seleção
                self.selected_box = None
            elif self.selected_box > idx:
                # removemos um item anterior → shift nos índices
                self.selected_box -= 1

        # atualiza UI
        self.draw_image()
        self.refresh_listbox()

        # limpa seleção na listbox
        self.box_listbox.selection_clear(0, tk.END)

        # salva se necessário
        if self.autosave:
            self.save_current()

    def on_zoom(self, event):
        min_zoom = 0.2
        max_zoom = 10.0
        old_zoom = self.zoom_factor

        if hasattr(event, 'num'):
            if event.num == 4:
                self.zoom_factor = min(self.zoom_factor * 1.1, max_zoom)
            elif event.num == 5:
                self.zoom_factor = max(self.zoom_factor / 1.1, min_zoom)
        elif hasattr(event, 'delta'):
            if event.delta > 0:
                self.zoom_factor = min(self.zoom_factor * 1.1, max_zoom)
            else:
                self.zoom_factor = max(self.zoom_factor / 1.1, min_zoom)

        # Ajusta o offset para manter o ponto do mouse fixo ao dar zoom
        if event is not None:
            mx, my = event.x, event.y
            scale = self.zoom_factor / old_zoom
            self.display_offset[0] = int(mx - scale * (mx - self.display_offset[0]))
            self.display_offset[1] = int(my - scale * (my - self.display_offset[1]))

        self.draw_image()

    def on_pan_start(self, event):
        self.pan_start = (event.x, event.y)

    def on_pan_move(self, event):
        if self.pan_start is not None:
            # Calcula o deslocamento
            dx = event.x - self.pan_start[0]
            dy = event.y - self.pan_start[1]

            # Atualiza o deslocamento da imagem
            self.display_offset[0] += dx
            self.display_offset[1] += dy

            # Redesenha a imagem e as caixas
            self.draw_boxes_overlay()

            # Atualiza a posição inicial para o próximo movimento
            self.pan_start = (event.x, event.y)

    def update_counter(self):
        total = len(self.img_files)
        atual = self.index + 1 if total > 0 else 0
        self.counter_label.config(text=f"{atual}/{total}")

