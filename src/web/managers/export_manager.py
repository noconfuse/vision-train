import os
import sys
import shutil
import json
import yaml
import threading
from datetime import datetime
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
    'result_path': None,
    'results': {}
}

class ExportManager:
    """模型导出管理器"""

    @staticmethod
    def get_status():
        return export_status

    @staticmethod
    def build_calibration_subset(project_path, dataset_name='training', training_id=None, per_class=20, max_images=200, dataset_yaml=None):
        dataset_dir = os.path.join(project_path, "training", dataset_name)
        # 如果 dataset_name 是 run 所在的目录，可能并不是原始 dataset 目录，尝试修正
        if not os.path.exists(dataset_dir):
            # 尝试在 training 目录下查找
            training_root = os.path.join(project_path, "training")
            if os.path.exists(training_root):
                for d in os.listdir(training_root):
                    if d == dataset_name:
                        dataset_dir = os.path.join(training_root, d)
                        break
        
        y = {}
        if dataset_yaml and os.path.exists(dataset_yaml):
            try:
                with open(dataset_yaml, 'r', encoding='utf-8') as f:
                    y = yaml.safe_load(f) or {}
            except Exception:
                y = {}
        else:
            for yfile in (os.path.join(dataset_dir, 'dataset.yaml'), os.path.join(dataset_dir, 'data.yaml')):
                if os.path.exists(yfile):
                    dataset_yaml = yfile
                    try:
                        with open(yfile, 'r', encoding='utf-8') as f:
                            y = yaml.safe_load(f) or {}
                    except Exception:
                        y = {}
                    break

        dataset_base = os.path.dirname(dataset_yaml) if dataset_yaml else dataset_dir
        base_path = y.get('path') or dataset_base
        
        def _abspath(p):
            if not p:
                return None
            return p if os.path.isabs(p) else os.path.join(base_path, p)
            
        # 严格遵循现有规范：仅使用 images/train 作为校准图片来源
        train_images_path = _abspath(y.get('train'))
        if not train_images_path or not os.path.exists(train_images_path):
            alt_train = os.path.join(base_path, 'images', 'train')
            if os.path.exists(alt_train):
                train_images_path = alt_train
            else:
                found = None
                for root, dirs, _ in os.walk(base_path):
                    if 'images' in dirs and os.path.exists(os.path.join(root, 'images', 'train')):
                        found = os.path.join(root, 'images', 'train')
                        break
                train_images_path = found

        # 严格规范：标签目录固定 labels/train（可选），缺失时按图片均匀采样
        labels_train = os.path.join(base_path, 'labels', 'train')
        labels_train = labels_train if os.path.exists(labels_train) else None

        names = y.get('names') or []
        nc = y.get('nc') or (len(names) if names else None)

        class_to_images = {}
        image_to_classes = {}
        if labels_train:
            for root, _, files in os.walk(labels_train):
                for f in files:
                    if not f.endswith('.txt'):
                        continue
                    lbl_path = os.path.join(root, f)
                    rel_lbl = os.path.relpath(lbl_path, labels_train)
                    img_rel = os.path.splitext(rel_lbl)[0] + '.jpg' 
                    # Note: assuming jpg, but could be png. Check existence? 
                    # Optimization: Just store base name and resolve extension later if needed, 
                    # or better: scan images and match.
                    # For simplicity, let's assume images match label names.
                    
                    # Better approach: Scan images first
                    pass

        # Re-implementing selection logic more robustly
        # 1. Scan all images
        all_images = []
        if train_images_path and os.path.exists(train_images_path):
            for root, _, files in os.walk(train_images_path):
                for f in files:
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                        all_images.append(os.path.join(root, f))
        
        # 2. Map images to classes if labels exist
        if labels_train:
            for img_path in all_images:
                rel_path = os.path.relpath(img_path, train_images_path)
                # Try to find corresponding label
                base_name = os.path.splitext(os.path.basename(img_path))[0]
                lbl_path = os.path.join(labels_train, base_name + '.txt')
                
                image_to_classes.setdefault(img_path, set())
                if os.path.exists(lbl_path):
                    try:
                        with open(lbl_path, 'r', encoding='utf-8') as lf:
                            for line in lf:
                                parts = line.strip().split()
                                if not parts: continue
                                cid = int(parts[0])
                                image_to_classes[img_path].add(cid)
                                class_to_images.setdefault(cid, set()).add(img_path)
                    except:
                        pass
        else:
             # No labels, treat as single class or just random sample
             for img_path in all_images:
                 image_to_classes.setdefault(img_path, set())

        # 3. Select images
        selected = set()
        cids = sorted(class_to_images.keys())
        
        if cids:
            rounds = 0
            while rounds < per_class and len(selected) < max_images:
                added_in_round = False
                for cid in cids:
                    pool = class_to_images.get(cid, set())
                    pick = next((p for p in pool if p not in selected), None)
                    if pick:
                        selected.add(pick)
                        added_in_round = True
                    if len(selected) >= max_images:
                        break
                if not added_in_round:
                    break
                rounds += 1
        
        # Fill remaining if needed
        if len(selected) < max_images and all_images:
            import random
            remaining = [img for img in all_images if img not in selected]
            # Shuffle deterministically if needed, or just take first N
            random.shuffle(remaining)
            need = max_images - len(selected)
            selected.update(remaining[:need])

        # 4. Prepare output directory
        base_out = os.path.join(project_path, 'training_outputs')
        if training_id is None:
            training_id = f"export_calib_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        calib_root = os.path.join(base_out, training_id if training_id else 'temp', 'calibration', ts)
        img_out = os.path.join(calib_root, 'images', 'train')
        os.makedirs(img_out, exist_ok=True)
        
        lbl_out = None
        if labels_train:
            lbl_out = os.path.join(calib_root, 'labels', 'train')
            os.makedirs(lbl_out, exist_ok=True)

        for src_img in selected:
            if not os.path.exists(src_img):
                continue
            fname = os.path.basename(src_img)
            dst_img = os.path.join(img_out, fname)
            shutil.copy2(src_img, dst_img)
            
            if lbl_out:
                base_name = os.path.splitext(fname)[0]
                src_lbl = os.path.join(labels_train, base_name + '.txt')
                if os.path.exists(src_lbl):
                    dst_lbl = os.path.join(lbl_out, base_name + '.txt')
                    shutil.copy2(src_lbl, dst_lbl)

        # 5. Generate data.yaml
        data_yaml_content = {
            'path': calib_root,
            'train': 'images/train',
            'val': 'images/train', # Use train for val in calibration to avoid errors
            'names': names if names else {0: 'object'}
        }
        if nc is not None:
            data_yaml_content['nc'] = nc
            
        calib_yaml_path = os.path.join(calib_root, 'data.yaml')
        with open(calib_yaml_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data_yaml_content, f, allow_unicode=True)
            
        return calib_yaml_path, calib_root

    @staticmethod
    def export_model(project_path, training_id=None, format='onnx', half=False, int8=False, imgsz=None, per_class=20, max_images=200, weights_path=None):
        global export_status
        export_status.update({
            'is_running': True, 
            'progress': 0, 
            'message': '准备导出...', 
            'start_time': datetime.now().isoformat(), 
            'results': {},
            'error': None
        })
        
        try:
            # 1. Locate weights and run directory
            run_dir = None
            if weights_path:
                if not os.path.exists(weights_path):
                    raise FileNotFoundError(f"指定的权重文件不存在: {weights_path}")
                weights = weights_path
                # Try to infer run_dir
                possible_run_dir = os.path.dirname(os.path.dirname(weights_path))
                if os.path.exists(os.path.join(possible_run_dir, 'training_config.json')):
                    run_dir = possible_run_dir
            else:
                runs = TrainingManager.list_training_runs(project_path)
                target_run = None
                if training_id:
                    target_run = next((r for r in runs if r['id'] == training_id), None)
                elif runs:
                    target_run = runs[0]
                
                if not target_run:
                    raise FileNotFoundError("未找到可用的训练记录")
                
                run_dir = target_run['path']
                weights_dir = os.path.join(run_dir, 'weights')
                weights = os.path.join(weights_dir, 'best.pt')
                if not os.path.exists(weights):
                    weights = os.path.join(weights_dir, 'last.pt')
                
                if not os.path.exists(weights):
                    raise FileNotFoundError(f"在 {run_dir} 中未找到权重文件")

            # 2. Prepare export directory
            # 统一覆盖到 latest 目录，不产生版本
            # But also keep under the specific training_id if available
            if training_id:
                export_dir = os.path.join(run_dir, 'export', 'latest')
            else:
                export_dir = os.path.join(project_path, 'training_outputs', 'export', 'latest')
                
            if os.path.exists(export_dir):
                try:
                    shutil.rmtree(export_dir)
                except Exception:
                    pass
            os.makedirs(export_dir, exist_ok=True)

            export_status['message'] = f'加载模型 {os.path.basename(weights)}...'
            model = YOLO(weights)
            
            args = {'format': format, 'half': bool(half), 'imgsz': imgsz}
            calib_root = None
            
            if int8:
                export_status['message'] = '构建校准集...'
                # Attempt to find original dataset config
                dy = None
                if run_dir:
                    cfg_path = os.path.join(run_dir, 'training_config.json')
                    if os.path.exists(cfg_path):
                        try:
                            with open(cfg_path, 'r', encoding='utf-8') as f:
                                info = json.load(f)
                                dy = info.get('dataset_yaml')
                        except:
                            pass
                
                dataset_name = 'training' # Default
                if run_dir:
                    dataset_name = os.path.basename(os.path.dirname(run_dir))
                
                calib_yaml, calib_root = ExportManager.build_calibration_subset(
                    project_path, 
                    dataset_name=dataset_name,
                    training_id=training_id or 'temp',
                    per_class=per_class, 
                    max_images=max_images, 
                    dataset_yaml=dy
                )
                export_status['message'] = f'构建校准集完成: {calib_yaml}'
                args.update({'format': 'openvino', 'int8': True, 'data': calib_yaml}) # INT8 typically implies OpenVINO or TensorRT with calibration
                
                # If format is specifically onnx with int8, Ultralytics might handle it differently, 
                # but usually 'int8' arg requires data.
                if format != 'openvino':
                     args['format'] = format # User requested format
                     args['int8'] = True
                     args['data'] = calib_yaml

            export_status['message'] = f'执行导出为 {args["format"]}...'
            # Remove None values
            clean_args = {k: v for k, v in args.items() if v is not None}
            out = model.export(**clean_args)
            
            export_status['message'] = '导出完成，正在打包...'
            
            # Clean up calibration data
            if calib_root and os.path.exists(calib_root):
                try:
                    shutil.rmtree(calib_root, ignore_errors=True)
                except:
                    pass

            export_status['progress'] = 90
            
            # Normalize output files
            results = {}
            if isinstance(out, (list, tuple)):
                files = [str(x) for x in out]
            else:
                files = [str(out)]

            # Copy to export directory
            copied = []
            for fp in files:
                if not fp: continue
                
                fname = os.path.basename(fp)
                dst = os.path.join(export_dir, fname)
                
                if os.path.isdir(fp):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(fp, dst)
                    copied.append(dst)
                else:
                    shutil.copy2(fp, dst)
                    copied.append(dst)

            # Identify primary model file
            primary = ''
            for c in copied:
                if c.endswith('.onnx'): primary = c; break
                if c.endswith('.xml'): primary = c; break
                if c.endswith('.engine'): primary = c; break
                if c.endswith('.pt') and c != weights: primary = c; break

            # Create ZIP package for download
            try:
                zip_name = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                zip_root = os.path.dirname(export_dir)
                zip_path_generated = shutil.make_archive(os.path.join(zip_root, zip_name), 'zip', export_dir)
                
                # Move zip into export_dir so it is self-contained and listed
                final_zip_path = os.path.join(export_dir, os.path.basename(zip_path_generated))
                shutil.move(zip_path_generated, final_zip_path)
                
                zip_path = final_zip_path
                results['zip_path'] = zip_path
                copied.append(zip_path) # Add to copied files list
            except Exception as e:
                print(f"Zip creation failed: {e}")
                zip_path = None

            # Calculate total size
            def _sz(p):
                try:
                    if os.path.isdir(p):
                        total = 0
                        for root, _, fs in os.walk(p):
                            for f in fs:
                                total += os.path.getsize(os.path.join(root, f))
                        return total
                    return os.path.getsize(p)
                except:
                    return 0

            results['files'] = copied
            results['primary_model_path'] = primary
            results['total_size_bytes'] = sum(_sz(p) for p in copied)
            results['export_dir'] = export_dir
            
            export_status['results'] = results
            # Prioritize ZIP for download if available, otherwise primary model
            export_status['result_path'] = zip_path if zip_path else primary 
            export_status['progress'] = 100
            export_status['message'] = '导出成功'
            
            return {'success': True, 'export_dir': export_dir, 'results': results}

        except Exception as e:
            import traceback
            traceback.print_exc()
            export_status['error'] = str(e)
            export_status['message'] = f'导出失败: {str(e)}'
            return {'success': False, 'error': str(e)}
        finally:
            export_status['is_running'] = False

    @staticmethod
    def list_exports(project_path, training_id=None):
        """列出导出记录"""
        items = []
        base = os.path.join(project_path, 'training_outputs')
        if not os.path.exists(base):
            return items

        # Helper to process an export dir
        def process_export_dir(exp_dir, tid):
            if not os.path.exists(exp_dir):
                return None
            
            files = []
            for root, _, fs in os.walk(exp_dir):
                for f in fs:
                    files.append(os.path.join(root, f))
            
            if not files:
                return None
                
            primary = ''
            for f in files:
                if f.endswith('.onnx'): primary = f; break
                if f.endswith('.xml'): primary = f; break
                if f.endswith('.engine'): primary = f; break
                
            def _sz(p):
                try:
                    return os.path.getsize(p)
                except:
                    return 0
            
            total = sum(_sz(p) for p in files)
            return {
                'training_id': tid,
                'ts': 'latest',
                'files': files,
                'primary_model_path': primary,
                'export_dir': exp_dir,
                'total_size_bytes': total
            }

        # 1. Check global latest export (legacy)
        global_latest = os.path.join(base, 'export', 'latest')
        res = process_export_dir(global_latest, 'latest')
        if res:
            items.append(res)

        # 2. Check per-run exports
        for ds in os.listdir(base):
            ds_dir = os.path.join(base, ds)
            if not os.path.isdir(ds_dir):
                continue
            
            # If specific training_id is requested, only look there
            if training_id:
                if training_id in os.listdir(ds_dir):
                    latest = os.path.join(ds_dir, training_id, 'export', 'latest')
                    res = process_export_dir(latest, training_id)
                    if res:
                        items.append(res)
            else:
                # Scan all runs in dataset
                for rid in os.listdir(ds_dir):
                    latest = os.path.join(ds_dir, rid, 'export', 'latest')
                    res = process_export_dir(latest, rid)
                    if res:
                        items.append(res)

        return items
