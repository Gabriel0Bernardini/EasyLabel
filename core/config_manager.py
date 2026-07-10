#config_manager.py
import json
from pathlib import Path

CONFIG_FILE = "config.json"

# Configurações padrão
DEFAULT_CONFIG = {
    "mode": "folder",
    "labels": ["goat"],
    "confidence": 0.4,
    "inference_size": [640, 640],
    "frames_to_extract": 10,
    "model_weights": "",
    "input_folder": "",
    "output_folder": "",
    "complete_output_folder": "",
    "video_path": "",
    "overwrite_output": True
}


def get_config_path():
    """Retorna o caminho do arquivo de configuração"""
    return Path(CONFIG_FILE)


def load_config():
    """Carrega as configurações do arquivo JSON. Se não existir, retorna as padrões"""
    try:
        if get_config_path().exists():
            with open(get_config_path(), "r") as f:
                config = json.load(f)
                return config
    except Exception as e:
        print(f"Erro ao carregar configurações: {e}")
    
    return DEFAULT_CONFIG.copy()


def save_config(labels, confidence, inference_size, frames_to_extract, 
                model_weights="", output_folder="", 
                video_path="", overwrite_output=True, mode="folder"):
    """Salva as configurações no arquivo JSON"""
    try:
        config = {
            "mode": mode,
            "labels": labels,
            "confidence": float(confidence),
            "inference_size": [int(inference_size[0]), int(inference_size[1])],
            "frames_to_extract": int(frames_to_extract),
            "model_weights": model_weights,
            "input_folder": load_config().get("input_folder", ""),  # Manter valor anterior
            "output_folder": output_folder,
            "complete_output_folder": output_folder,
            "video_path": video_path,
            "overwrite_output": bool(overwrite_output)
        }
        
        with open(get_config_path(), "w") as f:
            json.dump(config, f, indent=4)
        
        return True, "Configurações salvas com sucesso!"
    except Exception as e:
        return False, f"Erro ao salvar configurações: {e}"


def validate_config(labels, confidence, inference_size):
    """Valida as configurações antes de salvar"""
    errors = []
    
    # Validar labels
    if not labels or (isinstance(labels, str) and labels.strip() == ""):
        errors.append("Labels não podem estar vazios")
    
    # Validar confiança
    try:
        conf = float(confidence)
        if conf < 0.0 or conf > 1.0:
            errors.append("Confiança deve estar entre 0.0 e 1.0")
    except ValueError:
        errors.append("Confiança deve ser um número decimal")
    
    # Validar tamanho de inferência
    try:
        size = inference_size
        if len(size) != 2:
            errors.append("Tamanho de inferência deve ter 2 valores (largura, altura)")
        
        w, h = int(size[0]), int(size[1])
        if w % 32 != 0 or h % 32 != 0:
            errors.append("Largura e altura devem ser múltiplos de 32")
    except (ValueError, TypeError):
        errors.append("Tamanho de inferência deve conter números inteiros")
    
    return errors

def update_config_fields(**kwargs):
    try:
        config = load_config()

        for chave, valor in kwargs.items():
            if chave in config:
                config[chave] = valor

        with open(get_config_path(), "w") as f:
            json.dump(config, f, indent=4)

        return True, "Configurações atualizadas com sucesso!"
    
    except Exception as e:
        return False, f"Erro: {e}"

def update_mode(new_mode):
    """Atualiza apenas o campo mode no arquivo de configuração"""
    try:
        config = load_config()
        config["mode"] = new_mode
        
        with open(get_config_path(), "w") as f:
            json.dump(config, f, indent=4)
        
        return True
    except Exception as e:
        print(f"Erro ao atualizar mode: {e}")
        return False


def update_input_folder(folder_path):
    """Atualiza apenas o campo input_folder no arquivo de configuração"""
    try:
        config = load_config()
        config["input_folder"] = folder_path
        
        with open(get_config_path(), "w") as f:
            json.dump(config, f, indent=4)
        
        return True
    except Exception as e:
        print(f"Erro ao atualizar input_folder: {e}")
        return False

def create_output_folder():
    config = load_config()
    video_path = config.get("video_path")
    output_dir = config.get("output_folder")

    folder_name = f"Imagens_Rotuladas-{Path(video_path).stem}"
    complete_output_dir = Path(output_dir) / folder_name

    complete_output_dir.mkdir(parents=True, exist_ok=True)
    
    update_config_fields(complete_output_folder = str(complete_output_dir))

    return str(complete_output_dir)

def create_output_folder_images():
    config = load_config()
    input_folder = config.get("input_folder")
    output_dir = config.get("output_folder")

    folder_name = f"Imagens_Rotuladas-{Path(input_folder).name}"
    complete_output_dir = Path(output_dir) / folder_name
    complete_output_dir.mkdir(parents=True, exist_ok=True)

    update_config_fields(complete_output_folder=str(complete_output_dir))
    return str(complete_output_dir)