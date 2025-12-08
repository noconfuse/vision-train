#!/usr/bin/env python3
import os
import sys
import argparse
from pathlib import Path
import math
import cv2
import numpy as np
import subprocess
import tempfile
import shutil
import time

def list_videos(root):
    exts={'.mp4','.avi','.mov','.mkv','.flv','.wmv'}
    for dirpath,_,filenames in os.walk(root):
        for f in filenames:
            if os.path.splitext(f)[1].lower() in exts:
                yield os.path.join(dirpath,f)

class PersonDetector:
    def __init__(self,method='opencv',conf=0.5,min_size=80,model_path=None):
        self.method=method
        self.conf=conf
        self.min_size=min_size
        self.yolo=None
        if method=='yolo':
            try:
                from ultralytics import YOLO
                mp=model_path
                if mp and not os.path.isabs(mp):
                    mp=str(Path(__file__).resolve().parent.parent/ mp)
                self.yolo=YOLO(mp) if mp else YOLO('yolov8n.pt')
            except Exception:
                self.method='opencv'
        if self.method=='opencv':
            self.hog=cv2.HOGDescriptor()
            self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def has_person(self,img):
        if self.method=='yolo' and self.yolo is not None:
            try:
                res=self.yolo(img,conf=self.conf,verbose=False)
                for r in res:
                    for b in np.array(r.boxes.cls):
                        if int(b)==0:
                            return True
                return False
            except Exception:
                pass
        if self.method=='opencv':
            rects,_=self.hog.detectMultiScale(img,winStride=(8,8),padding=(8,8),scale=1.05)
            for (x,y,w,h) in rects:
                if max(w,h)>=self.min_size:
                    return True
            return False
        return False

def sample_indices(frame_count,k):
    if k<=0 or frame_count<=0:
        return []
    step=max(1,frame_count//k)
    idxs=list(range(0,frame_count,step))
    if len(idxs)>k:
        idxs=idxs[:k]
    return idxs

def extract_empty_frames_from_video(video_path,out_dir,detector,per_video_target,scale_width=320,timeout_sec=8,extract_mode='keyframe',pre_frames_per_video=500,keep_res=False,jpeg_quality=6):
    name=Path(video_path).stem
    saved=0
    ffmpeg_path=shutil.which('ffmpeg')
    ffprobe_path=shutil.which('ffprobe')
    dur=None
    if ffprobe_path:
        try:
            r=subprocess.run([
                ffprobe_path,'-v','error','-show_entries','format=duration',
                '-of','default=noprint_wrappers=1:nokey=1',video_path
            ],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=20)
            dur=float(r.stdout.strip()) if r.returncode==0 and r.stdout.strip() else None
        except Exception:
            dur=None
    if ffmpeg_path:
        with tempfile.TemporaryDirectory() as tmpdir:
            pattern=str(Path(tmpdir)/f"{name}_first_%06d.jpg")
            vf=[]
            if not keep_res and scale_width and scale_width>0:
                vf.append(f'scale={scale_width}:-2')
            cmd=[
                ffmpeg_path,'-nostdin','-hide_banner','-loglevel','quiet','-y',
                '-analyzeduration','0','-probesize','64',
                '-fflags','discardcorrupt','-err_detect','ignore_err',
                '-hwaccel','auto','-i',video_path
            ]
            if vf:
                cmd+=['-vf',','.join(vf)]
            cmd+=['-q:v',str(jpeg_quality),'-frames:v',str(pre_frames_per_video), pattern]
            try:
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=max(timeout_sec,30), check=True)
            except Exception:
                pass
            for p in sorted(Path(tmpdir).glob('*.jpg')):
                if saved>=per_video_target:
                    break
                img=cv2.imread(str(p))
                if img is None:
                    continue
                if not detector.has_person(img):
                    out=str(Path(out_dir)/p.name)
                    cv2.imwrite(out,img)
                    saved+=1
    if saved<per_video_target:
        cap=cv2.VideoCapture(video_path)
        if cap.isOpened():
            n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            idxs=sample_indices(n,per_video_target*3)
            for i in idxs:
                if saved>=per_video_target:
                    break
                cap.set(cv2.CAP_PROP_POS_FRAMES,i)
                ok,frame=cap.read()
                if not ok or frame is None:
                    continue
                if not detector.has_person(frame):
                    fn=f"{name}_f{i:06d}.jpg"
                    cv2.imwrite(str(Path(out_dir)/fn),frame)
                    saved+=1
            cap.release()
    return saved

def distribute_target(num_videos,total):
    if num_videos<=0:
        return []
    base=total//num_videos
    rem=total%num_videos
    arr=[base]*num_videos
    for i in range(rem):
        arr[i]+=1
    return arr

def _dhash(img):
    g=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    g=cv2.resize(g,(9,8),interpolation=cv2.INTER_AREA)
    diff=g[:,1:]-g[:,:-1]
    bits=(diff>0).flatten()
    h=0
    for i,b in enumerate(bits):
        if b:
            h|=(1<<i)
    return h

def _dhash_path(p):
    img=cv2.imread(str(p))
    if img is None:
        return None
    return _dhash(img)

def _hamming(a,b):
    return (a^b).bit_count()

def dedupe_similar_images(dir_path,threshold=5,move=True):
    p=Path(dir_path)
    imgs=sorted(list(p.glob('*.jpg')))
    groups={}
    for x in imgs:
        k=x.stem.split('_')[0]
        groups.setdefault(k,[]).append(x)
    dups=[]
    kept=0
    for k,arr in groups.items():
        prev=None
        for x in arr:
            h=_dhash_path(x)
            if h is None:
                continue
            if prev is not None and _hamming(prev,h)<=threshold:
                dups.append(x)
            else:
                prev=h
                kept+=1
    backup=None
    if dups:
        backup=p/f"dedup_removed_{int(time.time())}"
        os.makedirs(backup,exist_ok=True)
        for x in dups:
            shutil.move(str(x),str(backup/x.name))
    return {'kept':kept,'removed':len(dups),'backup_dir':str(backup) if backup else None}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--video-root',default='/media/paul/精神世界/视频')
    p.add_argument('--output-dir',default='/home/paul/worksapce/vision-train/tmp/empty_frames')
    p.add_argument('--target-count',type=int,default=200)
    p.add_argument('--method',choices=['opencv','yolo'],default='opencv')
    p.add_argument('--conf',type=float,default=0.5)
    p.add_argument('--min-size',type=int,default=80)
    p.add_argument('--model-path',type=str,default='pretrained_models/yolo11n.pt')
    p.add_argument('--scale-width',type=int,default=320)
    p.add_argument('--timeout-sec',type=int,default=8)
    p.add_argument('--extract-mode',choices=['keyframe','timepoint','fps'],default='keyframe')
    p.add_argument('--pre-frames-per-video',type=int,default=500)
    p.add_argument('--keep-res',action='store_true')
    p.add_argument('--jpeg-quality',type=int,default=6)
    p.add_argument('--dedupe-dir',type=str,default=None)
    p.add_argument('--dhash-threshold',type=int,default=5)
    args=p.parse_args()
    if args.dedupe_dir:
        res=dedupe_similar_images(args.dedupe_dir,threshold=args.dhash_threshold,move=True)
        print(f"dedupe: removed {res['removed']} similar images, kept {res['kept']}, backup {res['backup_dir']}")
        return 0
    Path(args.output_dir).mkdir(parents=True,exist_ok=True)
    vids=list(list_videos(args.video_root))
    if not vids:
        print('no videos found')
        return 1
    det=PersonDetector(method=args.method,conf=args.conf,min_size=args.min_size,model_path=args.model_path)
    quotas=distribute_target(len(vids),args.target_count)
    total=0
    for i,v in enumerate(vids):
        saved=extract_empty_frames_from_video(v,args.output_dir,det,quotas[i],args.scale_width,args.timeout_sec,args.extract_mode,args.pre_frames_per_video,args.keep_res,args.jpeg_quality)
        total+=saved
    if total<args.target_count:
        remain=args.target_count-total
        for v in vids:
            if remain<=0:
                break
            add=min(remain,5)
            s=extract_empty_frames_from_video(v,args.output_dir,det,add,args.scale_width,args.timeout_sec,args.extract_mode,args.pre_frames_per_video,args.keep_res,args.jpeg_quality)
            remain-=s
            total+=s
    print(f'extracted {total} frames to {args.output_dir}')
    return 0

if __name__=='__main__':
    sys.exit(main())