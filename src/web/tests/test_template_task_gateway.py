"""部署模板任务网关的回归测试。"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from db.session import init_db

from contexts.training.infrastructure import template_task_gateway
from contexts.training.infrastructure.template_task_gateway import (
    delete_template_task,
    execute_template_task,
    list_template_source_choices,
    resolve_template_source_selection,
    start_template_task,
)
from contexts.task.domain.task_types import TASK_TYPE_TEMPLATE
from contexts.task.infrastructure.task_repository import create_task
from contexts.task.infrastructure.task_runtime import load_task


class TemplateTaskGatewayTests(unittest.TestCase):
    def setUp(self):
        init_db()
        self.project_path = tempfile.mkdtemp(prefix="vt_template_task_")
        self.output_dir = os.path.join(self.project_path, "training_outputs", "demo", "run_1")
        self.weights_dir = os.path.join(self.output_dir, "weights")
        os.makedirs(self.weights_dir, exist_ok=True)
        self.best_weight = os.path.join(self.weights_dir, "best.pt")
        self.last_weight = os.path.join(self.weights_dir, "last.pt")
        with open(self.best_weight, "w", encoding="utf-8") as handle:
            handle.write("dummy-best")
        with open(self.last_weight, "w", encoding="utf-8") as handle:
            handle.write("dummy-last")

        self.dataset_yaml = os.path.join(self.project_path, "dataset.yaml")
        with open(self.dataset_yaml, "w", encoding="utf-8") as handle:
            handle.write("names:\n  - person\n")

        self.src_task = {
            "id": "train_1",
            "type": "training",
            "status": "completed",
            "project_path": self.project_path,
            "dataset_name": "demo",
            "dataset_id": "ds_1",
            "dataset_version_id": "ver_1",
            "dataset_path": os.path.join(self.project_path, "datasets", "demo"),
            "vision_task_type": "detect",
            "payload": {},
            "artifacts": {
                "output_dir": self.output_dir,
                "best_weight_path": self.best_weight,
                "last_weight_path": self.last_weight,
                "dataset_yaml": self.dataset_yaml,
            },
        }
        # 真实写入 DB，便于 load_task() 命中
        created = create_task(
            project_path=self.project_path,
            project_name="demo_project",
            type_="training",
            dataset_name=self.src_task["dataset_name"],
            dataset_id=self.src_task["dataset_id"],
            dataset_version_id=self.src_task["dataset_version_id"],
            dataset_path=self.src_task["dataset_path"],
            vision_task_type=self.src_task["vision_task_type"],
            payload={},
            message="已就绪",
            artifacts=self.src_task["artifacts"],
        )
        self.src_task["id"] = created["id"]

    def tearDown(self):
        shutil.rmtree(self.project_path, ignore_errors=True)

    def test_list_template_source_choices(self):
        choices = list_template_source_choices()
        keys = {item["key"] for item in choices}
        self.assertIn("best", keys)
        self.assertIn("last", keys)

    def test_list_template_source_choices_for_task_includes_export(self):
        from contexts.task.domain.task_artifact_keys import ARTIFACT_EXPORT_PATH
        from contexts.task.infrastructure.task_repository import create_task
        export_dir = os.path.join(self.project_path, "training_outputs", "demo", "run_1", "export", "exp_1")
        os.makedirs(export_dir, exist_ok=True)
        onnx_path = os.path.join(export_dir, "model.onnx")
        with open(onnx_path, "w", encoding="utf-8") as handle:
            handle.write("dummy-onnx")
        export_task = create_task(
            project_path=self.project_path,
            project_name="demo_project",
            type_="export",
            dataset_name=self.src_task["dataset_name"],
            dataset_id=self.src_task["dataset_id"],
            dataset_version_id=self.src_task["dataset_version_id"],
            dataset_path=self.src_task["dataset_path"],
            vision_task_type="detect",
            payload={"src_task_id": self.src_task["id"], "format": "onnx", "imgsz": 640},
            message="已导出",
            artifacts={ARTIFACT_EXPORT_PATH: onnx_path},
        )
        from contexts.task.infrastructure.task_repository import update_task
        update_task(export_task["id"], status="completed")
        from contexts.training.infrastructure.template_task_gateway import (
            list_template_source_choices_for_task,
        )

        choices = list_template_source_choices_for_task(self.project_path, self.src_task["id"])
        keys = [item["key"] for item in choices]
        self.assertIn("best", keys)
        self.assertIn("last", keys)
        self.assertTrue(any(key.startswith("export:") for key in keys))
        export_choice = next(item for item in choices if item["key"].startswith("export:"))
        self.assertEqual(export_choice["format"], "onnx")
        self.assertTrue(export_choice["source_model_path"].endswith("model.onnx"))

    def test_resolve_template_source_selection_unknown(self):
        with self.assertRaises(ValueError):
            resolve_template_source_selection("bogus")

    def test_start_template_task_creates_task_and_records(self):
        with patch.object(template_task_gateway, "spawn_worker_process") as spawn_mock:
            spawn_mock.return_value = (type("Proc", (), {"pid": 1234})(), None)
            with patch.object(template_task_gateway, "mark_worker_started") as mark_mock:
                result = start_template_task(
                project_path=self.project_path,
                src_task_id=self.src_task["id"],
                template_type="fastapi_service",
                source="best",
                source_format="pt",
            )
                self.assertTrue(result["task_id"])
                mark_mock.assert_called_once()
        # 验证任务记录
        from contexts.task.infrastructure.task_runtime import load_task

        task = load_task(result["task_id"])
        self.assertEqual(task["type"], TASK_TYPE_TEMPLATE)
        self.assertEqual(task["payload"]["template_type"], "fastapi_service")
        self.assertEqual(task["payload"]["source"], "best")
        self.assertEqual(task["payload"]["source_format"], "pt")
        self.assertEqual(task["payload"]["source_model_path"], self.best_weight)

    def test_execute_template_task_generates_template(self):
        with patch.object(template_task_gateway, "spawn_worker_process") as spawn_mock:
            spawn_mock.return_value = (type("Proc", (), {"pid": 1})(), None)
            with patch.object(template_task_gateway, "mark_worker_started"):
                result = start_template_task(
                project_path=self.project_path,
                src_task_id=self.src_task["id"],
                template_type="python_sdk",
                source="best",
                source_format="pt",
            )
                task_id = result["task_id"]

        with patch.object(template_task_gateway, "mark_worker_started"):
            execute_template_task(task_id)

        from contexts.task.infrastructure.task_runtime import load_task

        task = load_task(task_id)
        self.assertEqual(task["status"], "completed")
        self.assertTrue(task["artifacts"]["template_dir"])
        self.assertTrue(os.path.isfile(task["artifacts"]["template_manifest_path"]))
        self.assertEqual(task["artifacts"]["template_type"], "python_sdk")
        self.assertEqual(task["artifacts"]["template_source_format"], "pt")

        # 模板目录应包含源模型 + SDK 文件
        self.assertTrue(
            os.path.isfile(os.path.join(task["artifacts"]["template_dir"], "model", "best.pt"))
        )
        self.assertTrue(
            os.path.isfile(os.path.join(task["artifacts"]["template_dir"], "sdk", "predictor.py"))
        )

    def test_execute_template_task_rejects_missing_weight(self):
        os.remove(self.best_weight)
        os.remove(self.last_weight)
        with patch.object(template_task_gateway, "spawn_worker_process") as spawn_mock:
            spawn_mock.return_value = (type("Proc", (), {"pid": 1})(), None)
            with patch.object(template_task_gateway, "mark_worker_started"):
                with self.assertRaises(ValueError):
                    start_template_task(
                        project_path=self.project_path,
                        src_task_id=self.src_task["id"],
                        template_type="fastapi_service",
                        source="best",
                        source_format="pt",
                    )

    def test_delete_template_task_removes_artifacts(self):
        with patch.object(template_task_gateway, "spawn_worker_process") as spawn_mock:
            spawn_mock.return_value = (type("Proc", (), {"pid": 1})(), None)
            with patch.object(template_task_gateway, "mark_worker_started"):
                result = start_template_task(
                project_path=self.project_path,
                src_task_id=self.src_task["id"],
                template_type="python_sdk",
                source="best",
                source_format="pt",
            )
                task_id = result["task_id"]
        with patch.object(template_task_gateway, "mark_worker_started"):
            execute_template_task(task_id)

        from contexts.task.infrastructure.task_runtime import load_task

        task = load_task(task_id)
        template_dir = task["artifacts"]["template_dir"]
        self.assertTrue(os.path.isdir(template_dir))

        delete_result = delete_template_task(self.project_path, task_id)
        self.assertFalse(os.path.exists(template_dir))
        self.assertEqual(delete_result["deleted"], task_id)


if __name__ == "__main__":
    unittest.main()