#!/usr/bin/env python3
import os
import uuid
import json
import shutil
import time
from pathlib import Path
from typing import Dict, List, Any

from flask import Flask, render_template, request, jsonify, send_from_directory

PROJECT_ROOT = Path(__file__).parent.parent.parent
TEMPLATE_DIR = Path(__file__).parent / "templates"
PRETRAINED_MODELS_DIR = PROJECT_ROOT / "pretrained_models"
TMP_DIR = PROJECT_ROOT / "tmp" / "inference_tool"

app = Flask(__name__, template_folder=str(TEMPLATE_DIR))
app.secret_key = "inference_tool_secret_key"

sessions: Dict[str, Dict[str, Any]] = {}


def _ensure_dirs(*dirs: Path):
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def _read_models_config() -> Dict[str, Dict[str, Any]]:
    config_path = PRETRAINED_MODELS_DIR / "config.yaml"
    if not config_path.exists():
        return {}
    import yaml
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    items: Dict[str, Dict[str, Any]] = {}
    confs = cfg.get("pretrained_models") or {}
    if isinstance(confs, dict):
        for key, item in confs.items():
            name = item.get("name") or key
            path = item.get("path")
            description = item.get("description", "预训练模型")
            size = item.get("size")
            if path and not os.path.isabs(path):
                path = str((PROJECT_ROOT / path).resolve())
            if path:
                items[str(key)] = {
                    "id": str(key),
                    "name": name,
                    "path": path,
                    "description": description,
                    "size": size,
                }
    return items


def _ensure_local_model(model_item: Dict[str, Any]) -> str:
    path = model_item.get("path")
    if not path:
        raise FileNotFoundError("模型未配置有效路径")
    p = Path(path)
    if p.exists():
        return str(p)
    filename = p.name
    try:
        from ultralytics import YOLO
        YOLO(filename)
    except Exception:
        pass
    candidate_dirs = [
        Path.home() / ".cache" / "ultralytics" / "weights",
        Path.home() / ".cache" / "Ultralytics" / "weights",
        Path.home() / ".cache" / "ultralytics",
        Path.home() / ".cache" / "Ultralytics",
    ]
    for d in candidate_dirs:
        src = d / filename
        if src.exists():
            _ensure_dirs(p.parent)
            shutil.copy2(str(src), str(p))
            return str(p)
    for d in candidate_dirs:
        if d.exists():
            for root, _, files in os.walk(str(d)):
                if filename in files:
                    src = Path(root) / filename
                    _ensure_dirs(p.parent)
                    shutil.copy2(str(src), str(p))
                    return str(p)
    local_candidates = [PROJECT_ROOT / filename, Path.cwd() / filename]
    for src in local_candidates:
        if src.exists():
            _ensure_dirs(p.parent)
            shutil.copy2(str(src), str(p))
            return str(p)
    raise FileNotFoundError(f"无法获取模型文件: {p}")


def _load_yolo(model_path: str):
    from ultralytics import YOLO
    return YOLO(model_path)


@app.route("/")
def index():
    models = _read_models_config()
    return render_template("inference_tool.html", models=models)


@app.route("/api/models")
def api_models():
    models = _read_models_config()
    return jsonify({"success": True, "models": models})


@app.route("/api/models/<model_id>/classes")
def api_model_classes(model_id: str):
    models = _read_models_config()
    m = models.get(model_id)
    if not m:
        return jsonify({"success": False, "error": "模型不存在"}), 404
    try:
        ensured = _ensure_local_model(m)
        yolo = _load_yolo(ensured)
        names = yolo.names if hasattr(yolo, "names") else {}
        classes = [{"id": int(k), "name": str(v)} for k, v in names.items()]
        return jsonify({"success": True, "classes": classes})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/upload", methods=["POST"])
def api_upload():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"success": False, "error": "未选择文件"}), 400
    session_id = request.form.get("session_id") or uuid.uuid4().hex
    base_dir = TMP_DIR / session_id
    uploads_dir = base_dir / "uploads"
    outputs_dir = base_dir / "outputs"
    _ensure_dirs(base_dir, uploads_dir, outputs_dir)

    saved: List[Dict[str, Any]] = []
    for f in files:
        fn = f.filename or f.name or f"img_{uuid.uuid4().hex}.jpg"
        name = os.path.basename(fn)
        dst = uploads_dir / name
        f.save(str(dst))
        saved.append({
            "name": name,
            "url": f"/uploads/{session_id}/{name}",
            "path": str(dst),
        })
    
    # Ensure session exists
    if session_id not in sessions:
        sessions[session_id] = {}
        
    current_uploads = sessions[session_id].get("uploads", [])
    current_uploads.extend(saved)
    sessions[session_id].update({
        "created_at": time.time(),
        "uploads": current_uploads,
        "outputs_dir": str(outputs_dir),
        "uploads_dir": str(uploads_dir),
        "results": [],
        "model_id": None,
    })
    return jsonify({"success": True, "session_id": session_id, "files": current_uploads})


@app.route("/api/infer", methods=["POST"])
def api_infer():
    data = request.get_json(force=True) or {}
    session_id = data.get("session_id")
    model_id = data.get("model_id")
    conf = float(data.get("conf", 0.25))
    if not session_id or not model_id:
        return jsonify({"success": False, "error": "缺少参数"}), 400
    sess = sessions.get(session_id)
    if not sess:
        return jsonify({"success": False, "error": "会话不存在"}), 404
    models = _read_models_config()
    m = models.get(model_id)
    if not m:
        return jsonify({"success": False, "error": "模型不存在"}), 404
    try:
        ensured = _ensure_local_model(m)
        yolo = _load_yolo(ensured)
    except Exception as e:
        return jsonify({"success": False, "error": f"加载模型失败: {e}"}), 500

    results_all: List[Dict[str, Any]] = []
    for item in sess.get("uploads", []):
        img_path = item["path"]
        try:
            res = yolo(img_path, verbose=False, conf=conf)
            per_image = []
            for r in res:
                if hasattr(r, "boxes") and r.boxes is not None:
                    boxes = r.boxes
                    for i in range(len(boxes)):
                        cls_id = int(boxes.cls[i].item())
                        conf_v = float(boxes.conf[i].item())
                        x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                        per_image.append({
                            "class_id": cls_id,
                            "confidence": conf_v,
                            "bbox_xyxy": [x1, y1, x2, y2],
                        })
            results_all.append({
                "name": item["name"],
                "image_url": item["url"],
                "predictions": per_image,
            })
        except Exception as e:
            results_all.append({
                "name": item["name"],
                "image_url": item["url"],
                "predictions": [],
                "error": str(e),
            })
    sess["results"] = results_all
    sess["model_id"] = model_id
    return jsonify({"success": True, "results": results_all})


@app.route("/api/results")
def api_results():
    session_id = request.args.get("session_id")
    sess = sessions.get(session_id or "")
    if not sess:
        return jsonify({"success": False, "error": "会话不存在"}), 404
    return jsonify({"success": True, "results": sess.get("results", [])})


@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json(force=True) or {}
    session_id = data.get("session_id")
    edits = data.get("edits") or []
    if not session_id:
        return jsonify({"success": False, "error": "缺少会话"}), 400
    sess = sessions.get(session_id)
    if not sess:
        return jsonify({"success": False, "error": "会话不存在"}), 404
    outputs_dir = Path(sess["outputs_dir"])
    uploads_dir = Path(sess["uploads_dir"])
    _ensure_dirs(outputs_dir)
    base_dir = TMP_DIR / session_id

    from PIL import Image, ImageDraw, ImageFont

    def get_font():
        # List of font paths to check
        # Prefer fonts that support Chinese (CJK)
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/truetype/arphic/uming.ttc",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf", # May not support CJK
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", # No CJK
            "arial.ttf",
        ]
        
        for path in candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, 20)
                except:
                    continue
            # Also try loading by name if it's not an absolute path or just a filename
            if not os.path.isabs(path):
                try:
                     return ImageFont.truetype(path, 20)
                except:
                    continue
                    
        return ImageFont.load_default()

    font = get_font()

    saved_items: List[Dict[str, Any]] = []
    for item in edits:
        name = item.get("name")
        ann = item.get("annotations") or []
        if not name:
            continue
        src = uploads_dir / name
        if not src.exists():
            continue
        img = Image.open(str(src)).convert("RGB")
        draw = ImageDraw.Draw(img)


        for a in ann:
            cls_id = int(a.get("class_id", 0))
            label = a.get("class_name") or str(cls_id)
            xyxy = a.get("bbox_xyxy") or [0, 0, 0, 0]
            hex_color = a.get("color", "#2563eb")
            
            # Parse hex color to RGB
            if hex_color.startswith('#'):
                hex_color = hex_color.lstrip('#')
                if len(hex_color) == 6:
                    r = int(hex_color[0:2], 16)
                    g = int(hex_color[2:4], 16)
                    b = int(hex_color[4:6], 16)
                    color = (r, g, b)
                else:
                    color = (37, 99, 235) # Default blue
            else:
                color = (37, 99, 235)

            x1, y1, x2, y2 = map(int, xyxy)
            draw.rectangle([(x1, y1), (x2, y2)], outline=color, width=3)
            
            # Text size
            try:
                bbox = font.getbbox(label)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
            except AttributeError:
                 tw, th = font.getsize(label)
            
            # Label Position: Outside Top, Inside Right (上边框的外，右边框内)
            # x aligns right with box right edge: x = x2 - total_width
            # y sits on top of box top edge: y = y1 - total_height
            
            total_w = tw + 10
            total_h = th + 10
            
            lx = x2 - total_w
            ly = y1 - total_h
            
            # Background
            draw.rectangle([lx, ly, lx + total_w, ly + total_h], fill=color)
            draw.text((lx + 5, ly + 5), label, fill=(255, 255, 255), font=font)

        out_path = outputs_dir / name
        img.save(str(out_path))
        meta_path = outputs_dir / f"{Path(name).stem}.json"
        with open(str(meta_path), "w", encoding="utf-8") as f:
            json.dump({"name": name, "annotations": ann}, f, ensure_ascii=False, indent=2)
        saved_items.append({
            "name": name,
            "output_url": f"/outputs/{session_id}/{name}",
            "meta_url": f"/outputs/{session_id}/{Path(name).stem}.json",
        })
        
    # Create ZIP archive
    zip_filename = f"results_{session_id}"
    shutil.make_archive(str(base_dir / zip_filename), 'zip', outputs_dir)
    
    return jsonify({
        "success": True, 
        "saved": saved_items, 
        "download_url": f"/download_zip/{session_id}/{zip_filename}.zip"
    })

@app.route("/download_zip/<session_id>/<filename>")
def download_zip(session_id: str, filename: str):
    d = TMP_DIR / session_id
    return send_from_directory(str(d), filename, as_attachment=True)


@app.route("/uploads/<session_id>/<filename>")
def serve_upload(session_id: str, filename: str):
    d = TMP_DIR / session_id / "uploads"
    return send_from_directory(str(d), filename)


@app.route("/outputs/<session_id>/<filename>")
def serve_output(session_id: str, filename: str):
    d = TMP_DIR / session_id / "outputs"
    return send_from_directory(str(d), filename)


def main():
    _ensure_dirs(TMP_DIR)
    app.run(host="0.0.0.0", port=8765, debug=True)


if __name__ == "__main__":
    main()

