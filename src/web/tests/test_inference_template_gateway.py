"""部署模板生成器与展示的回归测试。"""

import os
import py_compile
import shutil
import tempfile
import unittest

from contexts.task.domain.task_artifact_keys import ARTIFACT_DATASET_YAML
from contexts.training.infrastructure.inference_template_gateway import (
    DEPLOYMENT_MANIFEST_FILENAME,
    generate_inference_template_bundle,
    list_inference_template_specs,
    normalize_inference_template_type,
    normalize_template_source_format,
    resolve_template_source_path,
)
from shared.utils.json_utils import load_json_file

_TEMPLATES = {
    "fastapi_service": {
        "files": [
            "README.md",
            "Dockerfile",
            "curl_examples.sh",
            "app/main.py",
            "app/predictor.py",
            "scripts/infer_folder.py",
            "scripts/smoke_test.py",
        ],
        "compile_targets": [
            "app/main.py",
            "app/predictor.py",
            "scripts/infer_folder.py",
            "scripts/smoke_test.py",
        ],
        "entrypoint": "app.main:app",
    },
    "python_sdk": {
        "files": [
            "README.md",
            "Dockerfile",
            "sdk/__init__.py",
            "sdk/predictor.py",
            "examples/predict.py",
            "examples/predict_folder.py",
        ],
        "compile_targets": [
            "sdk/__init__.py",
            "sdk/predictor.py",
            "examples/predict.py",
            "examples/predict_folder.py",
        ],
        "entrypoint": "sdk.predictor:Predictor",
    },
    "batch_processor": {
        "files": [
            "README.md",
            "Dockerfile",
            "runner/__init__.py",
            "runner/predictor.py",
            "runner/main.py",
        ],
        "compile_targets": [
            "runner/__init__.py",
            "runner/predictor.py",
            "runner/main.py",
        ],
        "entrypoint": "runner.main:main",
    },
}


class InferenceTemplateCoreTests(unittest.TestCase):
    """直接验证 inference_template_gateway 的纯生成能力。"""

    def setUp(self):
        self.temp_root = tempfile.mkdtemp(prefix="vt_infer_template_")
        self.dataset_yaml = os.path.join(self.temp_root, "dataset.yaml")
        with open(self.dataset_yaml, "w", encoding="utf-8") as handle:
            handle.write("names:\n  - person\n")

    def tearDown(self):
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def _write_source_model(self, name):
        source_dir = os.path.join(self.temp_root, "src")
        os.makedirs(source_dir, exist_ok=True)
        path = os.path.join(source_dir, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("dummy-model")
        return path

    def _target_dir(self, template_type, source_format):
        return os.path.join(self.temp_root, "templates", f"{template_type}-{source_format}")

    def test_list_specs_returns_three_templates(self):
        specs = list_inference_template_specs()
        keys = {item["template_type"] for item in specs}
        self.assertEqual(keys, {"fastapi_service", "python_sdk", "batch_processor"})

    def test_normalize_helpers_validate_input(self):
        self.assertEqual(normalize_inference_template_type("FastAPI_Service"), "fastapi_service")
        self.assertEqual(normalize_template_source_format("ONNX"), "onnx")
        with self.assertRaises(ValueError):
            normalize_inference_template_type("nope")
        with self.assertRaises(ValueError):
            normalize_template_source_format("safetensors")

    def test_resolve_template_source_path_finds_known_extensions(self):
        onnx_path = self._write_source_model("a.onnx")
        self.assertEqual(
            resolve_template_source_path(os.path.dirname(onnx_path), "onnx"),
            onnx_path,
        )
        pt_path = self._write_source_model("best.pt")
        self.assertEqual(resolve_template_source_path(pt_path, "pt"), pt_path)

    def test_each_template_supports_pt_onnx_openvino_engine_sources(self):
        for template_type in _TEMPLATES:
            for source_format, source_name in (
                ("pt", "best.pt"),
                ("onnx", "model.onnx"),
                ("openvino", "model.xml"),
                ("engine", "model.engine"),
            ):
                with self.subTest(template=template_type, source=source_format):
                    source_path = self._write_source_model(source_name)
                    target_dir = self._target_dir(template_type, source_format)
                    bundle = generate_inference_template_bundle(
                        template_type=template_type,
                        source_model_path=source_path,
                        source_format=source_format,
                        vision_task_type="detect",
                        dataset_yaml_path=self.dataset_yaml,
                        training_task_id="train_runtime",
                        target_dir=target_dir,
                        imgsz=640,
                        half=False,
                        int8=False,
                    )
                    self.assertEqual(bundle["template_type"], template_type)
                    self.assertEqual(bundle["source_format"], source_format)
                    self.assertTrue(os.path.isdir(bundle["template_dir"]))
                    expected_model_relpath = os.path.join("model", source_name).replace(os.sep, "/")
                    self.assertEqual(bundle["model_relative_path"], expected_model_relpath)
                    self.assertTrue(
                        os.path.isfile(os.path.join(bundle["template_dir"], expected_model_relpath))
                    )

                    for relative_path in _TEMPLATES[template_type]["files"]:
                        self.assertTrue(
                            os.path.isfile(os.path.join(bundle["template_dir"], relative_path)),
                            msg=f"{template_type} 缺少 {relative_path}",
                        )
                    for relative_path in _TEMPLATES[template_type]["compile_targets"]:
                        py_compile.compile(
                            os.path.join(bundle["template_dir"], relative_path),
                            doraise=True,
                        )

                    manifest = load_json_file(bundle["manifest_path"], default={})
                    self.assertEqual(manifest.get("template_type"), template_type)
                    self.assertEqual(manifest.get("entrypoint"), _TEMPLATES[template_type]["entrypoint"])
                    self.assertEqual(manifest.get("source_format"), source_format)
                    self.assertEqual(manifest.get("model_relative_path"), expected_model_relpath)

                    model_info = load_json_file(
                        os.path.join(bundle["template_dir"], "config", "model_info.json"),
                        default={},
                    )
                    self.assertEqual(model_info.get("vision_task_type"), "detect")
                    self.assertEqual(model_info.get("source_format"), source_format)
                    self.assertEqual(model_info.get("class_names"), ["person"])
                    self.assertEqual(model_info.get("source_training_task_id"), "train_runtime")

    def test_pt_template_does_not_require_onnx_runtime(self):
        source_path = self._write_source_model("best.pt")
        target_dir = self._target_dir("fastapi_service", "pt")
        bundle = generate_inference_template_bundle(
            template_type="fastapi_service",
            source_model_path=source_path,
            source_format="pt",
            vision_task_type="detect",
            target_dir=target_dir,
        )
        requirements = load_requirements(os.path.join(bundle["template_dir"], "requirements.txt"))
        self.assertIn("ultralytics>=8.2.0", requirements)
        self.assertNotIn("onnxruntime>=1.18.0", requirements)

    def test_invalid_source_path_raises(self):
        with self.assertRaises(ValueError):
            generate_inference_template_bundle(
                template_type="fastapi_service",
                source_model_path=os.path.join(self.temp_root, "missing.pt"),
                source_format="pt",
                vision_task_type="detect",
                target_dir=self._target_dir("fastapi_service", "pt"),
            )


def load_requirements(path):
    with open(path, "r", encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip() and not line.startswith("#")]


if __name__ == "__main__":
    unittest.main()