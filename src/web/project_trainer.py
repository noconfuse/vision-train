from pathlib import Path
import os
import json
import threading
from datetime import datetime

class ProjectTrainer:
    def __init__(self, project):
        self.project = project
        self.is_training = False
        self.training_progress = 0
        self.training_message = ''
        self.last_training_time = None
        self.thread = None
        self.models_dir = Path(project.get('models_dir', Path(project['id']) / 'models'))
        self.datasets_dir = Path(project.get('dataset_dir', Path(project['id']) / 'datasets'))
        self.pretrained_dir = Path(project.get('pretrained_dir', Path(project['id']) / 'pretrained'))
        self.configs_dir = Path(project.get('configs_dir', Path(project['id']) / 'configs'))
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_dataset_yaml(self):
        candidates = [self.configs_dir / 'dataset.yaml', self.datasets_dir / 'dataset.yaml']
        for p in candidates:
            if p.exists():
                return str(p)
        data = {
            'path': str(self.datasets_dir),
            'train': 'train/images',
            'val': 'val/images' if (self.datasets_dir / 'val' / 'images').exists() else 'train/images',
            'nc': int(self.project.get('nc', len(self.project.get('classes', {})))),
            'names': [self.project['classes'][i] for i in sorted(self.project.get('classes', {}).keys())]
        }
        yaml_path = self.models_dir / 'dataset.auto.yaml'
        try:
            import yaml
            with open(yaml_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)
        except Exception:
            pass
        return str(yaml_path)

    def _resolve_model_weight(self):
        for name in ['best.pt', 'yolo11m.pt', 'weights.pt']:
            p = self.pretrained_dir / name
            if p.exists():
                return str(p)
        root_model = Path(os.getcwd()) / 'yolo11m.pt'
        return str(root_model) if root_model.exists() else 'yolo11m.pt'

    def _run_training(self, params):
        try:
            import subprocess
            self.is_training = True
            self.training_progress = 0
            self.training_message = '准备训练'
            dataset_yaml = self._resolve_dataset_yaml()
            model_weight = self._resolve_model_weight()
            epochs = int(params.get('epochs', 50))
            batch = int(params.get('batch', 16))
            lr0 = float(params.get('lr0', 0.001))
            workers = int(params.get('workers', 8))
            device = str(params.get('device', 'auto'))
            run = f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            cmd = [
                'yolo','train',
                f'data={dataset_yaml}',
                f'model={model_weight}',
                f'epochs={epochs}',
                f'batch={batch}',
                f'lr0={lr0}',
                f'workers={workers}',
                f'project={str(self.models_dir)}',
                f'name={run}',
                'save=True',
                'plots=True'
            ]
            env = os.environ.copy()
            env['PATH'] = f"{os.path.expanduser('~/.local/bin')}:{env.get('PATH','')}"
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
            total = epochs
            seen = 0
            while True:
                line = p.stdout.readline()
                if line == '' and p.poll() is not None:
                    break
                if line and 'Epoch' in line and 'GPU_mem' in line:
                    seen += 1
                    self.training_progress = min(100, int((seen/total)*100))
                    self.training_message = f'训练中 {seen}/{total}'
            code = p.wait()
            if code == 0:
                self.training_progress = 100
                self.training_message = '训练完成'
                self.last_training_time = datetime.now().isoformat()
                self._finalize_best(run)
            else:
                self.training_message = f'训练失败({code})'
        except Exception as e:
            self.training_message = f'训练异常: {e}'
        finally:
            self.is_training = False

    def _finalize_best(self, run):
        try:
            w = self.models_dir / run / 'weights' / 'best.pt'
            if w.exists():
                import shutil
                target = self.models_dir / 'best.pt'
                shutil.copy2(w, target)
                info = {
                    'version': datetime.now().strftime('%Y%m%d_%H%M%S'),
                    'model_path': str(target),
                    'run_name': run,
                    'updated_at': datetime.now().isoformat()
                }
                with open(self.models_dir / 'version_info.json', 'w', encoding='utf-8') as f:
                    json.dump(info, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def start_training(self, params):
        if self.is_training:
            return False
        self.thread = threading.Thread(target=self._run_training, args=(params,), daemon=True)
        self.thread.start()
        return True

    def stop_training(self):
        self.training_message = '停止请求'

    def get_status(self):
        return {
            'is_training': self.is_training,
            'training_progress': self.training_progress,
            'training_message': self.training_message,
            'last_training_time': self.last_training_time
        }

