import os
import sys
import threading
from ultralytics import YOLO

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from managers.training_manager import TrainingManager

export_status = {
    'export_id': None,
    'is_running': False,
    'progress': 0,
    'message': '',
    'error': None,
    'result_path': None
}

class ExportManager:
    """模型导出管理器"""
    @staticmethod
    def export_model(project_path, training_id, format_='onnx', half=False, int8=False, imgsz=None, per_class=20, max_images=200, weights_path=None):
        """执行导出"""
        try:
            if not weights_path:
                # 查找 run
                runs = TrainingManager.list_training_runs(project_path)
                run = next((r for r in runs if r['id'] == training_id), None)
                if not run:
                    raise ValueError("未找到训练记录")
                weights_path = os.path.join(run['path'], 'weights', 'best.pt')
                if not os.path.exists(weights_path):
                    weights_path = os.path.join(run['path'], 'weights', 'last.pt')
            
            if not os.path.exists(weights_path):
                raise ValueError("未找到权重文件")
                
            export_status['message'] = f'正在加载模型 {os.path.basename(weights_path)}...'
            model = YOLO(weights_path)
            
            args = {'format': format_}
            if imgsz:
                args['imgsz'] = imgsz
            if half:
                args['half'] = True
            if int8:
                args['int8'] = True
                # INT8 需要校准数据
                # 简单处理：使用 data.yaml 中的 val 数据
                # 这里略过复杂的数据准备，Ultralytics 会尝试自动处理或报错
                
            export_status['message'] = f'开始导出为 {format_}...'
            res = model.export(**args)
            
            export_status['message'] = '导出完成'
            export_status['progress'] = 100
            export_status['result_path'] = res
            
        except Exception as e:
            export_status['error'] = str(e)
            export_status['message'] = '导出失败'
        finally:
            export_status['is_running'] = False

    @staticmethod
    def get_status():
        return export_status
