"""提供视频缩略图、帧探测与 ffmpeg 抽帧能力。"""

import logging
import os
import subprocess
import threading
from functools import lru_cache

from shared.utils.fs_utils import remove_file_silent

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def ffmpeg_executable():
    """跨平台解析 ffmpeg 可执行文件：优先 imageio-ffmpeg 自带二进制，回退宿主机 PATH。

    imageio-ffmpeg 按操作系统/架构自带静态 ffmpeg（含 libx264），pip 安装即用；
    未安装该包的环境才退回系统 PATH 上的 ffmpeg。结果进程内缓存一次。
    """
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        exe = get_ffmpeg_exe()
    except Exception as exc:
        logger.warning("imageio-ffmpeg 不可用，回退系统 ffmpeg: %s", exc)
        return "ffmpeg"
    return exe if exe and os.path.isfile(exe) else "ffmpeg"


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
            ffmpeg_executable(),
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


@lru_cache(maxsize=512)
def _probe_video_cached(video_path, mtime_ns, size):
    """按文件指纹缓存视频元信息，避免列表反复探测。读容器信息用 cv2 即可，无需 ffprobe。"""
    empty = {"codec": "", "width": 0, "height": 0, "duration": 0.0, "fps": 0.0}
    try:
        import cv2

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return empty
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC) or 0)
        codec = "".join(chr((fourcc >> 8 * i) & 0xFF) for i in range(4)).strip().lower()
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        cap.release()
        duration = (frames / fps) if fps > 0 and frames > 0 else 0.0
        return {
            "codec": codec,
            "width": width,
            "height": height,
            "duration": duration,
            "fps": fps,
        }
    except Exception as exc:
        logger.warning("探测视频元信息失败 %s: %s", video_path, exc)
        return empty


def probe_video_media(video_path):
    """返回视频编码、分辨率、时长与帧率。"""
    try:
        stat = os.stat(video_path)
    except OSError:
        return {"codec": "", "width": 0, "height": 0, "duration": 0.0, "fps": 0.0}
    return _probe_video_cached(video_path, stat.st_mtime_ns, stat.st_size)


def browser_can_play_video(codec, ext):
    """判断浏览器 video 标签能否直接解码该编码与容器组合。

    codec 来自 cv2 fourcc，H.264 在不同平台可能报作 h264 或 avc1，一并接受。
    """
    codec = str(codec or "").lower()
    ext = str(ext or "").lower()
    if ext in {".mp4", ".mov", ".m4v"} and codec in {"h264", "avc1"}:
        return True
    if ext == ".webm" and codec in {"vp8", "vp9"}:
        return True
    return False


def get_video_preview_path(videos_dir, video_name):
    """返回视频对应的 H.264 预览副本路径。"""
    stem = os.path.splitext(video_name)[0]
    return os.path.join(videos_dir, ".previews", f"{stem}.mp4")


def transcode_to_h264(
    src,
    dst,
    *,
    start=None,
    duration=None,
    scale_height=None,
    crf=20,
    progress_total=None,
    on_progress=None,
    stop_check=None,
):
    """把源视频（或其中一段）重编码为浏览器可播放的 H.264 MP4。

    返回 {ok, stopped, error}；取消或失败时清理半成品，不留可被误认成功的产物。
    """
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    # -ss/-t 置于 -i 之后做输出端裁剪：从首帧顺序解码再丢弃到起点。监控视频常带非零
    # start_time 且关键帧参考损坏，输入端 -ss 会产出空文件或错位片段，只有顺序解码可靠。
    cmd = [ffmpeg_executable(), "-y", "-i", src]
    if start is not None:
        cmd += ["-ss", f"{float(start):.3f}"]
    if duration is not None:
        cmd += ["-t", f"{float(duration):.3f}"]
    cmd += ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(int(crf)), "-pix_fmt", "yuv420p"]
    if scale_height:
        cmd += ["-vf", f"scale=-2:{int(scale_height)}"]
    cmd += ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", "-loglevel", "error", dst]

    err_lines = []
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except Exception as exc:
        remove_file_silent(dst)
        return {"ok": False, "stopped": False, "error": f"无法启动 ffmpeg: {exc}"}

    def drain_stderr():
        """收集 ffmpeg 错误尾部用于失败诊断。"""
        try:
            if process.stderr is None:
                return
            for line in process.stderr:
                err_lines.append(line.rstrip())
                if len(err_lines) > 50:
                    del err_lines[0]
        except Exception:
            pass

    threading.Thread(target=drain_stderr, daemon=True).start()

    stopped = False
    last_progress = -1
    try:
        for raw_line in process.stdout:
            line = raw_line.strip()
            if stop_check and stop_check():
                stopped = True
                process.terminate()
                break
            if line.startswith("out_time_us="):
                try:
                    seconds = int(line.split("=", 1)[1]) / 1_000_000
                except (TypeError, ValueError):
                    continue
                if progress_total and progress_total > 0 and on_progress:
                    percent = max(0, min(99, int((seconds / progress_total) * 100)))
                    if percent != last_progress:
                        last_progress = percent
                        on_progress(percent)
            elif line == "progress=end":
                break
    except Exception as exc:
        logger.warning("读取转码进度异常: %s", exc)
    finally:
        try:
            process.wait(timeout=10)
        except Exception:
            process.kill()

    if stopped:
        remove_file_silent(dst)
        return {"ok": False, "stopped": True, "error": "已取消"}
    if process.returncode != 0:
        remove_file_silent(dst)
        detail = "\n".join(err_lines[-8:]) or f"ffmpeg 退出码 {process.returncode}"
        return {"ok": False, "stopped": False, "error": detail}
    if not os.path.isfile(dst) or os.path.getsize(dst) == 0:
        remove_file_silent(dst)
        return {"ok": False, "stopped": False, "error": "转码未产出有效文件"}
    return {"ok": True, "stopped": False, "error": ""}
