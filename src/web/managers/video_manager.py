import os
import json
import uuid
import shutil
import threading
import time
from datetime import datetime
import cv2
import numpy as np

class VideoManager:
    # In-memory task store (could be persisted to disk if needed)
    _tasks = {}
    _lock = threading.Lock()

    @staticmethod
    def _get_task_dir(project_path, task_id):
        return os.path.join(project_path, 'temp_tasks', task_id)

    @staticmethod
    def _get_task_meta_path(project_path, task_id):
        return os.path.join(VideoManager._get_task_dir(project_path, task_id), 'task.json')

    @staticmethod
    def _write_task_meta(project_path, task_info):
        try:
            task_dir = VideoManager._get_task_dir(project_path, task_info['id'])
            os.makedirs(task_dir, exist_ok=True)
            meta_path = VideoManager._get_task_meta_path(project_path, task_info['id'])
            data = dict(task_info)
            data.pop('images_dir', None)
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def _read_task_meta(project_path, task_id):
        meta_path = VideoManager._get_task_meta_path(project_path, task_id)
        if not os.path.exists(meta_path):
            return None
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    @staticmethod
    def scan_videos(project_path):
        """扫描项目下的视频文件"""
        video_dir = os.path.join(project_path, 'videos')
        videos = []
        if not os.path.exists(video_dir):
            return videos
            
        # Ensure thumbnails directory exists
        thumb_dir = os.path.join(video_dir, '.thumbnails')
        os.makedirs(thumb_dir, exist_ok=True)

        for f in os.listdir(video_dir):
            if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
                path = os.path.join(video_dir, f)
                try:
                    size = os.path.getsize(path)
                    
                    # Generate/Check thumbnail
                    thumb_name = f"{f}.jpg"
                    thumb_path = os.path.join(thumb_dir, thumb_name)
                    if not os.path.exists(thumb_path):
                        VideoManager.generate_thumbnail(path, thumb_path)
                        
                    videos.append({
                        'name': f,
                        'path': path,
                        'size': size,
                        'size_mb': round(size / (1024*1024), 2),
                        'modified': datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M:%S'),
                        'thumbnail_path': thumb_path
                    })
                except Exception as e:
                    print(f"Error scanning video {f}: {e}")
                    
        return sorted(videos, key=lambda x: x['name'])

    @staticmethod
    def generate_thumbnail(video_path, save_path):
        """生成视频缩略图"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return
            
            # Try to grab a frame at 1 second mark, or the first frame
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            
            if frame_count > fps and fps > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps)) # 1 second
            
            ret, frame = cap.read()
            if ret:
                # Resize to reduce size (e.g., height 300px)
                h, w = frame.shape[:2]
                target_h = 300
                scale = target_h / h
                target_w = int(w * scale)
                frame = cv2.resize(frame, (target_w, target_h))
                cv2.imwrite(save_path, frame)
                
            cap.release()
        except Exception as e:
            print(f"Failed to generate thumbnail for {video_path}: {e}")

    @staticmethod
    def start_extraction_task(project_path, video_name, strategy='interval', value=1.0):
        """启动抽帧任务"""
        task_id = str(uuid.uuid4())
        task_dir = VideoManager._get_task_dir(project_path, task_id)
        images_dir = os.path.join(task_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        task_info = {
            'id': task_id,
            'video_name': video_name,
            'status': 'running',
            'progress': 0,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_frames': 0,
            'extracted_count': 0,
            'error': None,
            'strategy': strategy,
            'value': value,
            'images_dir': images_dir
        }
        
        with VideoManager._lock:
            VideoManager._tasks[task_id] = task_info
        VideoManager._write_task_meta(project_path, task_info)

        # Start background thread
        thread = threading.Thread(target=VideoManager._extraction_worker, 
                                args=(project_path, video_name, task_id, strategy, value))
        thread.daemon = True
        thread.start()
        
        return task_id

    @staticmethod
    def _should_use_robust_mode(cap, fps, total_frames, strategy, value):
        try:
            if fps <= 0 or total_frames <= 0:
                return True

            # Check start, middle, and near end
            probe_indices = [
                0, 
                int(total_frames * 0.5), 
                max(0, total_frames - int(fps) - 1)
            ]
            
            for frame_idx in probe_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                if (not ret) or frame is None:
                    return True

            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return False
        except Exception:
            return True

    @staticmethod
    def _get_video_info_ffprobe(video_path):
        """Use ffprobe to get accurate video info (duration, frames, fps) for broken containers"""
        try:
            import subprocess
            
            # Get frame count by counting packets (most accurate for broken streams)
            cmd = [
                'ffprobe', 
                '-v', 'error', 
                '-select_streams', 'v:0', 
                '-count_packets', 
                '-show_entries', 'stream=nb_read_packets', 
                '-of', 'csv=p=0', 
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                try:
                    frames = int(result.stdout.strip())
                    return frames
                except ValueError:
                    pass
            return 0
        except Exception as e:
            print(f"FFprobe failed: {e}")
            return 0

    @staticmethod
    def _extract_using_ffmpeg(project_path, video_path, images_dir, task_id, strategy, value, total_frames, fps, video_basename):
        """Use ffmpeg command line for extraction (more robust for broken videos)"""
        import subprocess
        import time
        from collections import deque
        
        try:
            # Build filter
            vf_filter = ""
            target_count_est = 0
            
            if strategy == 'interval':
                # value is seconds. fps = 1/value
                if value <= 0: value = 1
                vf_filter = f"fps=1/{value}"
                duration = total_frames / fps if fps > 0 else 0
                target_count_est = int(duration / value)
            elif strategy == 'count':
                # value is total count.
                target_count_est = int(value)
                duration = total_frames / fps if fps > 0 else 0
                if duration > 0:
                    rate = value / duration
                    vf_filter = f"fps={rate}"
                else:
                    vf_filter = "fps=1"
            
            # Output pattern: video_name_f000001.jpg
            # Note: ffmpeg numbering will be sequential (1, 2, 3...) not original frame index.
            # This is a trade-off for robustness.
            output_pattern = os.path.join(images_dir, f"{video_basename}_f%06d.jpg")
            
            cmd = [
                'ffmpeg',
                '-y', # Overwrite
                '-i', video_path,
                '-vf', vf_filter,
                '-q:v', '2', # High quality
                '-start_number', '0',
                output_pattern
            ]
            
            print(f"Starting ffmpeg extraction: {' '.join(cmd)}")
            
            stderr_tail = deque(maxlen=80)

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            def _drain_stderr():
                try:
                    if process.stderr is None:
                        return
                    for line in process.stderr:
                        stderr_tail.append(line.rstrip('\n'))
                except Exception:
                    pass

            drain_thread = threading.Thread(target=_drain_stderr, daemon=True)
            drain_thread.start()
            
            # Monitor progress
            last_count = -1
            last_change_ts = time.time()
            while process.poll() is None:
                try:
                    # Count files to estimate progress
                    # This is lightweight enough for 1s sleep
                    files = [f for f in os.listdir(images_dir) if f.endswith('.jpg')]
                    current_count = len(files)

                    if current_count != last_count:
                        last_count = current_count
                        last_change_ts = time.time()
                    else:
                        if time.time() - last_change_ts > 60:
                            try:
                                process.terminate()
                            except Exception:
                                pass
                            time.sleep(2)
                            try:
                                if process.poll() is None:
                                    process.kill()
                            except Exception:
                                pass
                            with VideoManager._lock:
                                if task_id in VideoManager._tasks:
                                    VideoManager._tasks[task_id]['error'] = 'ffmpeg 抽帧长时间无进展，可能视频已损坏/无法继续解码'
                            break
                    
                    if target_count_est > 0:
                        progress = int((current_count / target_count_est) * 100)
                        progress = max(0, min(99, progress))
                        
                        with VideoManager._lock:
                            if task_id in VideoManager._tasks:
                                VideoManager._tasks[task_id]['progress'] = progress
                except Exception:
                    pass
                time.sleep(1)
            
            if process.returncode != 0:
                tail = '\n'.join(list(stderr_tail)[-40:])
                if tail:
                    print(f"FFmpeg failed: {tail}")
                files = [f for f in os.listdir(images_dir) if f.endswith('.jpg')]
                extracted = len(files)
                if extracted > 0:
                    with VideoManager._lock:
                        if task_id in VideoManager._tasks and not VideoManager._tasks[task_id].get('error'):
                            VideoManager._tasks[task_id]['error'] = 'ffmpeg 退出异常，但已产出部分图片（视频可能损坏）'
                    return True, extracted
                return False, 0
            
            # Final count
            files = [f for f in os.listdir(images_dir) if f.endswith('.jpg')]
            return True, len(files)
            
        except Exception as e:
            print(f"FFmpeg extraction exception: {e}")
            return False, 0

    @staticmethod
    def _extraction_worker(project_path, video_name, task_id, strategy, value):
        video_path = os.path.join(project_path, 'videos', video_name)
        task_dir = VideoManager._get_task_dir(project_path, task_id)
        images_dir = os.path.join(task_dir, 'images')
        
        try:
            # 1. Get Video Info (Robust)
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0: fps = 25.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            
            # Fix for broken header
            if total_frames <= 0:
                ff_frames = VideoManager._get_video_info_ffprobe(video_path)
                if ff_frames > 0:
                    total_frames = ff_frames
                else:
                    # Fallback to some default if unknown, or let ffmpeg handle it
                    total_frames = 0 
            
            with VideoManager._lock:
                if task_id in VideoManager._tasks:
                    VideoManager._tasks[task_id]['total_frames'] = total_frames
                    VideoManager._write_task_meta(project_path, VideoManager._tasks[task_id])
            
            video_basename = os.path.splitext(video_name)[0]
            
            # 2. Try FFmpeg Extraction first (More robust for broken videos)
            success, extracted_count = VideoManager._extract_using_ffmpeg(
                project_path, video_path, images_dir, task_id, strategy, value, total_frames, fps, video_basename
            )
            
            if success and extracted_count > 0:
                with VideoManager._lock:
                    if task_id in VideoManager._tasks:
                        VideoManager._tasks[task_id]['status'] = 'completed'
                        VideoManager._tasks[task_id]['progress'] = 100
                        VideoManager._tasks[task_id]['extracted_count'] = extracted_count
                        VideoManager._tasks[task_id]['total_frames'] = total_frames
                        VideoManager._write_task_meta(project_path, VideoManager._tasks[task_id])
                return
            else:
                # 3. Fallback to OpenCV (Original Logic)
                print("FFmpeg failed or produced 0 images, falling back to OpenCV...")
                
                # Re-open cap for OpenCV logic
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    raise Exception("Failed to open video for OpenCV fallback")
                
                # Re-ensure fps/total_frames
                fps = cap.get(cv2.CAP_PROP_FPS)
                if fps <= 0: fps = 25.0
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total_frames <= 0:
                     # Simple manual scan fallback if needed, but we rely on previous scan result if possible
                     # Actually we already scanned it above and saved to total_frames var.
                     # But cap.get returns 0.
                     pass

            def robust_extract(cap_obj):
                nonlocal extracted_count
                interval_frames = 1
                if strategy == 'interval':
                    interval_frames = int(float(value) * fps)
                elif strategy == 'count':
                    count = int(value)
                    if count > 0 and total_frames > 0:
                        interval_frames = int(total_frames / count)
                    else:
                        interval_frames = int(fps)

                if interval_frames < 1:
                    interval_frames = 1

                frame_idx = 0
                consecutive_failures = 0
                while True:
                    try:
                        if frame_idx % interval_frames != 0:
                            ok = cap_obj.grab()
                            if ok:
                                consecutive_failures = 0
                                frame_idx += 1
                                continue

                            ret, frame = cap_obj.read()
                            if ret and frame is not None:
                                consecutive_failures = 0
                                frame_idx += 1
                                continue

                            consecutive_failures += 1
                            frame_idx += 1
                            if consecutive_failures >= 300:
                                break
                            continue
                        else:
                            ret, frame = cap_obj.read()
                            if not ret or frame is None:
                                consecutive_failures += 1
                                frame_idx += 1
                                if consecutive_failures >= 300:
                                    break
                                continue

                            frame_name = f"{video_basename}_f{frame_idx:06d}.jpg"
                            save_path = os.path.join(images_dir, frame_name)
                            cv2.imwrite(save_path, frame)
                            extracted_count += 1
                            consecutive_failures = 0

                            if total_frames > 0 and frame_idx % 100 == 0:
                                with VideoManager._lock:
                                    if task_id in VideoManager._tasks:
                                        VideoManager._tasks[task_id]['progress'] = int((frame_idx / total_frames) * 100)

                        frame_idx += 1
                    except Exception:
                        consecutive_failures += 1
                        frame_idx += 1
                        if consecutive_failures >= 300:
                            break

            use_robust = VideoManager._should_use_robust_mode(cap, fps, total_frames, strategy, value)

            if use_robust:
                robust_extract(cap)
            else:
                frame_indices = []
                if strategy == 'interval':
                    interval_frames = int(float(value) * fps)
                    if interval_frames < 1:
                        interval_frames = 1
                    frame_indices = range(0, total_frames, interval_frames)
                elif strategy == 'count':
                    count = int(value)
                    if count > total_frames:
                        count = total_frames
                    if count > 0:
                        frame_indices = np.linspace(0, total_frames - 1, count, dtype=int)
                        frame_indices = np.unique(frame_indices)

                total_to_extract = len(frame_indices)
                consecutive_failures = 0
                fallback_to_robust = False

                for idx, frame_idx in enumerate(frame_indices):
                    with VideoManager._lock:
                        if task_id in VideoManager._tasks:
                            VideoManager._tasks[task_id]['progress'] = int((idx / total_to_extract) * 100)

                    cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_idx))
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        frame_name = f"{video_basename}_f{frame_idx:06d}.jpg"
                        save_path = os.path.join(images_dir, frame_name)
                        cv2.imwrite(save_path, frame)
                        extracted_count += 1
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                        if idx < min(10, total_to_extract) and consecutive_failures >= 3:
                            fallback_to_robust = True
                            break

                if fallback_to_robust and extracted_count == 0:
                    cap.release()
                    cap = cv2.VideoCapture(video_path)
                    if cap.isOpened():
                        robust_extract(cap)
            
            cap.release()
            
            with VideoManager._lock:
                if task_id in VideoManager._tasks:
                    VideoManager._tasks[task_id]['status'] = 'completed'
                    VideoManager._tasks[task_id]['progress'] = 100
                    VideoManager._tasks[task_id]['extracted_count'] = extracted_count
                    VideoManager._tasks[task_id]['total_frames'] = total_frames
                    VideoManager._write_task_meta(project_path, VideoManager._tasks[task_id])
                    
        except Exception as e:
            with VideoManager._lock:
                if task_id in VideoManager._tasks:
                    VideoManager._tasks[task_id]['status'] = 'failed'
                    VideoManager._tasks[task_id]['error'] = str(e)
                    VideoManager._write_task_meta(project_path, VideoManager._tasks[task_id])

    @staticmethod
    def get_tasks(project_path):
        """获取任务列表"""
        tasks_by_id = {}

        temp_tasks_dir = os.path.join(project_path, 'temp_tasks')
        if os.path.exists(temp_tasks_dir):
            for tid in os.listdir(temp_tasks_dir):
                task_dir = os.path.join(temp_tasks_dir, tid)
                if not os.path.isdir(task_dir):
                    continue

                meta = VideoManager._read_task_meta(project_path, tid)
                if meta:
                    meta.setdefault('id', tid)
                    meta.setdefault('created_at', datetime.fromtimestamp(os.path.getmtime(task_dir)).strftime('%Y-%m-%d %H:%M:%S'))
                    meta.setdefault('status', 'completed')
                    meta.setdefault('extracted_count', 0)
                    meta.setdefault('total_frames', 0)
                    meta.setdefault('error', None)
                    images_dir = os.path.join(task_dir, 'images')
                    if meta.get('status') == 'running' and tid not in VideoManager._tasks and os.path.exists(images_dir):
                        try:
                            images = [f for f in os.listdir(images_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                            images.sort()
                            extracted_count = len(images)
                            if extracted_count > 0:
                                meta['status'] = 'completed'
                                meta['progress'] = 100
                                meta['extracted_count'] = extracted_count
                                VideoManager._write_task_meta(project_path, meta)
                        except Exception:
                            pass
                    meta.setdefault('progress', 100 if meta.get('status') == 'completed' else 0)
                    tasks_by_id[tid] = meta
                    continue

                images_dir = os.path.join(task_dir, 'images')
                images = []
                if os.path.exists(images_dir):
                    images = [f for f in os.listdir(images_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                images.sort()
                extracted_count = len(images)

                video_name = ''
                if images:
                    first = images[0]
                    video_name = first.split('_f', 1)[0] if '_f' in first else first

                tasks_by_id[tid] = {
                    'id': tid,
                    'video_name': video_name,
                    'status': 'completed',
                    'progress': 100,
                    'created_at': datetime.fromtimestamp(os.path.getmtime(task_dir)).strftime('%Y-%m-%d %H:%M:%S'),
                    'total_frames': 0,
                    'extracted_count': extracted_count,
                    'error': None,
                    'strategy': None,
                    'value': None
                }

        with VideoManager._lock:
            for tid, task in list(VideoManager._tasks.items()):
                expected_dir = VideoManager._get_task_dir(project_path, tid)
                if os.path.exists(expected_dir):
                    tasks_by_id[tid] = dict(task)

        tasks = list(tasks_by_id.values())
        return sorted(tasks, key=lambda x: x.get('created_at', ''), reverse=True)

    @staticmethod
    def get_task_images(project_path, task_id):
        """获取任务生成的图片列表"""
        task_dir = VideoManager._get_task_dir(project_path, task_id)
        images_dir = os.path.join(task_dir, 'images')
        
        if not os.path.exists(images_dir):
            return []
            
        images = []
        for f in os.listdir(images_dir):
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                images.append(f)
        return sorted(images)

    @staticmethod
    def add_frames_to_dataset(project_path, task_id, dataset_name, selected_images):
        """将选中的图片添加到数据集"""
        task_dir = VideoManager._get_task_dir(project_path, task_id)
        source_dir = os.path.join(task_dir, 'images')

        training_root = os.path.join(project_path, 'training', dataset_name)
        datasets_root = os.path.join(project_path, 'datasets', dataset_name)

        use_training = os.path.exists(training_root) or (not os.path.exists(datasets_root))
        if use_training:
            target_dir = os.path.join(training_root, 'train', 'images')
            labels_dir = os.path.join(training_root, 'train', 'labels')
        else:
            target_dir = os.path.join(datasets_root, 'images')
            labels_dir = os.path.join(datasets_root, 'labels')

        os.makedirs(target_dir, exist_ok=True)
        os.makedirs(labels_dir, exist_ok=True)
        
        # 如果未选择，默认导入所有图片
        if not selected_images:
            selected_images = [f for f in os.listdir(source_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        
        success_count = 0
        for img_name in selected_images:
            src = os.path.join(source_dir, img_name)
            dst = os.path.join(target_dir, img_name)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                success_count += 1
                
        return success_count

    @staticmethod
    def delete_task_images(project_path, task_id, selected_images):
        task_dir = VideoManager._get_task_dir(project_path, task_id)
        images_dir = os.path.join(task_dir, 'images')

        if not isinstance(selected_images, list) or len(selected_images) == 0:
            raise ValueError('Missing selected_images')

        project_real = os.path.realpath(project_path)
        images_dir_real = os.path.realpath(images_dir)
        images_dir_prefix = images_dir_real + os.sep
        if not (images_dir_real == project_real or images_dir_real.startswith(project_real + os.sep)):
            raise ValueError('Invalid project_path')

        deleted = []
        for img_name in selected_images:
            if not isinstance(img_name, str):
                continue
            safe_name = os.path.basename(img_name)
            if safe_name != img_name:
                continue
            img_path = os.path.join(images_dir, safe_name)
            img_real = os.path.realpath(img_path)
            if not img_real.startswith(images_dir_prefix):
                continue
            try:
                if os.path.exists(img_real):
                    os.remove(img_real)
                    deleted.append(safe_name)
            except Exception:
                pass

        remaining_count = None
        try:
            if os.path.isdir(images_dir_real):
                remaining = [f for f in os.listdir(images_dir_real) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                remaining_count = len(remaining)
        except Exception:
            remaining_count = None

        if remaining_count is not None:
            meta = VideoManager._read_task_meta(project_path, task_id)
            if meta is not None:
                meta['id'] = task_id
                meta['extracted_count'] = remaining_count
                VideoManager._write_task_meta(project_path, meta)

            with VideoManager._lock:
                if task_id in VideoManager._tasks:
                    VideoManager._tasks[task_id]['extracted_count'] = remaining_count

        return deleted

    @staticmethod
    def delete_task(project_path, task_id):
        """删除任务"""
        with VideoManager._lock:
            if task_id in VideoManager._tasks:
                del VideoManager._tasks[task_id]
        
        task_dir = VideoManager._get_task_dir(project_path, task_id)
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir)
