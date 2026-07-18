"""提供视频缩略图、帧探测与 ffmpeg 抽帧能力。"""

import logging
import subprocess
import threading

logger = logging.getLogger(__name__)


def generate_video_thumbnail(video_path, save_path):
    """截取视频首秒附近画面并生成缩略图。"""
    try:
        import cv2

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if frame_count > fps and fps > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps))
        ret, frame = cap.read()
        if ret:
            height, width = frame.shape[:2]
            target_height = 300
            scale = target_height / height
            target_width = int(width * scale)
            frame = cv2.resize(frame, (target_width, target_height))
            cv2.imwrite(save_path, frame)
        cap.release()
    except Exception as exc:
        logger.warning("生成缩略图失败 %s: %s", video_path, exc)


def should_use_robust_mode(cap, fps, total_frames):
    """探测随机跳帧是否可靠以决定抽帧模式。"""
    try:
        import cv2

        if fps <= 0 or total_frames <= 0:
            return True
        probe_indices = [0, int(total_frames * 0.5), max(0, total_frames - int(fps) - 1)]
        for frame_idx in probe_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if (not ret) or frame is None:
                return True
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        return False
    except Exception:
        return True


def get_video_frame_count_ffprobe(video_path):
    """使用 ffprobe 补充读取视频总帧数。"""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_packets",
            "-show_entries",
            "stream=nb_read_packets",
            "-of",
            "csv=p=0",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            try:
                return int(result.stdout.strip())
            except ValueError:
                pass
        return 0
    except Exception as exc:
        logger.warning("ffprobe 失败: %s", exc)
        return 0


def extract_frames_with_ffmpeg(video_path, images_dir, strategy, value, total_frames, fps, video_basename):
    """使用 ffmpeg 按策略批量输出抽帧图片。"""
    try:
        if strategy == "interval":
            if value <= 0:
                value = 1
            vf_filter = f"fps=1/{value}"
            duration = total_frames / fps if fps > 0 else 0
            target_count_est = int(duration / value)
        elif strategy == "count":
            target_count_est = int(value)
            duration = total_frames / fps if fps > 0 else 0
            if duration > 0:
                rate = value / duration
                vf_filter = f"fps={rate}"
            else:
                vf_filter = "fps=1"
        else:
            vf_filter = "fps=1"
            target_count_est = 0

        output_pattern = os.path.join(images_dir, f"{video_basename}_f%06d.jpg")
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-vf",
            vf_filter,
            "-q:v",
            "2",
            "-start_number",
            "0",
            output_pattern,
        ]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        def drain_stderr():
            """持续消费 ffmpeg stderr 以避免管道阻塞。"""
            try:
                if process.stderr is None:
                    return
                for _ in process.stderr:
                    pass
            except Exception:
                pass

        threading.Thread(target=drain_stderr, daemon=True).start()

        while process.poll() is None:
            try:
                files = [file_name for file_name in os.listdir(images_dir) if file_name.endswith(".jpg")]
                current_count = len(files)
                if target_count_est > 0:
                    _ = max(0, min(99, int((current_count / target_count_est) * 100)))
            except Exception:
                pass
            threading.Event().wait(1)

        if process.returncode != 0:
            files = [file_name for file_name in os.listdir(images_dir) if file_name.endswith(".jpg")]
            extracted = len(files)
            if extracted > 0:
                return True, extracted
            return False, 0

        files = [file_name for file_name in os.listdir(images_dir) if file_name.endswith(".jpg")]
        return True, len(files)
    except Exception as exc:
        logger.warning("ffmpeg 抽帧异常: %s", exc)
        return False, 0
