# tela_rotulagem.py
import time
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
        self.regiao = None #alça ou regiao clicada: 'tl', 'tc', 'tr', 'mr', 'br', 'bc', 'bl', 'ml', 'inside'
        self.drawing = False  #flag para indicar se estamos desenhando uma nova caixa(clicou e ainda nao soltou o mouse)
        self.moving = False  #flag para representar se estamos movendo uma bounding box 
        self.start_x = self.start_y = 0 #armazena a posição inicial do mouse ao começar a desenhar uma nova caixa
        self.drag_start_x = self.drag_start_y = 0
        self.drag_start_box = None
        self.boxes_before_drag = None
        self.undo_stack = []
        self.current_cursor = None
        self.last_backspace_time = 0.0
        self.zoom_factor = 1.0
        self.display_offset = [0, 0]  # [x, y]
        self.pan_start = None

        # Configurações de Espessura da BB e Hover
        try:
            from core.config_manager import load_config
            cfg = load_config()
            self.box_thickness = int(cfg.get("box_thickness", 2))
        except Exception:
            self.box_thickness = 2

        self.hovered_box = None
        self.hover_timer = None
        self.hover_badge_visible = False

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

        # Faz os controles se ajustarem
        for i in range(9):
            self.controls_frame.columnconfigure(i, weight=1)

        # Botões
        tk.Button(self.controls_frame, text="Prev", command=self.prev_image)\
            .grid(row=0, column=0, sticky="ew", padx=2)

        tk.Button(self.controls_frame, text="Next", command=self.next_image)\
            .grid(row=0, column=1, sticky="ew", padx=2)

        tk.Button(self.controls_frame, text="Save", command=self.save_current)\
            .grid(row=0, column=2, sticky="ew", padx=2)

        self.botao_undo = tk.Button(self.controls_frame, text="Desfazer (Ctrl+Z)", command=self.undo)
        self.botao_undo.grid(row=0, column=3, sticky="ew", padx=2)

        self.botao_repetir = tk.Button(self.controls_frame, text="Repetir Anterior (R)", command=self.repetir_boxes_anterior)
        self.botao_repetir.grid(row=0, column=4, sticky="ew", padx=2)

        self.botao_modo = tk.Button(self.controls_frame, text="Modo: Criação (M)", command=self.alternar_modo)
        self.botao_modo.grid(row=0, column=5, sticky="ew", padx=2)

        # Combobox (label)
        self.label_var = tk.StringVar(value=self.labels_list[0])
        self.label_selector = ttk.Combobox(
            self.controls_frame,
            textvariable=self.label_var,
            values=self.labels_list,
            state="readonly"
        )
        self.label_selector.grid(row=0, column=6, sticky="ew", padx=2)

        # Indicador e controle de espessura de Bounding Box (atalhos [ e ])
        thickness_frame = tk.Frame(self.controls_frame)
        thickness_frame.grid(row=0, column=7, sticky="ew", padx=2)
        tk.Button(thickness_frame, text="-", width=2, command=self.diminuir_espessura)\
            .pack(side="left", padx=1)
        self.thickness_label = tk.Label(
            thickness_frame,
            text=f"BB: {self.box_thickness}px",
            relief="groove",
            padx=4,
            pady=2
        )
        self.thickness_label.pack(side="left", fill="both", expand=True)
        tk.Button(thickness_frame, text="+", width=2, command=self.aumentar_espessura)\
            .pack(side="left", padx=1)

        # Contador
        self.counter_label = tk.Label(self.controls_frame, text="")
        self.counter_label.grid(row=0, column=8, sticky="e", padx=5)

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
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<Leave>", self.on_mouse_leave)

        self.root.bind_all("<Delete>", self.delete_selected_box)

        # Zoom (mouse wheel, touchpads e botões de scroll)
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", self.on_zoom)
        self.canvas.bind("<Button-5>", self.on_zoom)
        # Pinch-to-zoom / scroll com Ctrl no touchpad
        self.canvas.bind("<Control-MouseWheel>", self.on_zoom)
        self.canvas.bind("<Control-Button-4>", self.on_zoom)
        self.canvas.bind("<Control-Button-5>", self.on_zoom)
        # Binds no root também caso o foco esteja fora do canvas ao usar o touchpad
        self.root.bind("<Control-MouseWheel>", self.on_zoom)
        self.root.bind("<Control-Button-4>", self.on_zoom)
        self.root.bind("<Control-Button-5>", self.on_zoom)

        self.canvas.bind("<ButtonPress-3>", self.on_right_press)
        self.canvas.bind("<B3-Motion>", self.on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self.on_right_release)

        self.root.bind_all('<Left>', self._on_left_arrow)
        self.root.bind_all('<Right>', self._on_right_arrow)

        # Atalhos para modo (M) e repetição de caixas do frame anterior (R)
        self.root.bind_all("<m>", self.alternar_modo)
        self.root.bind_all("<M>", self.alternar_modo)
        self.root.bind_all("<r>", self.repetir_boxes_anterior)
        self.root.bind_all("<R>", self.repetir_boxes_anterior)

        # Atalhos para espessura da BB
        self.root.bind_all("<bracketleft>", self.diminuir_espessura)
        self.root.bind_all("<bracketright>", self.aumentar_espessura)
        self.root.bind_all("[", self.diminuir_espessura)
        self.root.bind_all("]", self.aumentar_espessura)
        self.root.bind_all("-", self.diminuir_espessura)
        self.root.bind_all("+", self.aumentar_espessura)
        self.root.bind_all("=", self.aumentar_espessura)

        # Atalho Ctrl+Z para desfazer
        self.root.bind_all("<Control-z>", self.undo)
        self.root.bind_all("<Control-Z>", self.undo)

        # Atalho Backspace duplo para excluir imagem e label
        self.root.bind_all("<BackSpace>", self.on_backspace)

        self.load_image() #carrega a primeira imagem e seus labels
        self.update_counter()  # Atualiza o contador ao iniciar
        self.set_canvas_cursor("create")
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


    def alternar_modo(self, event=None):
        """
        Alterna entre o modo de criação e o modo de edição.
        Atualiza o texto do botão e o estado atual.
        """
        if self._is_entry_focused():
            return
        self._clear_hover()
        if self.modo == "criacao":
            self.modo = "edicao"
            self.set_canvas_cursor("default")
        else:
            self.modo = "criacao"
            self.set_canvas_cursor("create")

        # Atualiza o texto do botão indicando o atalho (M)
        modo_str = "Criação" if self.modo == "criacao" else "Edição"
        self.botao_modo.config(text=f"Modo: {modo_str} (M)")
        self.redraw_canvas_boxes()
        print(f"Modo alterado para: {self.modo}")

    def push_undo(self):
        """Salva uma cópia do estado atual das boxes na pilha de desfazer (máx 50)."""
        self.undo_stack.append([tuple(b) for b in self.boxes])
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    def undo(self, event=None):
        """Restaura o estado anterior das bounding boxes (Ctrl+Z)."""
        if self._is_entry_focused():
            return
        if not self.undo_stack:
            print("Nada para desfazer.")
            return

        self._clear_hover()
        prev_boxes = self.undo_stack.pop()
        self.boxes = [tuple(b) for b in prev_boxes]
        self.selected_box = None
        self.drag_start_box = None
        self.acao = None
        self.regiao = None
        self.moving = False
        self.redraw_canvas_boxes()
        self.refresh_listbox()
        if self.autosave:
            self.save_current()
        print(f"Ação desfeita (Ctrl+Z). Caixas restantes: {len(self.boxes)}")

    def repetir_boxes_anterior(self, event=None):
        """
        Copia as bounding boxes do frame anterior para o frame atual.
        Útil para sequências onde a posição quase não mudou.
        Atalho: tecla 'r' ou 'R'
        """
        if self._is_entry_focused():
            return
        if self.index <= 0:
            print("Não há frame anterior para copiar.")
            return

        self._clear_hover()
        prev_img_file = self.img_files[self.index - 1]
        prev_label_fp = Path(self.labels_dir) / (Path(prev_img_file).stem + ".txt")
        prev_yolo_boxes = load_yolo_label(prev_label_fp)

        if not prev_yolo_boxes:
            print(f"Nenhuma bounding box encontrada no frame anterior ({prev_img_file}).")
            return

        if self.current_image is None:
            return

        # Salva o estado atual para permitir Ctrl+Z
        self.push_undo()

        W, H = self.current_image.size
        self.boxes = []
        for b in prev_yolo_boxes:
            cid, x1, y1, x2, y2 = yolo_to_pixel(b, W, H)
            self.boxes.append((x1, y1, x2, y2, b[0]))

        self.selected_box = None
        self.redraw_canvas_boxes()
        self.refresh_listbox()

        if self.autosave:
            self.save_current()

        print(f"{len(self.boxes)} box(es) copiada(s) do frame anterior ({prev_img_file}).")

    def _is_entry_focused(self):
        focus = self.root.focus_get()
        if isinstance(focus, ttk.Combobox):
            return str(focus.cget("state")) != "readonly"
        return isinstance(focus, (tk.Entry, ttk.Entry))

    def alterar_espessura(self, delta):
        nova = max(1, min(10, self.box_thickness + delta))
        if nova != self.box_thickness:
            self.box_thickness = nova
            self.atualizar_label_espessura()
            self.redraw_canvas_boxes()
            try:
                from core.config_manager import update_config_fields
                update_config_fields(box_thickness=self.box_thickness)
            except Exception:
                pass

    def diminuir_espessura(self, event=None):
        if self._is_entry_focused():
            return
        self.alterar_espessura(-1)

    def aumentar_espessura(self, event=None):
        if self._is_entry_focused():
            return
        self.alterar_espessura(1)

    def atualizar_label_espessura(self):
        if hasattr(self, 'thickness_label') and self.thickness_label.winfo_exists():
            self.thickness_label.config(text=f"BB: {self.box_thickness}px")

    def set_canvas_cursor(self, cursor_type):
        """
        Define o cursor do canvas de acordo com o tipo semântico, com cache
        para evitar chamadas redundantes e garantir máxima fluidez e responsividade.
        """
        if getattr(self, 'current_cursor', None) == cursor_type:
            return
        self.current_cursor = cursor_type

        cursor_map = {
            'default': ('arrow', 'left_ptr', 'default'),
            'move': ('fleur', 'move', 'size_all', 'arrow'),
            'create': ('crosshair', 'tcross', 'plus', 'arrow'),
            'tl': ('nwse-resize', 'size_nw_se', 'top_left_corner', 'sizing', 'arrow'),
            'br': ('nwse-resize', 'size_nw_se', 'bottom_right_corner', 'sizing', 'arrow'),
            'tr': ('nesw-resize', 'size_ne_sw', 'top_right_corner', 'sizing', 'arrow'),
            'bl': ('nesw-resize', 'size_ne_sw', 'bottom_left_corner', 'sizing', 'arrow'),
            'tc': ('ns-resize', 'sb_v_double_arrow', 'size_ns', 'arrow'),
            'bc': ('ns-resize', 'sb_v_double_arrow', 'size_ns', 'arrow'),
            'ml': ('ew-resize', 'sb_h_double_arrow', 'size_we', 'arrow'),
            'mr': ('ew-resize', 'sb_h_double_arrow', 'size_we', 'arrow'),
        }
        targets = cursor_map.get(cursor_type, ('arrow',))
        for c in targets:
            try:
                self.canvas.config(cursor=c)
                break
            except Exception:
                continue

    def _get_box_canvas_handles(self, box_idx):
        """
        Retorna as posições das 8 alças (handles) em coordenadas do Canvas para a caixa box_idx.
        """
        if not (0 <= box_idx < len(self.boxes)):
            return {}
        x1, y1, x2, y2, _ = self.boxes[box_idx]
        sx1 = int(min(x1, x2) * self.scale_x) + self.display_offset[0]
        sx2 = int(max(x1, x2) * self.scale_x) + self.display_offset[0]
        sy1 = int(min(y1, y2) * self.scale_y) + self.display_offset[1]
        sy2 = int(max(y1, y2) * self.scale_y) + self.display_offset[1]
        sxm = (sx1 + sx2) // 2
        sym = (sy1 + sy2) // 2

        return {
            'tl': (sx1, sy1),
            'tc': (sxm, sy1),
            'tr': (sx2, sy1),
            'mr': (sx2, sym),
            'br': (sx2, sy2),
            'bc': (sxm, sy2),
            'bl': (sx1, sy2),
            'ml': (sx1, sym),
        }

    def _hit_test_box(self, box_idx, canvas_x, canvas_y, hit_radius=8):
        """
        Verifica onde o cursor tocou na caixa:
        - Retorna o nome da alça ('tl', 'tc', 'tr', 'mr', 'br', 'bc', 'bl', 'ml') se tocou numa alça.
        - Retorna 'inside' se tocou no interior da caixa.
        - Retorna None se estiver fora.
        """
        if not (0 <= box_idx < len(self.boxes)):
            return None

        # 1. Testa primeiro as 8 alças (prioridade máxima e área confortável de clique)
        handles = self._get_box_canvas_handles(box_idx)
        for h_name, (hx, hy) in handles.items():
            if abs(canvas_x - hx) <= hit_radius and abs(canvas_y - hy) <= hit_radius:
                return h_name

        # 2. Testa o interior da bounding box
        x1, y1, x2, y2, _ = self.boxes[box_idx]
        sx1 = int(min(x1, x2) * self.scale_x) + self.display_offset[0]
        sx2 = int(max(x1, x2) * self.scale_x) + self.display_offset[0]
        sy1 = int(min(y1, y2) * self.scale_y) + self.display_offset[1]
        sy2 = int(max(y1, y2) * self.scale_y) + self.display_offset[1]

        if sx1 <= canvas_x <= sx2 and sy1 <= canvas_y <= sy2:
            return 'inside'

        return None

    def _draw_handles(self, box_idx, fill_color, outline_color="#000000"):
        """
        Desenha as 8 alças quadradas (8x8 px) ao redor da caixa box_idx no Canvas.
        """
        if not (0 <= box_idx < len(self.boxes)):
            return
        handles = self._get_box_canvas_handles(box_idx)
        r = 4  # Meio-tamanho: quadrado de 8x8 pixels na tela
        for hx, hy in handles.values():
            self.canvas.create_rectangle(
                hx - r, hy - r, hx + r, hy + r,
                fill=fill_color,
                outline=outline_color,
                width=1,
                tags=("box", "handle")
            )

    def _clear_hover(self):
        if self.hover_timer is not None:
            self.root.after_cancel(self.hover_timer)
            self.hover_timer = None
        if self.hovered_box is not None or self.hover_badge_visible:
            self.hovered_box = None
            self.hover_badge_visible = False
            self.canvas.delete("hover_badge")
            self.redraw_canvas_boxes()

    def on_mouse_leave(self, event=None):
        self._clear_hover()
        default_cur = "create" if self.modo == "criacao" else "default"
        self.set_canvas_cursor(default_cur)

    def on_mouse_move(self, event):
        if self.drawing or self.moving or self.acao is not None or self.pan_start is not None:
            self._clear_hover()
            return

        cx = event.x - self.display_offset[0]
        cy = event.y - self.display_offset[1]

        if not hasattr(self, 'display_size') or cx < 0 or cy < 0 or cx > self.display_size[0] or cy > self.display_size[1]:
            self._clear_hover()
            default_cur = "create" if self.modo == "criacao" else "default"
            self.set_canvas_cursor(default_cur)
            return

        ix = int(cx / self.scale_x)
        iy = int(cy / self.scale_y)

        hover_regiao = None
        target_box = None

        # 1. Prioriza a caixa já selecionada se o cursor estiver sobre suas alças ou interior
        if self.selected_box is not None and 0 <= self.selected_box < len(self.boxes):
            hit = self._hit_test_box(self.selected_box, event.x, event.y, hit_radius=8)
            if hit:
                hover_regiao = hit
                target_box = self.selected_box

        # 2. Se não estiver sobre a selecionada, testa as outras caixas (do topo para o fundo)
        if hover_regiao is None:
            for i in range(len(self.boxes) - 1, -1, -1):
                hit = self._hit_test_box(i, event.x, event.y, hit_radius=8)
                if hit:
                    hover_regiao = hit
                    target_box = i
                    break

        if hover_regiao is not None:
            if hover_regiao == "inside":
                self.set_canvas_cursor("move")
            else:
                self.set_canvas_cursor(hover_regiao)

            # Atualiza a caixa sob hover e exibe as 8 alças correspondentes
            if self.hovered_box != target_box:
                if self.hover_timer is not None:
                    self.root.after_cancel(self.hover_timer)
                    self.hover_timer = None
                self.hover_badge_visible = False
                self.hovered_box = target_box
                self.redraw_canvas_boxes()
                self.hover_timer = self.root.after(500, self._trigger_hover_badge)
        else:
            default_cur = "create" if self.modo == "criacao" else "default"
            self.set_canvas_cursor(default_cur)
            if self.hovered_box is not None:
                self._clear_hover()

    def _trigger_hover_badge(self):
        self.hover_timer = None
        if self.hovered_box is not None and 0 <= self.hovered_box < len(self.boxes):
            self.hover_badge_visible = True
            self._draw_hover_badge(self.hovered_box)

    def _draw_hover_badge(self, idx):
        self.canvas.delete("hover_badge")
        if not (0 <= idx < len(self.boxes)):
            return

        x1, y1, x2, y2, cid = self.boxes[idx]
        x_min, x_max = min(x1, x2), max(x1, x2)
        y_min, y_max = min(y1, y2), max(y1, y2)

        sx1 = int(x_min * self.scale_x) + self.display_offset[0]
        sy1 = int(y_min * self.scale_y) + self.display_offset[1]

        class_name = self.labels_list[cid] if cid < len(self.labels_list) else str(cid)
        badge_text = f" {class_name} (#{idx + 1}) "

        badge_y = sy1 - 22 if sy1 >= 25 else sy1 + 4
        badge_x = max(2, sx1)

        text_id = self.canvas.create_text(
            badge_x + 5,
            badge_y + 10,
            text=badge_text,
            fill="#ffffff",
            font=("Helvetica", 9, "bold"),
            anchor="w",
            tags="hover_badge"
        )
        bbox = self.canvas.bbox(text_id)
        if bbox:
            bx1, by1, bx2, by2 = bbox
            pad = 3
            bg_id = self.canvas.create_rectangle(
                bx1 - pad, by1 - pad, bx2 + pad, by2 + pad,
                fill="#1e1e1e",
                outline="#ffcc00",
                width=1,
                tags="hover_badge"
            )
            self.canvas.tag_lower(bg_id, text_id)

    def redraw_canvas_boxes(self):
        """
        Redesenha todas as bounding boxes exclusivamente no Canvas Tkinter,
        mantendo a imagem PIL limpa e suportando espessura variável e highlights.
        """
        self.canvas.delete("box")
        self.canvas.delete("hover_badge")

        for i, (x1, y1, x2, y2, cid) in enumerate(self.boxes):
            sx1 = int(min(x1, x2) * self.scale_x) + self.display_offset[0]
            sy1 = int(min(y1, y2) * self.scale_y) + self.display_offset[1]
            sx2 = int(max(x1, x2) * self.scale_x) + self.display_offset[0]
            sy2 = int(max(y1, y2) * self.scale_y) + self.display_offset[1]

            width = self.box_thickness
            if self.selected_box == i:
                color = "cyan"
                width = max(width + 1, 2)
            elif self.hovered_box == i:
                color = "#ffcc00"  # Destaque em amarelo ouro ao passar o mouse
                width = max(width + 1, 2)
            else:
                color = "red"

            self.canvas.create_rectangle(
                sx1, sy1, sx2, sy2,
                outline=color,
                width=width,
                tags=("box", f"box_{i}")
            )

        # Desenha as 8 alças (para caixa selecionada e/ou com hover)
        # Primeiro a hovered (se diferente da selecionada)
        if self.hovered_box is not None and self.hovered_box != self.selected_box:
            self._draw_handles(self.hovered_box, fill_color="#ffeb3b", outline_color="#333333")

        # Em seguida a selecionada (com destaque cyan/azul piscina)
        if self.selected_box is not None:
            self._draw_handles(self.selected_box, fill_color="#00ffff", outline_color="#002233")

        if self.hover_badge_visible and self.hovered_box is not None and 0 <= self.hovered_box < len(self.boxes):
            self._draw_hover_badge(self.hovered_box)

    def load_image(self):
        self._clear_hover()
        self.undo_stack = []
        self.boxes_before_drag = None

        # Se não há mais imagens na pasta
        if not self.img_files:
            self.current_image = None
            self.tkimg = None
            self.boxes = []
            self.selected_box = None
            self.canvas.delete("all")
            self.box_listbox.delete(0, tk.END)
            self.root.title("AutoLabeler – Todas as imagens foram excluídas")
            self.update_counter()
            return

        # Garante que index esteja dentro dos limites
        self.index = max(0, min(self.index, len(self.img_files) - 1))

        # constroi o caminho completo da imagem atual
        img_fp = Path(self.images_dir) / self.img_files[self.index]

        # abre e converte a imagem liberando o descritor de arquivo
        with Image.open(img_fp) as pil:
            self.current_image = pil.convert("RGB")

        # cria o caminho do arquivo de labels correspondente à imagem atual
        label_fp = Path(self.labels_dir) / (Path(self.img_files[self.index]).stem + ".txt")
        
        # chama a função load_yolo_label do utils.py para carregar as caixas do arquivo de labels
        yolo_boxes = load_yolo_label(label_fp)
        self.boxes = []
        W, H = self.current_image.size

        # converte as caixas do formato YOLO(normalizado) para coordenadas de pixel absolutas
        for b in yolo_boxes:
            cid, x1, y1, x2, y2 = yolo_to_pixel(b, W, H)
            self.boxes.append((x1, y1, x2, y2, b[0]))
        
        self.root.title(f"AutoLabeler – Editando: {self.img_files[self.index]}")
        self.draw_image(recenter=True)
        self.update_counter()

    def on_backspace(self, event=None):
        """
        Detecta dois pressionamentos rápidos de Backspace (< 0.6s)
        para excluir a imagem atual e seu respectivo arquivo label.txt do disco.
        """
        if self._is_entry_focused():
            return

        if not self.img_files or not (0 <= self.index < len(self.img_files)):
            return

        now = time.time()
        if now - self.last_backspace_time < 0.6:
            self.last_backspace_time = 0.0
            self._delete_current_image()
        else:
            self.last_backspace_time = now
            current_name = self.img_files[self.index]
            self.root.title(f"⚠️ Pressione Backspace novamente para EXCLUIR {current_name}!")
            self.root.after(700, self._restore_title_after_backspace)

    def _restore_title_after_backspace(self):
        if self.img_files and 0 <= self.index < len(self.img_files):
            self.root.title(f"AutoLabeler – Editando: {self.img_files[self.index]}")

    def _delete_current_image(self):
        """Exclui o arquivo da imagem atual e seu label .txt correspondente do disco."""
        if not self.img_files or not (0 <= self.index < len(self.img_files)):
            return

        self._clear_hover()
        img_name = self.img_files[self.index]
        img_fp = Path(self.images_dir) / img_name
        label_fp = Path(self.labels_dir) / (Path(img_name).stem + ".txt")

        # Libera referências à imagem antes de excluir o arquivo do disco
        self.current_image = None
        self.tkimg = None

        # Exclui imagem
        try:
            if img_fp.exists():
                img_fp.unlink()
                print(f"Arquivo de imagem excluído: {img_fp}")
        except Exception as e:
            print(f"Erro ao excluir arquivo de imagem {img_fp}: {e}")

        # Exclui arquivo de anotações .txt
        try:
            if label_fp.exists():
                label_fp.unlink()
                print(f"Arquivo de label excluído: {label_fp}")
        except Exception as e:
            print(f"Erro ao excluir arquivo de label {label_fp}: {e}")

        # Remove da lista de imagens
        self.img_files.pop(self.index)

        # Ajusta o índice
        if self.index >= len(self.img_files):
            self.index = max(0, len(self.img_files) - 1)

        # Carrega a próxima imagem da lista
        self.load_image()
        self.update_counter()


    def draw_image(self, recenter=True):
        if self.current_image is None:
            return

        pil_img = self.current_image

        w, h = pil_img.size
        canvas_w = self.canvas.winfo_width() or 800
        canvas_h = self.canvas.winfo_height() or 800
        scale_base = min(canvas_w / w, canvas_h / h)
        scale = scale_base * self.zoom_factor
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        pil_resized = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.display_size = pil_resized.size
        self.scale_x = scale
        self.scale_y = scale

        if recenter:
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
        self.redraw_canvas_boxes()
        self.refresh_listbox()

    def draw_boxes_overlay(self):
        """
        Redesenha as caixas no canvas mantendo o fundo atual.
        """
        self.redraw_canvas_boxes()


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

    
    def _find_clicked_box(self, canvas_x, canvas_y):
        """Retorna (box_idx, regiao) se o clique atingiu uma alça ou o interior de uma caixa."""
        # 1. Se já há uma caixa selecionada, prioriza suas alças e interior
        if self.selected_box is not None and 0 <= self.selected_box < len(self.boxes):
            hit = self._hit_test_box(self.selected_box, canvas_x, canvas_y, hit_radius=8)
            if hit:
                return self.selected_box, hit

        # 2. Testa todas as caixas em ordem inversa (do topo para o fundo)
        for i in range(len(self.boxes) - 1, -1, -1):
            hit = self._hit_test_box(i, canvas_x, canvas_y, hit_radius=8)
            if hit:
                return i, hit

        return None, None

    def _start_box_interaction(self, event, clicked_box, clicked_regiao):
        """Inicia o movimento ou redimensionamento da bounding box."""
        cx = event.x - self.display_offset[0]
        cy = event.y - self.display_offset[1]
        ix = int(cx / self.scale_x)
        iy = int(cy / self.scale_y)

        self.boxes_before_drag = [tuple(b) for b in self.boxes]
        self.drag_start_x = ix
        self.drag_start_y = iy
        self.selected_box = clicked_box
        self.regiao = clicked_regiao
        self.drag_start_box = self.boxes[clicked_box]
        self.acao = None

        self.box_listbox.selection_clear(0, tk.END)
        self.box_listbox.selection_set(clicked_box)
        self.refresh_listbox()
        self.redraw_canvas_boxes()

    def _update_box_drag(self, event):
        """Atualiza a posição ou tamanho da bounding box durante o arrasto."""
        if self.selected_box is None or self.drag_start_box is None:
            return

        cx = event.x - self.display_offset[0]
        cy = event.y - self.display_offset[1]
        if not hasattr(self, 'display_size'):
            return

        cx = max(0, min(self.display_size[0], cx))
        cy = max(0, min(self.display_size[1], cy))
        ix = int(cx / self.scale_x)
        iy = int(cy / self.scale_y)

        if self.acao is None:
            if abs(ix - self.drag_start_x) > 2 or abs(iy - self.drag_start_y) > 2:
                if self.regiao == "inside":
                    self.acao = "movendo"
                    self.moving = True
                else:
                    self.acao = "redimensionando"

        if self.acao == "movendo":
            orig_x1, orig_y1, orig_x2, orig_y2, cid = self.drag_start_box
            x1, x2 = min(orig_x1, orig_x2), max(orig_x1, orig_x2)
            y1, y2 = min(orig_y1, orig_y2), max(orig_y1, orig_y2)
            w = x2 - x1
            h = y2 - y1

            dx = ix - self.drag_start_x
            dy = iy - self.drag_start_y

            new_x1 = x1 + dx
            new_y1 = y1 + dy
            new_x2 = new_x1 + w
            new_y2 = new_y1 + h

            if self.current_image is not None:
                img_w, img_h = self.current_image.size
                if new_x1 < 0:
                    new_x1 = 0
                    new_x2 = w
                elif new_x2 > img_w:
                    new_x2 = img_w
                    new_x1 = max(0, img_w - w)

                if new_y1 < 0:
                    new_y1 = 0
                    new_y2 = h
                elif new_y2 > img_h:
                    new_y2 = img_h
                    new_y1 = max(0, img_h - h)

            self.boxes[self.selected_box] = (int(new_x1), int(new_y1), int(new_x2), int(new_y2), cid)
            self.redraw_canvas_boxes()

        elif self.acao == "redimensionando":
            orig_x1, orig_y1, orig_x2, orig_y2, cid = self.drag_start_box
            x1, x2 = min(orig_x1, orig_x2), max(orig_x1, orig_x2)
            y1, y2 = min(orig_y1, orig_y2), max(orig_y1, orig_y2)

            if self.regiao == "tl":
                x1 = min(ix, x2 - 2)
                y1 = min(iy, y2 - 2)
            elif self.regiao == "tc":
                y1 = min(iy, y2 - 2)
            elif self.regiao == "tr":
                x2 = max(ix, x1 + 2)
                y1 = min(iy, y2 - 2)
            elif self.regiao == "mr":
                x2 = max(ix, x1 + 2)
            elif self.regiao == "br":
                x2 = max(ix, x1 + 2)
                y2 = max(iy, y1 + 2)
            elif self.regiao == "bc":
                y2 = max(iy, y1 + 2)
            elif self.regiao == "bl":
                x1 = min(ix, x2 - 2)
                y2 = max(iy, y1 + 2)
            elif self.regiao == "ml":
                x1 = min(ix, x2 - 2)

            self.boxes[self.selected_box] = (int(x1), int(y1), int(x2), int(y2), cid)
            self.redraw_canvas_boxes()

    def _finish_box_interaction(self):
        """Finaliza a interação de mover/redimensionar e salva no undo se houve modificação."""
        if self.acao in ("movendo", "redimensionando") and self.selected_box is not None:
            x1, y1, x2, y2, cid = self.boxes[self.selected_box]
            nx1, nx2 = min(x1, x2), max(x1, x2)
            ny1, ny2 = min(y1, y2), max(y1, y2)
            novo_box = (int(nx1), int(ny1), int(nx2), int(ny2), cid)

            if self.boxes_before_drag is not None and self.boxes_before_drag != [tuple(b) for b in self.boxes]:
                self.undo_stack.append(self.boxes_before_drag)
                if len(self.undo_stack) > 50:
                    self.undo_stack.pop(0)

            self.boxes[self.selected_box] = novo_box
            self.canvas.delete("temp")
            self.refresh_listbox()
            if self.autosave:
                self.save_current()

        self.acao = None
        self.regiao = None
        self.moving = False
        self.boxes_before_drag = None
        self.redraw_canvas_boxes()

    def on_button_press(self, event):
        self._clear_hover()
        cx = event.x - self.display_offset[0]
        cy = event.y - self.display_offset[1]

        if not hasattr(self, 'display_size') or cx < 0 or cy < 0 or cx > self.display_size[0] or cy > self.display_size[1]:
            return

        ix = int(cx / self.scale_x)
        iy = int(cy / self.scale_y)

        if self.modo == "criacao":
            # No modo Criação: Botão ESQUERDO SEMPRE desenha nova bounding box
            self.drawing = True
            self.start_x = ix
            self.start_y = iy
            self.temp_rect = None

        elif self.modo == "edicao":
            # No modo Edição: Botão ESQUERDO move/redimensiona se clicou na caixa/alça, ou desmarca se clicou fora
            clicked_box, clicked_regiao = self._find_clicked_box(event.x, event.y)
            if clicked_box is not None:
                self._start_box_interaction(event, clicked_box, clicked_regiao)
            else:
                self.selected_box = None
                self.regiao = None
                self.acao = None
                self.drag_start_box = None
                self.box_listbox.selection_clear(0, tk.END)
                self.refresh_listbox()
                self.redraw_canvas_boxes()

    def on_drag(self, event):
        cx = event.x - self.display_offset[0]
        cy = event.y - self.display_offset[1]

        if not hasattr(self, 'display_size'):
            return

        cx = max(0, min(self.display_size[0], cx))
        cy = max(0, min(self.display_size[1], cy))
        ix = int(cx / self.scale_x)
        iy = int(cy / self.scale_y)

        if self.modo == "criacao" and self.drawing:
            # Atualiza retângulo azul temporário
            self.canvas.delete("temp")
            sx1 = int(self.start_x * self.scale_x) + self.display_offset[0]
            sy1 = int(self.start_y * self.scale_y) + self.display_offset[1]
            sx2 = int(ix * self.scale_x) + self.display_offset[0]
            sy2 = int(iy * self.scale_y) + self.display_offset[1]
            self.canvas.create_rectangle(sx1, sy1, sx2, sy2, outline="blue", width=self.box_thickness, tags="temp")

        elif self.modo == "edicao":
            self._update_box_drag(event)

    def on_button_release(self, event):
        """Finaliza ações iniciadas com o botão esquerdo."""
        self._clear_hover()

        if self.modo == "criacao" and self.drawing:
            self.drawing = False
            cx = event.x - self.display_offset[0]
            cy = event.y - self.display_offset[1]

            if not hasattr(self, 'display_size') or cx < 0 or cy < 0 or cx > self.display_size[0] or cy > self.display_size[1]:
                self.canvas.delete("temp")
                return

            end_x = int(cx / self.scale_x)
            end_y = int(cy / self.scale_y)

            x1, y1 = min(self.start_x, end_x), min(self.start_y, end_y)
            x2, y2 = max(self.start_x, end_x), max(self.start_y, end_y)

            if abs(x2 - x1) < 2 or abs(y2 - y1) < 2:
                self.canvas.delete("temp")
                return

            # Salva o estado atual na pilha de desfazer (Ctrl+Z)
            self.push_undo()

            class_id = self.labels_list.index(self.label_var.get())
            self.boxes.append((x1, y1, x2, y2, class_id))
            self.canvas.delete("temp")
            self.refresh_listbox()
            self.drawing = False
            self.redraw_canvas_boxes()

            if self.autosave:
                self.save_current()

        elif self.modo == "edicao":
            self._finish_box_interaction()

    def on_right_press(self, event):
        """Trata o clique do botão direito do mouse."""
        self._clear_hover()
        if self.modo == "criacao":
            # No modo Criação: Botão DIREITO edita/move a bounding box sob o cursor (pan desativado)
            clicked_box, clicked_regiao = self._find_clicked_box(event.x, event.y)
            if clicked_box is not None:
                self._start_box_interaction(event, clicked_box, clicked_regiao)
            else:
                self.selected_box = None
                self.regiao = None
                self.acao = None
                self.drag_start_box = None
                self.box_listbox.selection_clear(0, tk.END)
                self.refresh_listbox()
                self.redraw_canvas_boxes()
            self.pan_start = None

        elif self.modo == "edicao":
            # No modo Edição: Botão DIREITO arrasta toda a imagem (pan)
            self.pan_start = (event.x, event.y)

    def on_right_drag(self, event):
        """Trata o arrasto com o botão direito do mouse."""
        if self.modo == "criacao":
            # No modo Criação: Botão DIREITO move ou redimensiona a BB
            self._update_box_drag(event)

        elif self.modo == "edicao":
            # No modo Edição: move a imagem no canvas (pan)
            if self.pan_start is not None:
                self._clear_hover()
                dx = event.x - self.pan_start[0]
                dy = event.y - self.pan_start[1]
                self.display_offset[0] += dx
                self.display_offset[1] += dy
                self.canvas.coords("fundo", self.display_offset[0], self.display_offset[1])
                self.redraw_canvas_boxes()
                self.pan_start = (event.x, event.y)

    def on_right_release(self, event):
        """Finaliza ações iniciadas com o botão direito."""
        self._clear_hover()
        if self.modo == "criacao":
            self._finish_box_interaction()
        elif self.modo == "edicao":
            self.pan_start = None



    def prev_image(self):
        self._clear_hover()
        if not self.img_files:
            return
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
        self._clear_hover()
        if not self.img_files:
            return
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
        if not self.img_files or not (0 <= self.index < len(self.img_files)) or self.current_image is None:
            return

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
        self._clear_hover()
        #essa função é chamada quando o usuário seleciona uma caixa na listbox da direita

        #obtém a seleção atual (pode ter mais de uma, mas normalmente é uma só)
        sel = self.box_listbox.curselection()
        if not sel:
            #se não houver seleção, não faz nada
            return
        
        #pega o índice da caixa selecionada
        idx = sel[0]
        self.selected_box = idx  #armazena a referência para uso posterior (ex: exclusão)
        self.redraw_canvas_boxes()


    def delete_selected_box(self, event=None):
        """
        Remove a bounding box selecionada. Funciona tanto se a seleção
        vem da listbox quanto se a seleção veio do canvas (self.selected_box).
        Pode ser chamada por tecla Delete (event) ou por botão.
        """
        self._clear_hover()
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

        # Salva para Ctrl+Z
        self.push_undo()

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
        self.redraw_canvas_boxes()
        self.refresh_listbox()

        # limpa seleção na listbox
        self.box_listbox.selection_clear(0, tk.END)

        # salva se necessário
        if self.autosave:
            self.save_current()

    def on_zoom(self, event):
        self._clear_hover()
        min_zoom = 0.2
        max_zoom = 10.0
        old_zoom = self.zoom_factor

        zoom_in = False
        zoom_out = False

        if hasattr(event, 'num') and event.num in (4, 5):
            if event.num == 4:
                zoom_in = True
            elif event.num == 5:
                zoom_out = True
        elif hasattr(event, 'delta') and event.delta != 0:
            if event.delta > 0:
                zoom_in = True
            else:
                zoom_out = True

        if zoom_in:
            self.zoom_factor = min(self.zoom_factor * 1.1, max_zoom)
        elif zoom_out:
            self.zoom_factor = max(self.zoom_factor / 1.1, min_zoom)
        else:
            return

        # Ajusta o offset para manter o ponto do mouse fixo ao dar zoom
        if event is not None and hasattr(event, 'x') and hasattr(event, 'y'):
            # Se o evento veio pelo root, ajusta as coordenadas para o canvas
            if event.widget != self.canvas:
                mx = event.x_root - self.canvas.winfo_rootx()
                my = event.y_root - self.canvas.winfo_rooty()
            else:
                mx, my = event.x, event.y
            scale = self.zoom_factor / old_zoom
            self.display_offset[0] = int(mx - scale * (mx - self.display_offset[0]))
            self.display_offset[1] = int(my - scale * (my - self.display_offset[1]))

        self.draw_image(recenter=False)

    def update_counter(self):
        total = len(self.img_files)
        atual = self.index + 1 if total > 0 else 0
        self.counter_label.config(text=f"{atual}/{total}")

