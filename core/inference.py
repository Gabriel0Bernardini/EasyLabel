# inference.py
import os
from pathlib import Path
import ultralytics as ut
from core.config_manager import load_config

def load_model():
    """
    Carrega o modelo ultralytics YOLO.
    """
    config = load_config()
    model_weights = config["model_weights"]
    model = ut.YOLO(model_weights)
    return model

def run_inference_on_image(model, image_path: str, conf: float = 0.5, imgsz: int = 640):
    """
    Executa inferência na imagem e retorna bounding boxes no formato YOLO:
    list of tuples: (class_id, x_c_norm, y_c_norm, w_norm, h_norm, confidence)
    """

    # model.predict retorna uma lista de results
    results = model.predict(source=image_path, conf=conf, imgsz=imgsz, verbose=False)

    #lista onde serao guardadas as bounding boxes geradas pelos results
    all_boxes = []

    # iteramos por cada resutlado (provavelmente terá só um ja que aplicamos o modelo a uma imagem so)
    for r in results:
        # r.boxes pode ter .xyxy, .xywhn, .cls, .conf dependendo da versão
        boxes = []
        
        # preferência por xyxy e cls/conf
        xyxy = r.boxes.xyxy.cpu().numpy()
        cls = r.boxes.cls.cpu().numpy()
        confs = r.boxes.conf.cpu().numpy()
        # converter para xywh normalizado
        h, w = r.orig_shape[0], r.orig_shape[1]
        #loop sobre todas as boxes detectadas e converte suas informacoes para largura, altura e centro (formato de label do yolo)
        for (x1, y1, x2, y2), c, confv in zip(xyxy, cls, confs):
            bw = (x2 - x1) / w
            bh = (y2 - y1) / h
            xc = (x1 + x2) / 2 / w
            yc = (y1 + y2) / 2 / h
            boxes.append( (int(c), float(xc), float(yc), float(bw), float(bh), float(confv)) )
    
        all_boxes.extend(boxes)
    return all_boxes

def save_yolo_label(label_path: str, boxes):
    """
    boxes: list of tuples (class_id, xc, yc, w, h, conf?) -> salva no formato YOLO (sem confid)
    """
    caminho = os.path.dirname(label_path)
    if caminho and not os.path.exists(caminho):
        os.makedirs(caminho, exist_ok=True)
    with open(label_path, "w") as f:
        if boxes:
            for b in boxes:
                class_id, xc, yc, w, h = b[0], b[1], b[2], b[3], b[4]
                f.write(f"{class_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")
        else:
            f.write("")
