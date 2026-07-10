# utils.py
from pathlib import Path
from core.video_processing import extract_frames_equal
from core.inference import load_model, run_inference_on_image, save_yolo_label
from core.config_manager import load_config, create_output_folder, create_output_folder_images

def ensure_dataset_dirs(base_dir: str):
    images_dir = Path(base_dir) / "images" #cria o caminho da subpasta images
    labels_dir = Path(base_dir) / "labels" #cria o caminho da subpasta labels
    
    #cria as pastas se não existirem
    Path(images_dir).mkdir(parents=True, exist_ok=True)
    Path(labels_dir).mkdir(parents=True, exist_ok=True)
    return images_dir, labels_dir

def list_images(images_dir: str):
    #abre a pasta images/ e lista os arquivos de imagem
    exts = (".jpg", ".jpeg", ".png")
    images_dir = Path(images_dir) #convertendo o caminho para um arquivo Path
    files = sorted([f.name for f in images_dir.iterdir() if f.suffix.lower() in exts])
    return files

def load_yolo_label(label_fp: str):
    """
    lê um arquivo YOLO e retorna lista de bbox (class_id, xc, yc, w, h)
    """

    label_path = Path(label_fp)    
    boxes = []

    if not label_path.exists():
        #se o arquvio em txt YOLO não existir, retorna uma lista de caixas vazia
        return boxes
    
    with label_path.open("r") as f:
        for line in f:
            #remove espaços em branco no inicio e no fim da string e ignora linhas vazias
            line = line.strip()
            if not line:
                continue
            #divide a linha em partes e extrai os valores
            parts = line.split()
            if len(parts) < 5:
                #se houver menos de 5 partes, ignora a linha pois o formato é inválido
                continue

            #converte os valores para os tipos apropriados e adiciona à lista de caixas
            cid = int(float(parts[0]))
            xc = float(parts[1])
            yc = float(parts[2])
            w = float(parts[3])
            h = float(parts[4])
            boxes.append((cid, xc, yc, w, h))
    return boxes

def yolo_to_pixel(box, img_w, img_h):
    #O objetivo da função é converter as coordenadas de uma bounding box do formato YOLO para o formato de pixels

    #box: tupla (class, xc, yc, w, h) normalizados
    #img_w: largura da imagem em pixels
    #img_h: altura da imagem em pixels
    cid, xc, yc, w, h = box

    #calcula as coordenadas em pixels
    #é feito dessa forma porque a altura e largura são normalizadas (0 a 1) de acordo com o tamanho da imagem
    bw = w * img_w
    bh = h * img_h
    x1 = int((xc * img_w) - bw/2)
    y1 = int((yc * img_h) - bh/2)
    x2 = int((xc * img_w) + bw/2)
    y2 = int((yc * img_h) + bh/2)
    
    #retorna a tupla (class_id, x1, y1, x2, y2)
    return (cid, x1, y1, x2, y2)

def pixel_to_yolo(x1, y1, x2, y2, img_w, img_h, class_id=0):
    #converte coordenadas de pixel para o formato YOLO (class_id, xc, yc, w, h) normalizados
    #para quando um usuario criar uma bounding box manualmente na interface gráfica por exemplo
    
    #largura e altura normalizadas
    w = (x2 - x1) / img_w
    h = (y2 - y1) / img_h

    #centro normalizado
    xc = (x1 + x2) / 2 / img_w
    yc = (y1 + y2) / 2 / img_h
    return (class_id, xc, yc, w, h)


def prepare_from_video():
    config = load_config()

    video_path = config["video_path"]
    out_base = config["output_folder"]
    n_frames = config["frames_to_extract"]
    overwrite = config["overwrite_output"]
    conf = config["confidence"]
    imgsz = config["inference_size"]
    labels = config["labels"]
    model_weights = config["model_weights"]    
    #video_path: caminho para o arquvio do video (passado pelo arquivo config.py)
    #out_base: diretório base onde serão criadas as pastas images/ e labels/ (passado pelo arquivo config.py)
    #n_frames: quantas imagens deseja extrair do vídeo (passado pelo arquivo config.py)
    #overwrite: se true sobrescreve a pasta destino (passado pelo arquivo config.py)
    #conf: limiar de confiança para a inferência (passado pelo arquivo config.py)

    complete_output_dir = create_output_folder() #cria uma pasta de saída única para evitar sobrescrever resultados anteriores, retorna o caminho da pasta criada
    #update_config_fields(output_folder = str(complete_output_dir))

    #Cria as pastas images/ e labels/ atraves da função ensure_dataset_dirs
    images_dir, labels_dir = ensure_dataset_dirs(complete_output_dir)

    #gera o arquivo data.yaml com as classes do dataset
    gerar_data_yaml(labels, complete_output_dir)

    #extrai os frames do vídeo e salva na pasta images/
    extract_frames_equal() #não precisa de parametros pois tudo é tratado dentro da função através do config.json

    #carregar modelo e inferir em cada imagem gerada
    model = load_model()

    #Lista todos os arquivos(imagens) na pasta images/
    files = sorted(Path(images_dir).iterdir())
    for f in files:
        if f.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            #Se o arquivo não for uma imagem, ignora
            continue
        
        #fp é o caminho completo da imagem da iteração atual
        fp = Path(images_dir) / f

        #rodar inferência na imagem
        boxes = run_inference_on_image(model, fp, conf=conf, imgsz=imgsz[0])
        # boxes são (class, xc, yc, w, h, conf) ou (class, xc, yc, w, h)

        #prepara uma lista de caixas para salvar no formato YOLO, os 5 primeiros elementos esperados
        boxes_to_save = []
        for b in boxes:
            if len(b) >= 5:
                boxes_to_save.append((int(b[0]), b[1], b[2], b[3], b[4]))

        #salva o arquivo de label da imagem na pasta labels/
        label_fp = Path(labels_dir) / (f.stem + ".txt")
        save_yolo_label(label_fp, boxes_to_save)
    return images_dir, labels_dir

def prepare_from_folder():
    #Função para preparar o dataset a partir de uma pasta já existente de images/ e labels/

    config = load_config()
    folder_base = config["input_folder"]

    images_dir = Path(folder_base) / "images"
    labels_dir = Path(folder_base) / "labels"
    if not images_dir.exists() or not labels_dir.exists():
        raise RuntimeError("Pasta deve conter images/ e labels/")
    return images_dir, labels_dir

def prepare_from_images():
    config = load_config()
    input_folder = config["input_folder"]
    out_base = config["output_folder"]
    conf = config["confidence"]
    imgsz = config["inference_size"]
    overwrite = config["overwrite_output"]
    model_weights = config["model_weights"]
    
    """
    Aplica o modelo YOLO em todas as imagens de input_folder e salva resultados em out_base/images e out_base/labels.
    """
    images_dir, labels_dir = ensure_dataset_dirs(create_output_folder_images())
    # Copia imagens para images_dir (se overwrite ou se images_dir vazio)
    input_folder = Path(input_folder)
    if overwrite or not any(images_dir.iterdir()):
        for img in input_folder.iterdir():
            if img.suffix.lower() in (".jpg", ".jpeg", ".png"):
                dest = images_dir / img.name
                if not dest.exists() or overwrite:
                    dest.write_bytes(img.read_bytes())
    # Carrega modelo
    model = load_model()
    files = sorted(images_dir.iterdir())
    for f in files:
        if f.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        fp = images_dir / f.name
        boxes = run_inference_on_image(model, fp, conf=conf, imgsz=imgsz[0])
        boxes_to_save = []
        for b in boxes:
            if len(b) >= 5:
                boxes_to_save.append((int(b[0]), b[1], b[2], b[3], b[4]))
        label_fp = labels_dir / (f.stem + ".txt")
        save_yolo_label(label_fp, boxes_to_save)
    return images_dir, labels_dir


import os

def gerar_data_yaml(lista_names, caminho_dataset, nome_arquivo="data.yaml"):
    numero_classes = len(lista_names)
    
    
    #caminho_train = os.path.join(caminho_dataset, "images/train")
    #caminho_val = os.path.join(caminho_dataset, "images/val")
    #caminho_test = os.path.join(caminho_dataset, "images/test")
    
    # conteúdo do YAML
    conteudo = f"""# Caminhos do dataset
train: -
val: -
test: -

# Número de classes
nc: {numero_classes}

# Nomes das classes
names: {lista_names}

"""
    
    caminho_yaml = os.path.join(caminho_dataset, nome_arquivo)
    
    with open(caminho_yaml, "w", encoding="utf-8") as f:
        f.write(conteudo)
    
    print(f"data.yaml criado em: {caminho_yaml}")