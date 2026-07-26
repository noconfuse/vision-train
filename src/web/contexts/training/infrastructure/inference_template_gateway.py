"""部署模板生成器：纯目录生成层。

模型与模板解耦后，模板生成只关心：
- 一个具体的源模型路径（pt / onnx / openvino / engine）
- 一组模板规格（fastapi_service / python_sdk / batch_processor）
- 训练任务的展示元数据（dataset_id / dataset_version_id / vision_task_type）

生成结果是一个独立的部署模板目录树，可被下游任务消费与下载。
"""

from __future__ import annotations

import os
import shutil

from contexts.dataset.infrastructure.dataset_schema import (
    load_dataset_yaml_ref,
    resolve_dataset_names_list,
)
from contexts.task.domain.task_artifact_keys import ARTIFACT_DATASET_YAML

TEMPLATE_SOURCE_FORMATS = ("pt", "onnx", "openvino", "engine")

TEMPLATE_SOURCE_EXTENSIONS = {
    "pt": (".pt", ".pth"),
    "onnx": (".onnx",),
    "openvino": (".xml",),
    "engine": (".engine",),
}

RUNTIME_DEPENDENCIES = {
    "pt": ["ultralytics>=8.2.0"],
    "onnx": ["onnxruntime>=1.18.0"],
    "openvino": ["openvino>=2024.0.0"],
    "engine": [],
}

INFERENCE_TEMPLATE_SPECS = (
    {
        "template_type": "fastapi_service",
        "label": "FastAPI 服务",
        "description": "容器化 HTTP 推理服务，适合在线 API 部署。",
        "runtime_mode": "http_service",
        "entrypoint": "app.main:app",
        "model_subdir": "app",
    },
    {
        "template_type": "python_sdk",
        "label": "Python SDK",
        "description": "嵌入现有 Python 服务或业务代码，直接调用预测器。",
        "runtime_mode": "python_sdk",
        "entrypoint": "sdk.predictor:Predictor",
        "model_subdir": "sdk",
    },
    {
        "template_type": "batch_processor",
        "label": "批处理任务",
        "description": "离线批量推理任务模板，适合定时任务与数据回刷。",
        "runtime_mode": "batch_job",
        "entrypoint": "runner.main:main",
        "model_subdir": "runner",
    },
)
_INFERENCE_TEMPLATE_SPEC_MAP = {item["template_type"]: item for item in INFERENCE_TEMPLATE_SPECS}

DEPLOYMENT_TEMPLATE_SUBDIRNAME = "templates"
DEPLOYMENT_MANIFEST_FILENAME = "manifest.json"


def list_inference_template_specs():
    """返回当前支持的部署模板规格。"""
    return [dict(item) for item in INFERENCE_TEMPLATE_SPECS]


def get_inference_template_spec(template_type):
    """读取单个模板规格。"""
    return dict(_INFERENCE_TEMPLATE_SPEC_MAP.get(str(template_type or "").strip().lower(), {}))


def normalize_inference_template_type(template_type):
    """校验并标准化部署模板类型。"""
    normalized = str(template_type or "").strip().lower()
    if normalized not in _INFERENCE_TEMPLATE_SPEC_MAP:
        raise ValueError("不支持的部署模板类型")
    return normalized


def normalize_template_source_format(source_format):
    """校验并标准化源模型格式。"""
    normalized = str(source_format or "").strip().lower()
    if normalized not in TEMPLATE_SOURCE_FORMATS:
        raise ValueError("不支持的源模型格式")
    return normalized


def resolve_template_source_path(source_dir, source_format):
    """在源目录中按格式挑选主模型文件。"""
    extensions = TEMPLATE_SOURCE_EXTENSIONS.get(source_format, ())
    candidates = []
    if os.path.isfile(source_dir):
        candidates.append(source_dir)
        scan_root = os.path.dirname(source_dir)
    else:
        scan_root = source_dir
    if os.path.isdir(scan_root):
        for root, _, files in os.walk(scan_root):
            for name in files:
                candidates.append(os.path.join(root, name))
    for path in candidates:
        if path.lower().endswith(extensions):
            return path
    return ""


def generate_inference_template_bundle(
    *,
    template_type,
    source_model_path,
    source_format,
    vision_task_type,
    dataset_yaml_path=None,
    training_task_id="",
    target_dir,
    imgsz=640,
    half=False,
    int8=False,
):
    """生成单套生产级部署模板目录。

    入口只关心源模型 + 模板规格，不再依赖 export_task。
    """
    spec = get_inference_template_spec(template_type)
    if not spec:
        raise ValueError("不支持的部署模板类型")
    normalized_format = normalize_template_source_format(source_format)
    if not source_model_path or not os.path.isfile(source_model_path):
        raise ValueError("源模型路径无效")
    target_dir = os.path.realpath(target_dir)
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)
    os.makedirs(target_dir, exist_ok=True)

    dataset_config = load_dataset_yaml_ref(dataset_yaml_path, default={})
    model_relative_path = _copy_primary_model(source_model_path, target_dir)
    model_info = _build_model_info(
        vision_task_type=vision_task_type,
        source_format=normalized_format,
        imgsz=imgsz,
        half=half,
        int8=int8,
        dataset_config=dataset_config,
        training_task_id=training_task_id,
        primary_model_relative_path=model_relative_path,
    )
    _write_template_files(target_dir, spec, model_info)
    manifest_path = os.path.join(target_dir, DEPLOYMENT_MANIFEST_FILENAME)
    manifest = _build_template_manifest(spec, model_info)
    _write_json(manifest_path, manifest)
    return {
        "template_type": spec["template_type"],
        "label": spec["label"],
        "description": spec["description"],
        "runtime_mode": spec["runtime_mode"],
        "entrypoint": spec["entrypoint"],
        "template_dir": target_dir,
        "manifest_path": manifest_path,
        "source_format": normalized_format,
        "source_model_path": source_model_path,
        "model_relative_path": model_relative_path,
    }


def _copy_primary_model(source_model_path, template_dir):
    model_dir = os.path.join(template_dir, "model")
    os.makedirs(model_dir, exist_ok=True)
    target_path = os.path.join(model_dir, os.path.basename(source_model_path))
    shutil.copy2(source_model_path, target_path)
    return os.path.relpath(target_path, template_dir).replace(os.sep, "/")


def _build_model_info(
    *,
    vision_task_type,
    source_format,
    imgsz,
    half,
    int8,
    dataset_config,
    training_task_id,
    primary_model_relative_path,
):
    names = resolve_dataset_names_list((dataset_config or {}).get("names"))
    info = {
        "service_name": "vision-train-inference-service",
        "vision_task_type": vision_task_type,
        "source_format": source_format,
        "imgsz": int(imgsz or 640),
        "half": bool(half),
        "int8": bool(int8),
        "class_names": list(names),
        "source_training_task_id": training_task_id,
        "model_relative_path": primary_model_relative_path,
    }
    if vision_task_type == "pose":
        info["kpt_shape"] = list((dataset_config or {}).get("kpt_shape") or [])
        info["kpt_names"] = _normalize_pose_kpt_names((dataset_config or {}).get("kpt_names"))
        info["skeleton"] = list((dataset_config or {}).get("skeleton") or [])
    return info


def _normalize_pose_kpt_names(raw_value):
    if isinstance(raw_value, dict):
        result = {}
        for key, value in raw_value.items():
            try:
                result[str(int(key))] = [str(item) for item in value or []]
            except (TypeError, ValueError):
                result[str(key)] = [str(item) for item in value or []]
        return result
    if isinstance(raw_value, list):
        return {"0": [str(item) for item in raw_value]}
    return {}


def _write_template_files(template_dir, spec, model_info):
    os.makedirs(os.path.join(template_dir, "config"), exist_ok=True)
    _write_json(os.path.join(template_dir, "config", "model_info.json"), model_info)
    _write_text(os.path.join(template_dir, "requirements.txt"), _render_requirements(spec["template_type"], model_info))
    _write_text(os.path.join(template_dir, ".dockerignore"), _render_dockerignore())
    template_type = spec["template_type"]
    if template_type == "fastapi_service":
        _write_fastapi_service_template_files(template_dir, model_info, spec)
    elif template_type == "python_sdk":
        _write_python_sdk_template_files(template_dir, model_info, spec)
    elif template_type == "batch_processor":
        _write_batch_processor_template_files(template_dir, model_info, spec)
    else:
        raise ValueError("不支持的部署模板类型")


def _build_template_manifest(spec, model_info):
    return {
        "template_type": spec["template_type"],
        "template_label": spec["label"],
        "template_description": spec["description"],
        "runtime_mode": spec["runtime_mode"],
        "vision_task_type": model_info["vision_task_type"],
        "source_format": model_info["source_format"],
        "entrypoint": spec["entrypoint"],
        "model_relative_path": model_info["model_relative_path"],
    }


def _write_fastapi_service_template_files(template_dir, model_info, spec):
    _write_text(os.path.join(template_dir, "README.md"), _render_fastapi_readme(model_info, spec))
    _write_text(os.path.join(template_dir, "Dockerfile"), _render_service_dockerfile(model_info, spec["entrypoint"]))
    _write_text(os.path.join(template_dir, "curl_examples.sh"), _render_curl_examples())
    _write_text(os.path.join(template_dir, "scripts", "infer_folder.py"), _render_infer_folder_script("app.predictor"))
    _write_text(os.path.join(template_dir, "scripts", "smoke_test.py"), _render_http_smoke_test_script())
    _write_text(os.path.join(template_dir, "app", "__init__.py"), "")
    _write_text(os.path.join(template_dir, "app", "main.py"), _render_fastapi_main_py())
    _write_text(os.path.join(template_dir, "app", "predictor.py"), _render_predictor_py(model_info))


def _write_python_sdk_template_files(template_dir, model_info, spec):
    _write_text(os.path.join(template_dir, "README.md"), _render_python_sdk_readme(model_info, spec))
    _write_text(os.path.join(template_dir, "Dockerfile"), _render_sdk_dockerfile())
    _write_text(os.path.join(template_dir, "sdk", "__init__.py"), _render_sdk_init_py())
    _write_text(os.path.join(template_dir, "sdk", "predictor.py"), _render_predictor_py(model_info))
    _write_text(os.path.join(template_dir, "examples", "predict.py"), _render_sdk_predict_script())
    _write_text(os.path.join(template_dir, "examples", "predict_folder.py"), _render_sdk_predict_folder_script())


def _write_batch_processor_template_files(template_dir, model_info, spec):
    _write_text(os.path.join(template_dir, "README.md"), _render_batch_processor_readme(model_info, spec))
    _write_text(os.path.join(template_dir, "Dockerfile"), _render_batch_dockerfile())
    _write_text(os.path.join(template_dir, "runner", "__init__.py"), "from .predictor import Predictor\n\n__all__ = [\"Predictor\"]\n")
    _write_text(os.path.join(template_dir, "runner", "predictor.py"), _render_predictor_py(model_info))
    _write_text(os.path.join(template_dir, "runner", "main.py"), _render_batch_main_script())


def _render_requirements(template_type, model_info):
    lines = list(_TEMPLATE_SHARED_DEPENDENCIES)
    for package in _TEMPLATE_EXTRA_DEPENDENCIES.get(template_type, []):
        if package not in lines:
            lines.append(package)
    for package in RUNTIME_DEPENDENCIES.get(model_info["source_format"], []):
        if package not in lines:
            lines.append(package)
    return "\n".join(lines) + "\n"


def _render_service_dockerfile(model_info, entrypoint):
    base_image = "python:3.11-slim"
    if model_info["source_format"] == "engine":
        base_image = "nvcr.io/nvidia/tensorrt:24.06-py3"
    return f"""FROM {base_image}

ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "2", "-b", "0.0.0.0:8000", "{entrypoint}", "--timeout", "120"]
"""


def _render_sdk_dockerfile():
    return """FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "examples/predict_folder.py", "/workspace/input", "/workspace/output/predictions.json"]
"""


def _render_batch_dockerfile():
    return """FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "-m", "runner.main", "--input", "/workspace/input", "--output", "/workspace/output/predictions.json"]
"""


def _render_dockerignore():
    return """__pycache__/
*.pyc
*.pyo
*.pyd
.pytest_cache/
.DS_Store
"""


_TEMPLATE_SHARED_DEPENDENCIES = [
    "numpy>=1.26.0",
    "opencv-python>=4.9.0",
    "Pillow>=10.2.0",
    "PyYAML>=6.0.1",
]

_TEMPLATE_EXTRA_DEPENDENCIES = {
    "fastapi_service": [
        "fastapi>=0.115.0",
        "gunicorn>=22.0.0",
        "python-multipart>=0.0.9",
        "requests>=2.32.0",
        "uvicorn[standard]>=0.30.0",
    ],
    "python_sdk": [],
    "batch_processor": [],
}


def _render_fastapi_main_py():
    return """from __future__ import annotations

import io

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from .predictor import Predictor

app = FastAPI(title="VisionTrain Inference Service", version="1.0.0")
predictor = Predictor()


@app.get("/healthz")
def healthz():
    return predictor.healthz()


@app.get("/metadata")
def metadata():
    return predictor.metadata()


@app.post("/predict")
async def predict(
    files: list[UploadFile] = File(...),
    conf: float = Form(0.25),
    iou: float = Form(0.7),
    imgsz: int = Form(0),
    max_det: int = Form(200),
):
    if not files:
        raise HTTPException(status_code=400, detail="缺少推理图片")
    images = []
    names = []
    for upload in files:
        try:
            image = Image.open(io.BytesIO(upload.file.read())).convert("RGB")
        except UnidentifiedImageError as exc:
            raise HTTPException(status_code=400, detail=f"无法解析图片: {upload.filename}") from exc
        images.append(image)
        names.append(upload.filename or "image.jpg")
    try:
        return predictor.predict(images=images, names=names, conf=conf, iou=iou, imgsz=imgsz, max_det=max_det)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
"""


def _render_predictor_py(model_info):
    task_type = model_info["vision_task_type"]
    pose_block = ""
    if task_type == "pose":
        pose_block = """
    def _serialize_pose(self, result):
        return {
            "keypoints": [
                {
                    "x": float(kp[0]),
                    "y": float(kp[1]),
                    "confidence": float(kp[2]) if len(kp) > 2 else 0.0,
                }
                for kp in (result.keypoints.xyn if hasattr(result, "keypoints") else []).reshape(-1, 3).tolist()
            ] if hasattr(result, "keypoints") else [],
        }
"""
    return f"""from __future__ import annotations

import os
from pathlib import Path

from ultralytics import YOLO

ROOT_DIR = Path(__file__).resolve().parent.parent
MODEL_RELATIVE_PATH = {model_info["model_relative_path"]!r}
VISION_TASK_TYPE = {model_info["vision_task_type"]!r}
SOURCE_FORMAT = {model_info["source_format"]!r}
DEFAULT_IMGSZ = {int(model_info.get("imgsz") or 640)}
HALF = {bool(model_info.get("half"))}
INT8 = {bool(model_info.get("int8"))}
CLASS_NAMES = {model_info.get("class_names") or []!r}


class Predictor:
    def __init__(self):
        model_path = ROOT_DIR / MODEL_RELATIVE_PATH
        if not model_path.is_file():
            raise FileNotFoundError(f"模型文件不存在: {{model_path}}")
        self.model = YOLO(str(model_path))

    def healthz(self):
        return {{"status": "ok", "vision_task_type": VISION_TASK_TYPE, "source_format": SOURCE_FORMAT}}

    def metadata(self):
        return {{
            "vision_task_type": VISION_TASK_TYPE,
            "source_format": SOURCE_FORMAT,
            "imgsz": DEFAULT_IMGSZ,
            "half": HALF,
            "int8": INT8,
            "class_names": CLASS_NAMES,
        }}

    def predict(self, images, names=None, conf=0.25, iou=0.7, imgsz=0, max_det=200):
        if not images:
            raise ValueError("缺少推理图片")
        target_imgsz = int(imgsz) if imgsz else DEFAULT_IMGSZ
        outputs = []
        for index, image in enumerate(images):
            name = (names or [])[index] if names and index < len(names) else f"image-{{index}}.jpg"
            result = self.model.predict(
                source=image,
                conf=conf,
                iou=iou,
                imgsz=target_imgsz,
                max_det=max_det,
                verbose=False,
            )[0]
            outputs.append(self._serialize_result(name, result))
        return {{"items": outputs}}

    def _serialize_result(self, image_name, result):
        if VISION_TASK_TYPE == "classify":
            return self._serialize_classify(image_name, result)
        if VISION_TASK_TYPE == "segment":
            return self._serialize_segment(image_name, result)
        if VISION_TASK_TYPE == "pose":
            return self._serialize_pose(image_name, result)
        return self._serialize_detect(image_name, result)

    def _serialize_detect(self, image_name, result):
        boxes = result.boxes
        instances = []
        if boxes is not None:
            xyxy = boxes.xyxy.cpu().numpy().tolist()
            confs = boxes.conf.cpu().numpy().tolist()
            cls = boxes.cls.cpu().numpy().tolist()
            for bbox, score, class_id in zip(xyxy, confs, cls):
                instances.append(
                    {{
                        "class_id": int(class_id),
                        "class_name": result.names.get(int(class_id), str(int(class_id))),
                        "confidence": float(score),
                        "xyxy": [float(value) for value in bbox],
                    }}
                )
        return {{"image_name": image_name, "task_type": "detect", "instances": instances}}

    def _serialize_segment(self, image_name, result):
        return {{**self._serialize_detect(image_name, result), "task_type": "segment"}}

    def _serialize_classify(self, image_name, result):
        probs = getattr(result, "probs", None)
        top1 = int(getattr(probs, "top1", 0)) if probs is not None else 0
        score = float(getattr(probs, "top1conf", 0.0)) if probs is not None else 0.0
        return {{
            "image_name": image_name,
            "task_type": "classify",
            "top1": {{"class_id": top1, "class_name": result.names.get(top1, str(top1)), "confidence": score}},
        }}{pose_block}
"""


def _render_sdk_init_py():
    return """from .predictor import Predictor

__all__ = ["Predictor"]
"""


def _render_sdk_predict_script():
    return """from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdk import Predictor  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Single image prediction using the SDK predictor")
    parser.add_argument("image", help="Path to the input image")
    parser.add_argument("output", help="Path to the output JSON file")
    args = parser.parse_args()

    predictor = Predictor()
    from PIL import Image  # noqa: WPS433

    with Image.open(args.image) as image:
        payload = predictor.predict(images=[image.convert("RGB")], names=[args.image])
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
"""


def _render_sdk_predict_folder_script():
    return """from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sdk import Predictor  # noqa: E402

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def main():
    parser = argparse.ArgumentParser(description="Batch image prediction using the SDK predictor")
    parser.add_argument("--input", required=True, help="Directory of images to process")
    parser.add_argument("--output", required=True, help="Output JSON file")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=0)
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.is_dir():
        raise SystemExit(f"输入目录不存在: {input_dir}")
    predictor = Predictor()
    from PIL import Image  # noqa: WPS433

    images = []
    names = []
    for path in sorted(input_dir.iterdir()):
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        with Image.open(path) as image:
            images.append(image.convert("RGB"))
        names.append(path.name)
    payload = predictor.predict(images=images, names=names, conf=args.conf, imgsz=args.imgsz)
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
"""


def _render_batch_main_script():
    return """from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runner import Predictor  # noqa: E402

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def main():
    parser = argparse.ArgumentParser(description="Batch image prediction runner")
    parser.add_argument("--input", required=True, help="Directory of images to process")
    parser.add_argument("--output", required=True, help="Output JSON file")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=0)
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.is_dir():
        raise SystemExit(f"输入目录不存在: {input_dir}")
    from PIL import Image  # noqa: WPS433

    images = []
    names = []
    for path in sorted(input_dir.iterdir()):
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        with Image.open(path) as image:
            images.append(image.convert("RGB"))
        names.append(path.name)
    predictor = Predictor()
    payload = predictor.predict(images=images, names=names, conf=args.conf, imgsz=args.imgsz)
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
"""


def _render_infer_folder_script(module):
    return f"""from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from {module} import Predictor  # noqa: E402

IMAGE_EXTENSIONS = {{".jpg", ".jpeg", ".png", ".bmp", ".webp"}}


def main():
    parser = argparse.ArgumentParser(description="Run a folder of images through the FastAPI predictor")
    parser.add_argument("--input", required=True, help="Directory of images")
    parser.add_argument("--output", required=True, help="Output JSON file")
    args = parser.parse_args()

    from PIL import Image  # noqa: WPS433

    images = []
    names = []
    for path in sorted(Path(args.input).iterdir()):
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        with Image.open(path) as image:
            images.append(image.convert("RGB"))
        names.append(path.name)
    payload = Predictor().predict(images=images, names=names)
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
"""


def _render_http_smoke_test_script():
    return """from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import requests
from PIL import Image


def main():
    parser = argparse.ArgumentParser(description="Smoke test against the running inference service")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Service base URL")
    parser.add_argument("--image", required=True, help="Image path")
    args = parser.parse_args()

    health = requests.get(f"{args.url}/healthz", timeout=10)
    health.raise_for_status()
    metadata = requests.get(f"{args.url}/metadata", timeout=10)
    metadata.raise_for_status()
    with Image.open(args.image) as raw:
        image = raw.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    response = requests.post(
        f"{args.url}/predict",
        files={"files": (Path(args.image).name, buffer.getvalue(), "image/jpeg")},
        data={"conf": "0.25", "iou": "0.7"},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    Path("/tmp/inference_smoke_result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
"""


def _render_curl_examples():
    return """#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
IMAGE_PATH="${IMAGE_PATH:-./sample.jpg}"

curl -fsS "${BASE_URL}/healthz"
echo
curl -fsS "${BASE_URL}/metadata"
echo
curl -fsS -X POST "${BASE_URL}/predict" \\
    -F "files=@${IMAGE_PATH};type=image/jpeg" \\
    -F "conf=0.25" \\
    -F "iou=0.7"
"""


def _render_fastapi_readme(model_info, spec):
    return f"""# {spec['label']}

模型来源：训练任务 `{model_info['source_training_task_id'] or '-'}`
任务类型：`{model_info['vision_task_type']}`
模型格式：`{model_info['source_format']}`

## 启动

```bash
pip install -r requirements.txt
gunicorn -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8000 {spec['entrypoint']}
```

或使用 Docker：

```bash
docker build -t vision-train-service .
docker run --rm -p 8000:8000 vision-train-service
```

## 推理

```bash
curl -X POST http://127.0.0.1:8000/predict \\
    -F "files=@sample.jpg;type=image/jpeg" \\
    -F "conf=0.25" -F "iou=0.7"
```
"""


def _render_python_sdk_readme(model_info, spec):
    return f"""# {spec['label']}

任务类型：`{model_info['vision_task_type']}`
模型格式：`{model_info['source_format']}`

## 单图推理

```bash
python examples/predict.py sample.jpg predictions.json
```

## 目录批推理

```bash
python examples/predict_folder.py --input ./images --output predictions.json
```
"""


def _render_batch_processor_readme(model_info, spec):
    return f"""# {spec['label']}

任务类型：`{model_info['vision_task_type']}`
模型格式：`{model_info['source_format']}`

```bash
python -m runner.main --input ./images --output predictions.json
```
"""


def _write_text(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def _write_json(path, payload):
    import json

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)