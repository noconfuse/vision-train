#!/usr/bin/env python3
import os
import sys
import random
import subprocess
from pathlib import Path
import cv2

BASE = "/media/paul/精神世界/视频"
OUT = "/home/paul/worksapce/vision-train/tmp/empty_subset"
TARGET = 20

def list_videos(d):
    exts = {".mp4",".avi",".mov",".mkv",".flv",".wmv"}
    vids = []
    for r,_,fs in os.walk(d):
        for f in fs:
            if os.path.splitext(f)[1].lower() in exts:
                vids.append(os.path.join(r,f))
    return vids

def duration(v):
    try:
        r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",v],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=5)
        return float(r.stdout.strip()) if r.returncode==0 and r.stdout.strip() else None
    except Exception:
        return None

def has_person(img):
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    rects,_ = hog.detectMultiScale(img,winStride=(8,8),padding=(8,8),scale=1.05)
    return len(rects)>0

def export_keyframes(v,pattern,timeout=20,keep_res=True,scale_width=640):
    cmd = [
        "ffmpeg","-nostdin","-hide_banner","-loglevel","error","-y",
        "-analyzeduration","0","-probesize","64",
        "-fflags","discardcorrupt","-err_detect","ignore_err",
        "-hwaccel","none","-i",v,
        "-vf", f"select=eq(pict_type\\,I){'' if keep_res else ',scale='+str(scale_width)+':-2'}",
        "-vsync","vfr","-f","image2","-q:v","3",pattern
    ]
    try:
        subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=True)
        return True
    except Exception:
        return False

def main():
    Path(OUT).mkdir(parents=True,exist_ok=True)
    selected = []
    if not os.path.isdir(BASE):
        print("no videos")
        return 1
    tops = [p for p in os.listdir(BASE) if os.path.isdir(os.path.join(BASE,p))]
    for idx in range(5):
        candidates = [p for p in tops if p.startswith(f"人工制样室{idx}") or p.startswith(f"人工制样室0{idx}")]
        room_dirs = [os.path.join(BASE,p) for p in candidates]
        room_videos = []
        for rd in room_dirs:
            room_videos.extend(list_videos(rd))
        if room_videos:
            selected.append(random.choice(room_videos))
    if not selected:
        print("no videos")
        return 1
    saved = 0
    per = max(1, (TARGET + len(selected) - 1) // len(selected))
    for v in selected:
        if saved>=TARGET:
            break
        name = Path(v).stem
        tmp_dir = Path(OUT)/f"tmp_{name}"
        tmp_dir.mkdir(parents=True,exist_ok=True)
        pattern = str(tmp_dir/"kf_%06d.jpg")
        ok = export_keyframes(v,pattern,timeout=25,keep_res=True,scale_width=640)
        if not ok:
            continue
        files = sorted(tmp_dir.glob("*.jpg"))
        for p in files:
            if saved>=TARGET:
                break
            try:
                if p.stat().st_size < 4096:
                    p.unlink(missing_ok=True)
                    continue
            except Exception:
                continue
            img = cv2.imread(str(p))
            if img is None:
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass
                continue
            if has_person(img):
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass
            else:
                outp = Path(OUT)/p.name
                cv2.imwrite(str(outp),img)
                saved += 1
        for p in tmp_dir.glob("*.jpg"):
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
        try:
            tmp_dir.rmdir()
        except Exception:
            pass
    print(f"saved {saved} to {OUT}")
    return 0

if __name__ == "__main__":
    sys.exit(main())