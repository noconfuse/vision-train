
import os
from roboflow import Roboflow

api_key = os.getenv("ROBOFLOW_API_KEY")
rf = Roboflow(api_key=api_key) if api_key else Roboflow()
workspace = rf.workspace("test-rpqnn")
workspace.project_list = [p for p in workspace.project_list if isinstance(p, dict) and "annotation" in p]
workspace.deploy_model(
    model_type="yolov11",
    model_path="/home/paul/worksapce/vision-train/pretrained_models",
    project_ids=["my-first-project-7avfg"],
    model_name="yolo11m",
    filename="yolo11m.pt"
)