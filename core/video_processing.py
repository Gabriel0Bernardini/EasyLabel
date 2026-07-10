# video_processing.py
import cv2
from pathlib import Path
from PIL import Image
from core.config_manager import load_config, update_config_fields


def extract_frames_equal():
    """
    Extrai n_frames igualmente espaçados do vídeo, redimensiona para resize_to e salva em out_images_dir.
    """
    
    config = load_config()
    video_path = config["video_path"]
    n_frames = config["frames_to_extract"]
    overwrite = config["overwrite_output"]
    out_images_dir = config["complete_output_folder"] + "/images"
    resize_to = tuple(config["inference_size"])

    video_name = Path(video_path).stem

    #Cria o diretorio out_images_dir (e todos os diretórios pais, se ainda não existirem).
    Path(out_images_dir).mkdir(parents=True, exist_ok=True)

    #abre o video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Não consegui abrir o vídeo: {video_path}")

    #le o numero total de frames do video original
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    def save_resized(frame, out_fp):
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(img)
        pil = pil.resize(resize_to, Image.Resampling.LANCZOS)
        pil.save(out_fp, "JPEG")

    #caso o total seja 0 ou negativo precisamos ler o video frame a frame
    #isso acontece por conta de erros ou certos videos avi nao suportam a contagem de frames através do cv2
    if total <= 0:
        frames = []
        i = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
            i += 1
        total = len(frames)
        # salvar amostras
        idxs = []
        if n_frames >= total:
            idxs = list(range(total))
        else:
            step = total / n_frames
            idxs = [int(i * step) for i in range(n_frames)]
        for k, idx in enumerate(idxs):
            frame = frames[idx]
            out_fp = str(Path(out_images_dir) / f"{video_name}-frame_{k:04d}.jpg")
            save_resized(frame, out_fp)
        return


    if n_frames >= total:
        #se voce pedir para recortar mais frames que o video possuir apenas entregar o total de frames
        selected = list(range(total))
    else:
        #caso contrario cada passo (step) será a razao dos frames que voce pediu com o total
        #ai ele vai selecionar por exemplo de 5 em 5, 10 em 10, etc
        step = total / n_frames
        selected = [int(i * step) for i in range(n_frames)]

    # se overwrite==False e já existirem arquivos, não sobrescrever por padrão
    #loop sobre os frames
    for k, idx in enumerate(selected):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx) #muda a posição do leitor para idx
        ret, frame = cap.read() #le o frame
        if not ret:
            #nao conseguiu ler o frame
            continue
        
        #aqui definimos o nome do arquivo de saida no formato 4 digitos ex frame_0013
        out_fp = str(Path(out_images_dir) / f"{video_name}-frame_{k:04d}.jpg")

        if not overwrite and Path(out_fp).exists():
            #se overwrite for false (nao sobrescrever) e o arquivo ja existir na pasta, pula esse frame
            continue
        
        save_resized(frame, out_fp)

    #fecha o video
    cap.release()
