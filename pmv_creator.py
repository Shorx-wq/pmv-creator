#!/usr/bin/env python3
"""
PMV Creator Pro v4 – Beat-Synced Music Video Generator
=======================================================
Polished dark UI · Layouts · Effects · Ken Burns

Dependencies:  pip install librosa numpy soundfile Pillow
Requires:      FFmpeg
"""

import os, sys, json, random, subprocess, tempfile, threading, time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import timedelta

VIDEO_EXTS = {".mp4",".avi",".mkv",".mov",".wmv",".flv",".webm",".m4v",".ts"}
IMAGE_EXTS = {".jpg",".jpeg",".png",".bmp",".webp",".tiff",".tif"}
AUDIO_EXTS = {".mp3",".wav",".ogg",".flac",".m4a",".aac"}
MEDIA_EXTS = VIDEO_EXTS | IMAGE_EXTS

LAYOUTS = {
    "single":       {"name":"Fullscreen",         "icon":"⬛","sources":1},
    "split_2":      {"name":"Split (2 Columns)",  "icon":"◫","sources":2},
    "split_3":      {"name":"Split (3 Columns)",  "icon":"☰","sources":3},
    "grid_2x2":     {"name":"Grid 2×2",           "icon":"⊞","sources":4},
    "top_bottom":   {"name":"Top / Bottom",        "icon":"⬒","sources":2},
    "pip":          {"name":"Picture in Picture",  "icon":"❐","sources":2},
    "center_wings": {"name":"Center + Wings",      "icon":"☷","sources":3},
    "letterbox_3":  {"name":"Letterbox Triple",    "icon":"▬","sources":3},
}

EFFECTS = {
    "none":"", "grayscale":"colorchannelmixer=.3:.4:.3:0:.3:.4:.3:0:.3:.4:.3",
    "sepia":"colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131",
    "high_contrast":"curves=preset=increase_contrast,eq=contrast=1.3:saturation=1.2",
    "vignette":"vignette=PI/4",
    "film_grain":"noise=alls=20:allf=t+u",
    "neon_glow":"eq=saturation=2.5:contrast=1.3,unsharp=5:5:1.5",
    "vintage":"curves=preset=vintage,noise=alls=12:allf=t",
    "cold_blue":"colorbalance=rs=-0.1:gs=-0.05:bs=0.2:rm=-0.1:gm=0:bm=0.15",
    "warm_orange":"colorbalance=rs=0.15:gs=0.05:bs=-0.1:rm=0.1:gm=0.03:bm=-0.05",
    "invert":"negate","mirror":"hflip",
    "blur_soft":"boxblur=2:1","sharpen":"unsharp=5:5:1.0:5:5:0.0",
    "emboss":"convolution='0 -1 0 -1 4 -1 0 -1 0:0 -1 0 -1 4 -1 0 -1 0:0 -1 0 -1 4 -1 0 -1 0:0 0 0 0 1 0 0 0 0'",
}


# ===========================================================================
# BACKEND (unchanged logic)
# ===========================================================================
class FFmpegBackend:
    def __init__(self, ffmpeg="ffmpeg", ffprobe="ffprobe"):
        self.ffmpeg = ffmpeg; self.ffprobe = ffprobe

    def _run(self, cmd):
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        return subprocess.run(cmd, capture_output=True, text=True, creationflags=flags)

    def validate(self):
        try:
            r = self._run([self.ffmpeg, "-version"])
            return (True, r.stdout.split("\n")[0]) if r.returncode == 0 else (False, "error")
        except FileNotFoundError:
            return False, "not found"

    def probe_video(self, path):
        cmd = [self.ffprobe,"-v","quiet","-print_format","json","-show_format","-show_streams",path]
        r = self._run(cmd)
        if r.returncode != 0 or not r.stdout.strip():
            raise RuntimeError(f"ffprobe failed: {Path(path).name}")
        data = json.loads(r.stdout); dur = float(data["format"].get("duration",0))
        w,h,fps = 1920,1080,30.0
        for s in data.get("streams",[]):
            if s.get("codec_type")=="video":
                w,h = int(s.get("width",1920)),int(s.get("height",1080))
                rfr = s.get("r_frame_rate","30/1"); parts = rfr.split("/")
                if len(parts)==2 and int(parts[1])>0: fps = round(int(parts[0])/int(parts[1]),2)
                break
        return {"type":"video","duration":dur,"width":w,"height":h,"fps":fps,"path":path,"name":Path(path).name}

    def probe_image(self, path):
        cmd = [self.ffprobe,"-v","quiet","-print_format","json","-show_streams",path]
        r = self._run(cmd); w,h = 1920,1080
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout)
            for s in data.get("streams",[]): w,h = int(s.get("width",1920)),int(s.get("height",1080)); break
        return {"type":"image","duration":999999,"width":w,"height":h,"fps":0,"path":path,"name":Path(path).name}

    def probe(self, path):
        return self.probe_image(path) if Path(path).suffix.lower() in IMAGE_EXTS else self.probe_video(path)

    def _vf_scale_pad(self, w, h):
        return f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"

    def _vf_ken_burns(self, kb, w, h, frames):
        if kb == "random": kb = random.choice(["zoom_in","zoom_out","pan_left","pan_right"])
        b = "scale=8000:-1,"
        if kb=="zoom_in": return b+f"zoompan=z='min(zoom+0.0015,1.2)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={{fps}}"
        if kb=="zoom_out": return b+f"zoompan=z='if(eq(on,1),1.2,max(zoom-0.0015,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={{fps}}"
        if kb=="pan_left": return b+f"zoompan=z='1.15':x='iw/2-(iw/zoom/2)-on*2':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={{fps}}"
        if kb=="pan_right": return b+f"zoompan=z='1.15':x='iw/2-(iw/zoom/2)+on*2':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={{fps}}"
        return None

    def _vf_transition(self, tr, dur, fd):
        if tr=="crossfade": return f"fade=t=in:st=0:d={fd},fade=t=out:st={max(0,dur-fd)}:d={fd}"
        if tr=="fade to black": return f"fade=t=in:st=0:d={fd}:color=black,fade=t=out:st={max(0,dur-fd)}:d={fd}:color=black"
        return None

    def make_segment(self, src, is_img, start, dur, out, w, h, fps,
                     kb="none", tr="hard cut", fd=.15, eff="none", flash=False):
        frames = max(int(dur*fps),2); vf = []
        if is_img:
            kb_vf = self._vf_ken_burns(kb,w,h,frames)
            vf.append(kb_vf.replace("{fps}",str(fps)) if kb_vf else self._vf_scale_pad(w,h))
        else:
            vf.append(self._vf_scale_pad(w,h))
        e = EFFECTS.get(eff,"")
        if e: vf.append(e)
        if flash: vf.append(f"fade=t=in:st=0:d={min(2,int(fps*0.06))/fps}:color=white")
        t = self._vf_transition(tr,dur,fd)
        if t: vf.append(t)
        if is_img:
            cmd = [self.ffmpeg,"-y","-loop","1","-i",src,"-vf",",".join(vf),"-t",f"{dur:.4f}",
                   "-r",str(fps),"-c:v","libx264","-preset","ultrafast","-crf","18",
                   "-pix_fmt","yuv420p","-an","-movflags","+faststart",out]
        else:
            cmd = [self.ffmpeg,"-y","-ss",f"{start:.4f}","-i",src,"-t",f"{dur:.4f}",
                   "-vf",",".join(vf),"-r",str(fps),"-c:v","libx264","-preset","ultrafast",
                   "-crf","18","-pix_fmt","yuv420p","-an","-movflags","+faststart",out]
        self._run(cmd)

    def compose_layout(self, sources, layout, dur, out, w, h, fps,
                       kb="none", tr="hard cut", fd=.15, eff="none", flash=False):
        tmp_d = os.path.dirname(out); parts = []
        sizes = self._sub_sizes(layout,w,h)
        for i,((src,is_img,start),(sw,sh)) in enumerate(zip(sources,sizes)):
            tp = os.path.join(tmp_d,f"_p{i}_{random.randint(0,99999)}.mp4")
            self.make_segment(src,is_img,start,dur,tp,sw,sh,fps,kb if is_img else "none","hard cut",0,"none",False)
            parts.append(tp)
        fc = self._layout_filter(layout,w,h,parts)
        post = []
        e = EFFECTS.get(eff,"")
        if e: post.append(e)
        if flash: post.append(f"fade=t=in:st=0:d={min(2,int(fps*0.06))/fps}:color=white")
        t = self._vf_transition(tr,dur,fd)
        if t: post.append(t)
        if post: fc += ","+",".join(post)
        fc += "[out]"
        cmd = [self.ffmpeg,"-y"]
        for tp in parts: cmd += ["-i",tp]
        cmd += ["-filter_complex",fc,"-map","[out]","-t",f"{dur:.4f}","-r",str(fps),
                "-c:v","libx264","-preset","ultrafast","-crf","18","-pix_fmt","yuv420p",
                "-an","-movflags","+faststart",out]
        self._run(cmd)
        for tp in parts:
            try: os.remove(tp)
            except: pass

    def _sub_sizes(self, ly, w, h):
        if ly=="split_2": return [(w//2,h)]*2
        if ly=="split_3": return [(w//3,h)]*3
        if ly=="grid_2x2": return [(w//2,h//2)]*4
        if ly=="top_bottom": return [(w,h//2)]*2
        if ly=="pip": return [(w,h),(w//4,h//4)]
        if ly=="center_wings": cw=int(w*.5); sw=(w-cw)//2; return [(sw,h),(cw,h),(sw,h)]
        if ly=="letterbox_3": return [(w//3,int(h*.6))]*3
        return [(w,h)]

    def _layout_filter(self, ly, w, h, parts):
        if ly=="split_2": return "[0:v][1:v]hstack=inputs=2"
        if ly=="split_3": return "[0:v][1:v][2:v]hstack=inputs=3"
        if ly=="grid_2x2": return "[0:v][1:v]hstack=inputs=2[top];[2:v][3:v]hstack=inputs=2[bot];[top][bot]vstack=inputs=2"
        if ly=="top_bottom": return "[0:v][1:v]vstack=inputs=2"
        if ly=="pip": return f"[0:v][1:v]overlay={w-w//4-20}:20"
        if ly=="center_wings": return "[0:v][1:v][2:v]hstack=inputs=3"
        if ly=="letterbox_3": pt=(h-int(h*.6))//2; return f"[0:v][1:v][2:v]hstack=inputs=3[row];[row]pad={w}:{h}:0:{pt}:color=black"
        return f"[0:v]scale={w}:{h}"

    def concat_mux(self, segs, audio, output, quality="medium"):
        pm = {"fast":("ultrafast","23"),"medium":("medium","20"),"high":("slow","18"),"ultra":("veryslow","16")}
        preset, crf = pm.get(quality,("medium","20"))
        cf = os.path.join(tempfile.gettempdir(),"pmv_concat.txt")
        with open(cf,"w",encoding="utf-8") as f:
            for s in segs: f.write(f"file '{s.replace(chr(92),'/').replace(chr(39),chr(39)+chr(92)+chr(39)+chr(39))}'\n")
        cmd = [self.ffmpeg,"-y","-f","concat","-safe","0","-i",cf,"-i",audio,
               "-c:v","libx264","-preset",preset,"-crf",crf,"-pix_fmt","yuv420p",
               "-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",output]
        r = self._run(cmd)
        try:
            os.remove(cf)
            for s in segs: os.remove(s)
        except: pass
        return r


def detect_beats(audio_path, sensitivity=1.0, subdivision=1):
    import librosa, numpy as np
    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    tempo, bf = librosa.beat.beat_track(y=y, sr=sr, tightness=100*sensitivity)
    bt = librosa.frames_to_time(bf, sr=sr).tolist()
    dur = librosa.get_duration(y=y, sr=sr)
    if not bt or bt[0] > 0.05: bt.insert(0, 0.0)
    if bt[-1] < dur - 0.1: bt.append(dur)
    if subdivision > 1:
        s = [bt[0]]
        for i in range(len(bt)-1):
            a,b = bt[i],bt[i+1]; step = (b-a)/subdivision
            for j in range(1,subdivision): s.append(a+step*j)
            s.append(b)
        bt = s
    bpm = float(tempo.item()) if isinstance(tempo,np.ndarray) and tempo.size==1 \
        else float(tempo.flat[0]) if isinstance(tempo,np.ndarray) else float(tempo)
    return bt, dur, bpm


def build_pmv(backend, media_paths, audio_path, output_path,
              sensitivity=1.0, subdivision=1, beat_skip=1,
              clip_mode="sequential", layout="single",
              transition="hard cut", fade_dur=0.15,
              ken_burns="none", effect="none", beat_flash=False,
              target_w=1920, target_h=1080, fps=30,
              quality="medium", seed=-1, progress_cb=None, log_cb=None):
    def log(m):
        if log_cb: log_cb(m)
    if seed >= 0: random.seed(seed); log(f"🎲 Seed: {seed}")
    t0 = time.time(); li = LAYOUTS.get(layout, LAYOUTS["single"]); ns = li["sources"]
    log("⏳ Detecting beats …")
    bt, adur, bpm = detect_beats(audio_path, sensitivity, subdivision)
    log(f"   ✔ {bpm:.0f} BPM")
    if beat_skip > 1:
        flt = [bt[0]]
        for i in range(beat_skip, len(bt), beat_skip): flt.append(bt[i])
        if flt[-1] < bt[-1]: flt.append(bt[-1])
        bt = flt
    ivs = [(bt[i],bt[i+1]) for i in range(len(bt)-1)]
    log(f"   ✔ {len(ivs)} segments | {li['name']} ({ns} src/seg)")
    log("⏳ Analyzing media …")
    infos, valid = [], []; nv=ni=0
    for mp in media_paths:
        try:
            info = backend.probe(mp); infos.append(info); valid.append(mp)
            if info["type"]=="image": ni+=1
            else: nv+=1
            tag = "🖼" if info["type"]=="image" else "🎬"
            log(f"   ✔ {tag} {info['name']}  {info['width']}x{info['height']}"
                +(f"  {info['duration']:.1f}s" if info["type"]=="video" else ""))
        except Exception as e: log(f"   ✖ {Path(mp).name}: {e}")
    if not valid: raise RuntimeError("No valid media!")
    log(f"   {nv} videos + {ni} images")
    n = len(ivs); tp = n*ns
    if clip_mode=="random": order = [random.randint(0,len(valid)-1) for _ in range(tp)]
    elif clip_mode=="shuffle":
        base = list(range(len(valid))); random.shuffle(base)
        order = (base*((tp//len(base))+1))[:tp]
    else: order = [i%len(valid) for i in range(tp)]
    log("⏳ Cutting segments …")
    pos = [0.0]*len(valid); td = tempfile.mkdtemp(prefix="pmv_"); sfs = []
    for idx,(st,en) in enumerate(ivs):
        sd = en-st
        if sd < 0.02: continue
        sp = os.path.join(td, f"seg_{idx:05d}.mp4")
        if ns == 1:
            ci = order[idx]; info = infos[ci]; ii = info["type"]=="image"
            p = 0
            if not ii:
                p = pos[ci]
                if p+sd > info["duration"]: p = max(0,random.uniform(0,max(.01,info["duration"]-sd)))
                pos[ci] = min(p+sd, info["duration"])
            backend.make_segment(valid[ci],ii,p,sd,sp,target_w,target_h,fps,ken_burns,transition,fade_dur,effect,beat_flash)
        else:
            srcs = []
            for s in range(ns):
                pi = idx*ns+s; ci = order[pi%len(order)]; info = infos[ci]; ii = info["type"]=="image"
                p = 0
                if not ii:
                    p = pos[ci]
                    if p+sd > info["duration"]: p = max(0,random.uniform(0,max(.01,info["duration"]-sd)))
                    pos[ci] = min(p+sd, info["duration"])
                srcs.append((valid[ci],ii,p))
            backend.compose_layout(srcs,layout,sd,sp,target_w,target_h,fps,ken_burns,transition,fade_dur,effect,beat_flash)
        sfs.append(sp)
        if progress_cb: progress_cb(int((idx+1)/n*75))
        if (idx+1)%25==0 or idx==n-1: log(f"   … {idx+1}/{n}")
    log("⏳ Assembling …")
    r = backend.concat_mux(sfs, audio_path, output_path, quality)
    if r.returncode != 0: log(f"   ⚠ {r.stderr[-300:]}")
    try: os.rmdir(td)
    except: pass
    el = time.time()-t0; sz = os.path.getsize(output_path)/(1024*1024)
    if progress_cb: progress_cb(100)
    log(f"✅ Done in {timedelta(seconds=int(el))} | {sz:.1f} MB → {output_path}")


def build_splitscreen(backend, base_pmv, center_media, output_path,
                       audio_mode="base", custom_audio=None,
                       target_w=1920, target_h=1080, fps=30, quality="medium",
                       progress_cb=None, log_cb=None):
    def log(m):
        if log_cb: log_cb(m)
    t0 = time.time()
    col_w = target_w // 3
    col_h = target_h
    log("⏳ Analyzing base PMV …")
    base_info = backend.probe_video(base_pmv)
    duration = base_info["duration"]
    log(f"   ✔ Base: {base_info['name']}  {duration:.1f}s")
    log("⏳ Analyzing center media …")
    is_img = Path(center_media).suffix.lower() in IMAGE_EXTS
    c_info = backend.probe_image(center_media) if is_img else backend.probe_video(center_media)
    if not is_img: duration = min(duration, c_info["duration"])
    log(f"   ✔ Center: {c_info['name']}")
    if progress_cb: progress_cb(10)
    td = tempfile.mkdtemp(prefix="pmv_ss_")
    sp = (f"scale={col_w}:{col_h}:force_original_aspect_ratio=decrease,"
          f"pad={col_w}:{col_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1")
    def _col(src, out, extra="", loop=False):
        vf = sp + (f",{extra}" if extra else "")
        cmd = [backend.ffmpeg, "-y"]
        if loop: cmd += ["-loop", "1"]
        cmd += ["-i", src, "-vf", vf, "-t", f"{duration:.4f}", "-r", str(fps),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", out]
        backend._run(cmd)
    log("⏳ Left column …")
    left = os.path.join(td, "col_L.mp4"); _col(base_pmv, left)
    if progress_cb: progress_cb(30)
    log("⏳ Center column …")
    center = os.path.join(td, "col_C.mp4"); _col(center_media, center, loop=is_img)
    if progress_cb: progress_cb(55)
    log("⏳ Right column (mirrored) …")
    right = os.path.join(td, "col_R.mp4"); _col(base_pmv, right, extra="hflip")
    if progress_cb: progress_cb(72)
    log("⏳ Combining columns …")
    combined = os.path.join(td, "combined.mp4")
    backend._run([backend.ffmpeg, "-y", "-i", left, "-i", center, "-i", right,
                  "-filter_complex", "[0:v][1:v][2:v]hstack=inputs=3[out]",
                  "-map", "[out]", "-t", f"{duration:.4f}", "-r", str(fps),
                  "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
                  "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", combined])
    if progress_cb: progress_cb(85)
    log("⏳ Muxing audio …")
    pm = {"fast":("ultrafast","23"),"medium":("medium","20"),"high":("slow","18"),"ultra":("veryslow","16")}
    preset, crf = pm.get(quality, ("medium","20"))
    asrc = base_pmv if audio_mode == "base" else custom_audio
    r = backend._run([backend.ffmpeg, "-y", "-i", combined, "-i", asrc,
                      "-c:v", "libx264", "-preset", preset, "-crf", crf,
                      "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                      "-shortest", "-movflags", "+faststart", output_path])
    if r.returncode != 0: log(f"   ⚠ {r.stderr[-300:]}")
    for f in [left, center, right, combined]:
        try: os.remove(f)
        except: pass
    try: os.rmdir(td)
    except: pass
    el = time.time()-t0; sz = os.path.getsize(output_path)/(1024*1024)
    if progress_cb: progress_cb(100)
    log(f"✅ Done in {timedelta(seconds=int(el))} | {sz:.1f} MB → {output_path}")


# ===========================================================================
# CUSTOM WIDGETS
# ===========================================================================
class HoverButton(tk.Button):
    """Flat button with hover color change."""
    def __init__(self, parent, text="", command=None, width=None, height=None,
                 bg="#1e1e1e", fg="#e0e0e0", hover_bg="#2a2a2a",
                 active_bg="#e94560", font=("Segoe UI", 9), **kw):
        super().__init__(parent, text=text, command=command,
                         bg=bg, fg=fg, activebackground=active_bg,
                         activeforeground=fg, font=font,
                         relief="flat", bd=0, padx=12, pady=6,
                         cursor="hand2", highlightthickness=0, **kw)
        self._bg = bg; self._fg = fg; self._hover = hover_bg
        self._enabled = True
        self.bind("<Enter>", lambda e: self.config(bg=self._hover) if self._enabled else None)
        self.bind("<Leave>", lambda e: self.config(bg=self._bg) if self._enabled else None)

    def set_enabled(self, val):
        self._enabled = val
        self.config(state="normal" if val else "disabled",
                    bg=self._bg, fg=self._fg if val else "#555")


class SectionHeader(tk.Frame):
    """Section header with accent bar."""
    def __init__(self, parent, text, accent="#e94560", bg="#161616", **kw):
        super().__init__(parent, bg=bg, **kw)
        bar = tk.Frame(self, bg=accent, width=3, height=18)
        bar.pack(side="left", padx=(0, 10), pady=2)
        bar.pack_propagate(False)
        tk.Label(self, text=text, font=("Segoe UI", 11, "bold"),
                 bg=bg, fg="#ffffff").pack(side="left")


class StatusDot(tk.Frame):
    """Tiny colored status indicator."""
    def __init__(self, parent, color="#555", size=8, **kw):
        bg = parent.cget("bg") if hasattr(parent, "cget") else "#161616"
        super().__init__(parent, bg=bg, width=size+4, height=size+4, **kw)
        self.pack_propagate(False)
        self._dot = tk.Frame(self, bg=color, width=size, height=size)
        self._dot.place(relx=0.5, rely=0.5, anchor="center",
                        width=size, height=size)

    def set_color(self, c):
        self._dot.config(bg=c)


# ===========================================================================
# GUI
# ===========================================================================
class PMVCreatorApp(tk.Tk):
    C = {
        "bg":"#0c0c0c", "surface":"#141414", "card":"#1a1a1a",
        "card2":"#202020", "border":"#2a2a2a", "border_light":"#333333",
        "text":"#e8e8e8", "text2":"#b0b0b0", "muted":"#606060",
        "accent":"#e94560", "accent_h":"#ff6b81", "accent_dim":"#3d1520",
        "green":"#34d399", "green_dim":"#0d3d2e",
        "blue":"#3b82f6", "cyan":"#22d3ee",
        "yellow":"#facc15", "trough":"#1a2332",
    }

    def __init__(self):
        super().__init__()
        self.title("PMV Creator Pro")
        self.geometry("1040x900")
        self.configure(bg=self.C["bg"])
        self.resizable(True, True)
        self.minsize(820, 680)
        self.media_paths = []; self.audio_path = ""
        self.ffmpeg_backend = None; self.rendering = False
        self._apply_styles()
        self._build_ui()
        self._auto_detect_ffmpeg()

    def _apply_styles(self):
        C = self.C; s = ttk.Style(self); s.theme_use("clam")
        s.configure(".", background=C["surface"], foreground=C["text"],
                    font=("Segoe UI",10), borderwidth=0)
        s.configure("BG.TFrame", background=C["bg"])
        s.configure("Card.TFrame", background=C["card"])
        s.configure("TFrame", background=C["surface"])
        for n, bg, fg, f in [
            ("H2.TLabel",C["card"],C["text2"],("Segoe UI",10)),
            ("Info.TLabel",C["card"],C["muted"],("Segoe UI",9)),
            ("Status.TLabel",C["bg"],C["muted"],("Segoe UI",9)),
        ]:
            s.configure(n, background=bg, foreground=fg, font=f)
        s.configure("TCombobox", fieldbackground=C["card2"], background=C["card2"],
                    foreground=C["text"], arrowcolor=C["muted"], bordercolor=C["border"],
                    selectbackground=C["accent"], selectforeground="#fff", padding=6)
        s.map("TCombobox", fieldbackground=[("readonly",C["card2"])],
              selectbackground=[("readonly",C["card2"])],
              selectforeground=[("readonly",C["text"])],
              bordercolor=[("focus",C["accent"])])
        self.option_add("*TCombobox*Listbox.background", C["card2"])
        self.option_add("*TCombobox*Listbox.foreground", C["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", C["accent"])
        self.option_add("*TCombobox*Listbox.selectForeground", "#fff")
        s.configure("Horizontal.TScale", background=C["card"], troughcolor=C["trough"],
                    sliderthickness=16, borderwidth=0)
        s.map("Horizontal.TScale", background=[("active",C["accent"])])
        s.configure("TEntry", fieldbackground=C["card2"], foreground=C["text"],
                    insertcolor=C["text"], bordercolor=C["border"], padding=6)
        s.map("TEntry", bordercolor=[("focus",C["accent"])])
        s.configure("TCheckbutton", background=C["card"], foreground=C["text"],
                    font=("Segoe UI",10), focuscolor=C["card"])
        s.map("TCheckbutton", background=[("active",C["card"])])
        s.configure("TRadiobutton", background=C["card"], foreground=C["text"],
                    font=("Segoe UI",10), focuscolor=C["card"])
        s.map("TRadiobutton", background=[("active",C["card"])])
        s.configure("TNotebook", background=C["bg"], borderwidth=0, tabmargins=[0,0,0,0])
        s.configure("TNotebook.Tab", background=C["card"], foreground=C["muted"],
                    padding=(18,8), font=("Segoe UI",9,"bold"))
        s.map("TNotebook.Tab", background=[("selected",C["accent_dim"])],
              foreground=[("selected","#fff")])

    def _build_ui(self):
        C = self.C
        main = tk.Frame(self, bg=C["bg"])
        main.pack(fill="both", expand=True, padx=24, pady=18)

        # Header
        hdr = tk.Frame(main, bg=C["bg"]); hdr.pack(fill="x", pady=(0,16))
        tk.Label(hdr, text="PMV Creator", font=("Segoe UI",26,"bold"),
                 bg=C["bg"], fg="#ffffff").pack(side="left")
        tk.Label(hdr, text="PRO", font=("Segoe UI",12,"bold"),
                 bg=C["bg"], fg=C["accent"]).pack(side="left", padx=(6,0), anchor="s", pady=(0,6))
        self.status_dot = StatusDot(hdr, color=C["muted"], size=8)
        self.status_dot.pack(side="right", padx=(0,8), anchor="s", pady=(0,8))
        self.status_label = tk.Label(hdr, text="Ready", font=("Segoe UI",9),
                                     bg=C["bg"], fg=C["muted"])
        self.status_label.pack(side="right", anchor="s", pady=(0,6))

        # Tabs
        nb = ttk.Notebook(main); nb.pack(fill="both", expand=True)
        tabs = {}
        for tid, label in [("media","  📹 Media  "),("layout","  🎨 Layout & FX  "),
                           ("beats","  🥁 Beats  "),("output","  📤 Output  "),
                           ("ffmpeg","  ⚡ FFmpeg  "),("splitscreen","  🖥 Splitscreen  ")]:
            tabs[tid] = tk.Frame(nb, bg=C["bg"])
            nb.add(tabs[tid], text=label)

        self._build_media_tab(tabs["media"])
        self._build_layout_tab(tabs["layout"])
        self._build_beats_tab(tabs["beats"])
        self._build_output_tab(tabs["output"])
        self._build_ffmpeg_tab(tabs["ffmpeg"])
        self._build_splitscreen_tab(tabs["splitscreen"])
        self._try_enable_dnd()

        # Bottom bar
        bot = tk.Frame(main, bg=C["bg"]); bot.pack(fill="x", pady=(14,0))
        self.render_btn = HoverButton(bot, text="🚀  Render PMV", width=160, height=40,
                                       bg=C["accent"], fg="#ffffff", hover_bg=C["accent_h"],
                                       active_bg="#c0392b", font=("Segoe UI",11,"bold"),
                                       command=self._start_render)
        self.render_btn.pack(side="left")
        self.cancel_btn = HoverButton(bot, text="Cancel", width=80, height=40,
                                       bg=C["card"], fg=C["muted"], hover_bg=C["card2"],
                                       active_bg=C["border"], font=("Segoe UI",9),
                                       command=self._cancel)
        self.cancel_btn.pack(side="left", padx=(10,0))
        self.cancel_btn.set_enabled(False)

        pf = tk.Frame(bot, bg=C["bg"])
        pf.pack(side="left", fill="x", expand=True, padx=20)
        self.progress = ttk.Progressbar(pf, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", expand=True, pady=8)

    # ── Card helper ─────────────────────────────────────────────────
    def _card(self, parent, title, pady=(0,10)):
        C = self.C
        wrapper = tk.Frame(parent, bg=C["bg"])
        wrapper.pack(fill="x", padx=12, pady=pady)
        SectionHeader(wrapper, title, accent=C["accent"], bg=C["bg"]).pack(
            fill="x", pady=(8,8))
        card = tk.Frame(wrapper, bg=C["card"], highlightbackground=C["border"],
                        highlightthickness=1, bd=0)
        card.pack(fill="x")
        inner = tk.Frame(card, bg=C["card"])
        inner.pack(fill="both", expand=True, padx=16, pady=14)
        return inner

    def _card_expand(self, parent, title, pady=(0,10)):
        C = self.C
        wrapper = tk.Frame(parent, bg=C["bg"])
        wrapper.pack(fill="both", expand=True, padx=12, pady=pady)
        SectionHeader(wrapper, title, accent=C["accent"], bg=C["bg"]).pack(
            fill="x", pady=(8,8))
        card = tk.Frame(wrapper, bg=C["card"], highlightbackground=C["border"],
                        highlightthickness=1, bd=0)
        card.pack(fill="both", expand=True)
        inner = tk.Frame(card, bg=C["card"])
        inner.pack(fill="both", expand=True, padx=16, pady=14)
        return inner

    def _row(self, parent, label, row):
        C = self.C
        tk.Label(parent, text=label, font=("Segoe UI",10), bg=C["card"],
                 fg=C["text2"]).grid(row=row, column=0, sticky="w", padx=(0,16), pady=7)

    # ── Tab: Media ──────────────────────────────────────────────────
    def _build_media_tab(self, p):
        C = self.C
        inner = self._card_expand(p, "Media Files", (0,6))

        br = tk.Frame(inner, bg=C["card"]); br.pack(fill="x", pady=(0,10))
        for txt, cmd in [("＋ Add Files",self._add_media),("📂 Folder",self._add_folder),
                         ("✕ Remove",self._remove_sel),("🗑 Clear",self._clear_all)]:
            HoverButton(br, text=txt, width=100, height=30, bg=C["card2"],
                       fg=C["text"], hover_bg=C["border"], font=("Segoe UI",9),
                       command=cmd).pack(side="left", padx=(0,6))

        mr = tk.Frame(inner, bg=C["card"]); mr.pack(fill="x", pady=(0,6))
        for txt, cmd in [("▲",self._move_up),("▼",self._move_down),("🔀",self._shuffle)]:
            HoverButton(mr, text=txt, width=36, height=28, bg=C["card2"],
                       fg=C["text"], hover_bg=C["border"], font=("Segoe UI",9),
                       command=cmd).pack(side="left", padx=(0,4))
        self.count_lbl = tk.Label(mr, text="0 files", font=("Segoe UI",9),
                                  bg=C["card"], fg=C["muted"])
        self.count_lbl.pack(side="right")

        self.media_list = tk.Listbox(
            inner, selectmode="extended", bg=C["card2"], fg=C["text"],
            font=("Consolas",10), relief="flat", bd=0, highlightthickness=0,
            selectbackground=C["accent"], selectforeground="#fff", activestyle="none")
        self.media_list.pack(fill="both", expand=True, pady=(0,4))

        # Audio
        ai = self._card(p, "Audio Track", (0,6))
        ar = tk.Frame(ai, bg=C["card"]); ar.pack(fill="x")
        HoverButton(ar, text="Select Audio", width=120, height=32, bg=C["card2"],
                   fg=C["text"], hover_bg=C["border"], font=("Segoe UI",9),
                   command=self._select_audio).pack(side="left")
        self.audio_lbl = tk.Label(ar, text="  – none –", font=("Segoe UI",10),
                                  bg=C["card"], fg=C["muted"])
        self.audio_lbl.pack(side="left", padx=14)
        self.audio_dur = tk.Label(ar, text="", font=("Consolas",9),
                                  bg=C["card"], fg=C["cyan"])
        self.audio_dur.pack(side="right")

        # Log
        li = self._card_expand(p, "Output Log", (0,4))
        lb = tk.Frame(li, bg=C["card"]); lb.pack(fill="x", pady=(0,6))
        HoverButton(lb, text="Clear", width=60, height=24, bg=C["card2"],
                   fg=C["muted"], hover_bg=C["border"], font=("Segoe UI",8),
                   command=self._clear_log).pack(side="right")
        self.log_text = tk.Text(li, height=6, bg="#090909", fg=C["green"],
                                insertbackground=C["green"], font=("JetBrains Mono",9),
                                relief="flat", bd=0, wrap="word", highlightthickness=0,
                                padx=10, pady=8)
        self.log_text.pack(fill="both", expand=True)

    # ── Tab: Layout & Effects ───────────────────────────────────────
    def _build_layout_tab(self, p):
        C = self.C
        g = self._card(p, "Layout Template", (0,6))
        g.columnconfigure(1, weight=1)
        self._row(g, "Template", 0)
        self.layout_var = tk.StringVar(value="single")
        ttk.Combobox(g, textvariable=self.layout_var, values=list(LAYOUTS.keys()),
                     state="readonly", width=22).grid(row=0, column=1, sticky="w", pady=7)
        self.layout_desc = tk.Label(g, text="⬛  Fullscreen – 1 source per segment",
                                    font=("Segoe UI",9), bg=C["card"], fg=C["muted"])
        self.layout_desc.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0,4))
        self.layout_var.trace_add("write", self._on_layout)

        g2 = self._card(p, "Visual Effects", (0,6))
        g2.columnconfigure(1, weight=1)
        self._row(g2, "Color Effect", 0)
        self.effect_var = tk.StringVar(value="none")
        ttk.Combobox(g2, textvariable=self.effect_var, values=list(EFFECTS.keys()),
                     state="readonly", width=22).grid(row=0, column=1, sticky="w", pady=7)
        self.flash_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(g2, text="  ⚡ Beat Flash (white flash on every cut)",
                        variable=self.flash_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4,0))

        g3 = self._card(p, "Transitions", (0,6))
        g3.columnconfigure(1, weight=1)
        self._row(g3, "Type", 0)
        self.transition_var = tk.StringVar(value="hard cut")
        ttk.Combobox(g3, textvariable=self.transition_var,
                     values=["hard cut","crossfade","fade to black"],
                     state="readonly", width=22).grid(row=0, column=1, sticky="w", pady=7)
        self._row(g3, "Fade Duration", 1)
        self.fade_var = tk.DoubleVar(value=0.15)
        ttk.Scale(g3, from_=0.05, to=0.5, variable=self.fade_var,
                  orient="horizontal").grid(row=1, column=1, sticky="we", pady=7)

        g4 = self._card(p, "Image Motion (Ken Burns)", (0,6))
        g4.columnconfigure(1, weight=1)
        self._row(g4, "Effect", 0)
        self.kb_var = tk.StringVar(value="random")
        ttk.Combobox(g4, textvariable=self.kb_var,
                     values=["none","zoom_in","zoom_out","pan_left","pan_right","random"],
                     state="readonly", width=22).grid(row=0, column=1, sticky="w", pady=7)

    def _on_layout(self, *a):
        k = self.layout_var.get(); info = LAYOUTS.get(k, LAYOUTS["single"])
        self.layout_desc.config(text=f"{info['icon']}  {info['name']} – {info['sources']} source{'s' if info['sources']>1 else ''}/segment")

    # ── Tab: Beats ──────────────────────────────────────────────────
    def _build_beats_tab(self, p):
        C = self.C
        g = self._card(p, "Beat Detection", (0,6))
        g.columnconfigure(1, weight=1)
        self._row(g, "Sensitivity", 0)
        self.sens_var = tk.DoubleVar(value=1.0)
        ttk.Scale(g, from_=0.3, to=3.0, variable=self.sens_var,
                  orient="horizontal").grid(row=0, column=1, sticky="we", pady=7)
        self._row(g, "Subdivision", 1)
        self.subdiv_var = tk.StringVar(value="1 (every beat)")
        ttk.Combobox(g, textvariable=self.subdiv_var,
                     values=["1 (every beat)","2 (half beats)","4 (quarter beats)"],
                     state="readonly", width=22).grid(row=1, column=1, sticky="w", pady=7)
        self._row(g, "Every Nth Beat", 2)
        self.skip_var = tk.StringVar(value="1")
        ttk.Combobox(g, textvariable=self.skip_var, values=["1","2","4","8"],
                     state="readonly", width=22).grid(row=2, column=1, sticky="w", pady=7)

        g2 = self._card(p, "Clip Order", (0,6))
        g2.columnconfigure(1, weight=1)
        self._row(g2, "Mode", 0)
        self.clip_mode_var = tk.StringVar(value="sequential")
        ttk.Combobox(g2, textvariable=self.clip_mode_var,
                     values=["sequential","random","shuffle"],
                     state="readonly", width=22).grid(row=0, column=1, sticky="w", pady=7)
        self._row(g2, "Random Seed", 1)
        self.seed_var = tk.StringVar(value="-1")
        ttk.Entry(g2, textvariable=self.seed_var, width=12).grid(
            row=1, column=1, sticky="w", pady=7)
        tk.Label(g2, text="(-1 = random)", font=("Segoe UI",9),
                 bg=C["card"], fg=C["muted"]).grid(row=1, column=2, sticky="w", padx=8)

    # ── Tab: Output ─────────────────────────────────────────────────
    def _build_output_tab(self, p):
        g = self._card(p, "Output Settings", (0,6))
        g.columnconfigure(1, weight=1)
        for row, lbl, vn, vals, default in [
            (0,"Resolution","resolution_var",["3840x2160","2560x1440","1920x1080","1280x720","854x480"],"1920x1080"),
            (1,"FPS","fps_var",["24","30","60"],"30"),
            (2,"Quality","quality_var",["fast","medium","high","ultra"],"medium"),
        ]:
            self._row(g, lbl, row)
            sv = tk.StringVar(value=default); setattr(self, vn, sv)
            ttk.Combobox(g, textvariable=sv, values=vals, state="readonly",
                         width=22).grid(row=row, column=1, sticky="w", pady=7)

    # ── Tab: FFmpeg ─────────────────────────────────────────────────
    def _build_ffmpeg_tab(self, p):
        C = self.C
        g = self._card(p, "FFmpeg Configuration", (0,6))
        tk.Label(g, text="Path to ffmpeg binary or bin folder:",
                 font=("Segoe UI",10), bg=C["card"], fg=C["text2"]).pack(anchor="w", pady=(0,8))
        pr = tk.Frame(g, bg=C["card"]); pr.pack(fill="x", pady=(0,10))
        self.ff_path_var = tk.StringVar(value="")
        ent = ttk.Entry(pr, textvariable=self.ff_path_var, font=("JetBrains Mono",10))
        ent.pack(side="left", fill="x", expand=True)
        HoverButton(pr, text="Browse", width=80, height=32, bg=C["card2"],
                   fg=C["text"], hover_bg=C["border"], font=("Segoe UI",9),
                   command=self._browse_ff).pack(side="left", padx=(8,0))
        br = tk.Frame(g, bg=C["card"]); br.pack(fill="x", pady=(0,10))
        HoverButton(br, text="✔ Validate", width=100, height=32, bg=C["card2"],
                   fg=C["text"], hover_bg=C["border"], font=("Segoe UI",9),
                   command=self._validate_ff).pack(side="left")
        HoverButton(br, text="Auto-Detect", width=110, height=32, bg=C["card2"],
                   fg=C["text"], hover_bg=C["border"], font=("Segoe UI",9),
                   command=self._auto_detect_ffmpeg).pack(side="left", padx=(8,0))
        sf = tk.Frame(g, bg=C["card"]); sf.pack(fill="x")
        self.ff_dot = StatusDot(sf, color=C["muted"]); self.ff_dot.pack(side="left", padx=(0,8))
        self.ff_status = tk.Label(sf, text="Not configured", font=("Segoe UI",9),
                                  bg=C["card"], fg=C["muted"])
        self.ff_status.pack(side="left")

    # ── FFmpeg ──────────────────────────────────────────────────────
    def _resolve_ff(self, s):
        p = Path(s.strip())
        if p.is_file() and p.name.lower().startswith("ffmpeg"):
            return str(p), str(p.parent / p.name.replace("ffmpeg","ffprobe"))
        if p.is_dir():
            for n in ["ffmpeg.exe","ffmpeg"]:
                if (p/n).is_file(): return str(p/n), str(p/n.replace("ffmpeg","ffprobe"))
        return s, "ffprobe"

    def _browse_ff(self):
        d = filedialog.askdirectory(title="FFmpeg bin"); 
        if d: self.ff_path_var.set(d); self._validate_ff()

    def _validate_ff(self):
        C = self.C; raw = self.ff_path_var.get().strip() or "ffmpeg"
        ff, fp = self._resolve_ff(raw)
        self._log(f"   ffmpeg:  {ff}\n   ffprobe: {fp}")
        b = FFmpegBackend(ff, fp); ok, ver = b.validate()
        if ok:
            self.ffmpeg_backend = b
            self.ff_status.config(text=ver, fg=C["green"]); self.ff_dot.set_color(C["green"])
            self.status_dot.set_color(C["green"]); self._log(f"✔ {ver}")
        else:
            self.ff_status.config(text=ver, fg=C["accent"]); self.ff_dot.set_color(C["accent"])

    def _auto_detect_ffmpeg(self):
        C = self.C
        cands = ["ffmpeg",r"C:\ffmpeg\bin\ffmpeg.exe",r"C:\ffmpeg\ffmpeg.exe",
                 r"C:\Program Files\ffmpeg\bin\ffmpeg.exe","/usr/bin/ffmpeg","/usr/local/bin/ffmpeg"]
        if sys.platform == "win32":
            for d in ["C:","D:","G:"]:
                bp = Path(d+"\\ffmpeg")
                if bp.exists():
                    for pp in bp.rglob("ffmpeg.exe"):
                        if "bin" in str(pp): cands.insert(0, str(pp)); break
        for c in cands:
            cp = Path(c); fp = str(cp.parent/cp.name.replace("ffmpeg","ffprobe")) if c!="ffmpeg" else "ffprobe"
            b = FFmpegBackend(c, fp); ok, ver = b.validate()
            if ok:
                self.ffmpeg_backend = b
                self.ff_path_var.set(str(Path(c).parent) if c!="ffmpeg" else "(PATH)")
                self.ff_status.config(text=ver, fg=C["green"]); self.ff_dot.set_color(C["green"])
                self.status_dot.set_color(C["green"]); self._log(f"✔ Auto: {ver}"); return
        self.ff_status.config(text="Not found", fg=C["accent"]); self.ff_dot.set_color(C["accent"])

    # ── Media ops ───────────────────────────────────────────────────
    def _fmt(self, p):
        return f"  {'🖼' if Path(p).suffix.lower() in IMAGE_EXTS else '🎬'}   {Path(p).name}"

    def _add_media(self):
        for f in filedialog.askopenfilenames(title="Select Media",
            filetypes=[("Media"," ".join(f"*{e}" for e in sorted(MEDIA_EXTS))),("All","*.*")]):
            if f not in self.media_paths:
                self.media_paths.append(f); self.media_list.insert("end", self._fmt(f))
        self._upd()

    def _add_folder(self):
        d = filedialog.askdirectory(title="Select folder")
        if not d: return
        a = 0
        for f in sorted(Path(d).iterdir()):
            if f.suffix.lower() in MEDIA_EXTS and str(f) not in self.media_paths:
                self.media_paths.append(str(f)); self.media_list.insert("end", self._fmt(str(f))); a+=1
        self._log(f"📂 +{a} from {Path(d).name}/"); self._upd()

    def _remove_sel(self):
        for i in reversed(list(self.media_list.curselection())):
            self.media_list.delete(i); del self.media_paths[i]
        self._upd()

    def _clear_all(self):
        self.media_paths.clear(); self.media_list.delete(0,"end"); self._upd()

    def _move_up(self):
        s = self.media_list.curselection()
        if not s or s[0]==0: return
        i = s[0]; self.media_paths[i-1],self.media_paths[i] = self.media_paths[i],self.media_paths[i-1]
        self._refresh(i-1)

    def _move_down(self):
        s = self.media_list.curselection()
        if not s or s[0]>=len(self.media_paths)-1: return
        i = s[0]; self.media_paths[i+1],self.media_paths[i] = self.media_paths[i],self.media_paths[i+1]
        self._refresh(i+1)

    def _shuffle(self): random.shuffle(self.media_paths); self._refresh()

    def _refresh(self, sel=None):
        self.media_list.delete(0,"end")
        for p in self.media_paths: self.media_list.insert("end", self._fmt(p))
        if sel is not None: self.media_list.selection_set(sel)

    def _upd(self):
        ni = sum(1 for p in self.media_paths if Path(p).suffix.lower() in IMAGE_EXTS)
        nv = len(self.media_paths)-ni
        parts = []
        if nv: parts.append(f"{nv} vid")
        if ni: parts.append(f"{ni} img")
        self.count_lbl.config(text=" + ".join(parts) if parts else "0 files")

    def _select_audio(self):
        f = filedialog.askopenfilename(title="Select Audio",
            filetypes=[("Audio"," ".join(f"*{e}" for e in sorted(AUDIO_EXTS))),("All","*.*")])
        if f:
            self.audio_path = f; self.audio_lbl.config(text=f"  {Path(f).name}", fg=self.C["text"])
            if self.ffmpeg_backend:
                try:
                    info = self.ffmpeg_backend.probe_video(f)
                    self.audio_dur.config(text=str(timedelta(seconds=int(info["duration"]))))
                except: pass

    def _log(self, m): self.log_text.insert("end", m+"\n"); self.log_text.see("end")
    def _clear_log(self): self.log_text.delete("1.0","end")
    def _set_prog(self, v): self.progress["value"] = v
    def _cancel(self): self.rendering = False; self._log("⚠ Cancel …")

    def _start_render(self):
        if not self.media_paths: return messagebox.showwarning("Error","Add media!")
        if not self.audio_path: return messagebox.showwarning("Error","Select audio!")
        if not self.ffmpeg_backend: return messagebox.showwarning("Error","Set FFmpeg path!")
        out = filedialog.asksaveasfilename(title="Save As", defaultextension=".mp4",
            filetypes=[("MP4","*.mp4")], initialfile="pmv_output.mp4")
        if not out: return
        res = self.resolution_var.get().split("x"); tw,th = int(res[0]),int(res[1])
        fps = int(self.fps_var.get())
        subdiv = int(self.subdiv_var.get().split("(")[0].strip())
        skip = int(self.skip_var.get())
        try: seed = int(self.seed_var.get())
        except: seed = -1

        self.render_btn.set_enabled(False); self.cancel_btn.set_enabled(True)
        self.status_label.config(text="Rendering …", fg=self.C["yellow"])
        self.status_dot.set_color(self.C["yellow"])
        self.log_text.delete("1.0","end"); self.rendering = True

        def _run():
            try:
                build_pmv(
                    backend=self.ffmpeg_backend, media_paths=list(self.media_paths),
                    audio_path=self.audio_path, output_path=out,
                    sensitivity=self.sens_var.get(), subdivision=subdiv, beat_skip=skip,
                    clip_mode=self.clip_mode_var.get(), layout=self.layout_var.get(),
                    transition=self.transition_var.get(), fade_dur=self.fade_var.get(),
                    ken_burns=self.kb_var.get(), effect=self.effect_var.get(),
                    beat_flash=self.flash_var.get(), target_w=tw, target_h=th, fps=fps,
                    quality=self.quality_var.get(), seed=seed,
                    progress_cb=lambda v: self.after(0, self._set_prog, v),
                    log_cb=lambda m: self.after(0, self._log, m))
                self.after(0, lambda: self.status_label.config(text="✅ Done!", fg=self.C["green"]))
                self.after(0, lambda: self.status_dot.set_color(self.C["green"]))
                self.after(0, lambda: messagebox.showinfo("Done!", f"Saved:\n{out}"))
            except Exception as exc:
                err = str(exc)
                self.after(0, lambda: self._log(f"❌ {err}"))
                self.after(0, lambda: self.status_label.config(text="Error", fg=self.C["accent"]))
                self.after(0, lambda: self.status_dot.set_color(self.C["accent"]))
                self.after(0, lambda: messagebox.showerror("Error", err))
            finally:
                self.after(0, lambda: self.render_btn.set_enabled(True))
                self.after(0, lambda: self.cancel_btn.set_enabled(False))
                self.rendering = False
        threading.Thread(target=_run, daemon=True).start()

    def _try_enable_dnd(self):
        try:
            from tkinterdnd2 import DND_FILES
            self.media_list.drop_target_register(DND_FILES)
            self.media_list.dnd_bind("<<Drop>>", self._on_drop)
            for w in [self.ss_center_zone, self.ss_center_lbl]:
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._ss_on_drop)
                w.dnd_bind("<<DragEnter>>", lambda e: self.ss_center_zone.config(
                    highlightbackground=self.C["green"], bg=self.C["green_dim"]) or
                    self.ss_center_lbl.config(bg=self.C["green_dim"]))
                w.dnd_bind("<<DragLeave>>", lambda e: self.ss_center_zone.config(
                    highlightbackground=self.C["accent"], bg=self.C["accent_dim"]) or
                    self.ss_center_lbl.config(bg=self.C["accent_dim"]))
        except: pass

    def _on_drop(self, event):
        for f in self.tk.splitlist(event.data):
            ext = Path(f).suffix.lower()
            if ext in MEDIA_EXTS and f not in self.media_paths:
                self.media_paths.append(f); self.media_list.insert("end", self._fmt(f))
            elif ext in AUDIO_EXTS:
                self.audio_path = f; self.audio_lbl.config(text=f"  {Path(f).name}")
        self._upd()


    # ── Tab: Splitscreen Studio ─────────────────────────────────────
    def _build_splitscreen_tab(self, p):
        C = self.C
        self.ss_base_pmv = ""
        self.ss_center_media = ""
        self.ss_audio_mode = tk.StringVar(value="base")
        self.ss_custom_audio = ""

        # Section: Base PMV
        bi = self._card(p, "Base PMV  (used for Left & Right columns)", (0,6))
        br = tk.Frame(bi, bg=C["card"]); br.pack(fill="x")
        HoverButton(br, text="Browse PMV …", width=120, height=32,
                    bg=C["card2"], fg=C["text"], hover_bg=C["border"],
                    command=self._ss_browse_base).pack(side="left")
        self.ss_base_lbl = tk.Label(br, text="  – none –", font=("Segoe UI",10),
                                     bg=C["card"], fg=C["muted"])
        self.ss_base_lbl.pack(side="left", padx=14)
        self.ss_base_dur = tk.Label(br, text="", font=("Consolas",9),
                                     bg=C["card"], fg=C["cyan"])
        self.ss_base_dur.pack(side="right")

        # Section: 3-column visual layout
        li = self._card(p, "3-Column Layout Preview", (0,6))
        cols_f = tk.Frame(li, bg=C["card"]); cols_f.pack(anchor="w", pady=4)

        lf = tk.Frame(cols_f, bg=C["card2"], width=130, height=95,
                      highlightbackground=C["border"], highlightthickness=1)
        lf.pack(side="left", padx=(0,6)); lf.pack_propagate(False)
        tk.Label(lf, text="LEFT\n(Base PMV)", font=("Segoe UI",9),
                 bg=C["card2"], fg=C["muted"]).place(relx=.5, rely=.5, anchor="center")

        self.ss_center_zone = tk.Frame(cols_f, bg=C["accent_dim"], width=190, height=95,
                                        highlightbackground=C["accent"], highlightthickness=2,
                                        cursor="hand2")
        self.ss_center_zone.pack(side="left", padx=4); self.ss_center_zone.pack_propagate(False)
        self.ss_center_lbl = tk.Label(self.ss_center_zone,
                                       text="CENTER\n⬇ Drop video/image here",
                                       font=("Segoe UI",8), bg=C["accent_dim"],
                                       fg=C["accent_h"], justify="center")
        self.ss_center_lbl.place(relx=.5, rely=.35, anchor="center")
        HoverButton(self.ss_center_zone, text="Browse …", width=80, height=22,
                    bg=C["card2"], fg=C["text"], hover_bg=C["border"],
                    font=("Segoe UI",8), command=self._ss_browse_center).place(
                    relx=.5, rely=.78, anchor="center")

        rf = tk.Frame(cols_f, bg=C["card2"], width=130, height=95,
                      highlightbackground=C["border"], highlightthickness=1)
        rf.pack(side="left", padx=(6,0)); rf.pack_propagate(False)
        tk.Label(rf, text="RIGHT\n(Base PMV\nmirrored)", font=("Segoe UI",9),
                 bg=C["card2"], fg=C["muted"]).place(relx=.5, rely=.5, anchor="center")

        tk.Label(li, text="Tip: left and right columns play the base PMV, right side is horizontally mirrored.",
                 font=("Segoe UI",8), bg=C["card"], fg=C["muted"]).pack(anchor="w", pady=(8,0))

        # Section: Audio
        ai = self._card(p, "Audio Source", (0,6))
        ttk.Radiobutton(ai, text="  Keep base PMV audio",
                        variable=self.ss_audio_mode, value="base",
                        command=self._ss_toggle_audio).pack(anchor="w", pady=3)
        ttk.Radiobutton(ai, text="  Custom audio or MP4 file",
                        variable=self.ss_audio_mode, value="custom",
                        command=self._ss_toggle_audio).pack(anchor="w", pady=3)
        self.ss_audio_row = tk.Frame(ai, bg=C["card"]); self.ss_audio_row.pack(fill="x", pady=(8,0))
        HoverButton(self.ss_audio_row, text="Browse …", width=100, height=30,
                    bg=C["card2"], fg=C["text"], hover_bg=C["border"],
                    command=self._ss_browse_audio).pack(side="left")
        self.ss_custom_audio_lbl = tk.Label(self.ss_audio_row, text="  – none –",
                                             font=("Segoe UI",9), bg=C["card"], fg=C["muted"])
        self.ss_custom_audio_lbl.pack(side="left", padx=10)
        self.ss_audio_row.pack_forget()

        # Section: Output settings
        oi = self._card(p, "Output Settings", (0,6))
        oi.columnconfigure(1, weight=1)
        for row, lbl, vn, vals, default in [
            (0,"Resolution","ss_res_var",["3840x2160","2560x1440","1920x1080","1280x720","854x480"],"1920x1080"),
            (1,"FPS","ss_fps_var",["24","30","60"],"30"),
            (2,"Quality","ss_qual_var",["fast","medium","high","ultra"],"medium"),
        ]:
            self._row(oi, lbl, row)
            sv = tk.StringVar(value=default); setattr(self, vn, sv)
            ttk.Combobox(oi, textvariable=sv, values=vals, state="readonly",
                         width=22).grid(row=row, column=1, sticky="w", pady=7)

        # Render row
        ri = self._card(p, "Render Splitscreen", (0,6))
        rf2 = tk.Frame(ri, bg=C["card"]); rf2.pack(fill="x")
        self.ss_render_btn = HoverButton(rf2, text="🖥  Render Splitscreen", width=190, height=38,
                                          bg=C["accent"], fg="#fff", hover_bg=C["accent_h"],
                                          active_bg="#c0392b", font=("Segoe UI",10,"bold"),
                                          command=self._ss_render)
        self.ss_render_btn.pack(side="left")
        self.ss_progress = ttk.Progressbar(rf2, orient="horizontal", mode="determinate", length=280)
        self.ss_progress.pack(side="left", padx=(16,0), pady=8)

    def _ss_browse_base(self):
        f = filedialog.askopenfilename(title="Select Base PMV",
            filetypes=[("MP4","*.mp4"),("Video"," ".join(f"*{e}" for e in sorted(VIDEO_EXTS))),("All","*.*")])
        if f:
            self.ss_base_pmv = f
            self.ss_base_lbl.config(text=f"  {Path(f).name}", fg=self.C["text"])
            if self.ffmpeg_backend:
                try:
                    info = self.ffmpeg_backend.probe_video(f)
                    self.ss_base_dur.config(text=str(timedelta(seconds=int(info["duration"]))))
                except: pass

    def _ss_browse_center(self):
        f = filedialog.askopenfilename(title="Select Center Column Media",
            filetypes=[("Media"," ".join(f"*{e}" for e in sorted(MEDIA_EXTS))),("All","*.*")])
        if f: self._ss_set_center(f)

    def _ss_set_center(self, f):
        self.ss_center_media = f
        icon = "🖼" if Path(f).suffix.lower() in IMAGE_EXTS else "🎬"
        name = Path(f).name
        self.ss_center_lbl.config(
            text=f"CENTER\n{icon} {name[:22]}", fg=self.C["green"])
        self.ss_center_zone.config(highlightbackground=self.C["green"], bg=self.C["green_dim"])
        self.ss_center_lbl.config(bg=self.C["green_dim"])

    def _ss_on_drop(self, event):
        for f in self.tk.splitlist(event.data):
            ext = Path(f).suffix.lower()
            if ext in MEDIA_EXTS:
                self._ss_set_center(f); break
        self.ss_center_zone.config(highlightbackground=self.C["accent"], bg=self.C["accent_dim"])
        self.ss_center_lbl.config(bg=self.C["accent_dim"])

    def _ss_toggle_audio(self):
        if self.ss_audio_mode.get() == "custom":
            self.ss_audio_row.pack(fill="x", pady=(8,0))
        else:
            self.ss_audio_row.pack_forget()

    def _ss_browse_audio(self):
        f = filedialog.askopenfilename(title="Select Audio or MP4",
            filetypes=[("Audio/Video"," ".join(f"*{e}" for e in sorted(AUDIO_EXTS | VIDEO_EXTS))),("All","*.*")])
        if f:
            self.ss_custom_audio = f
            self.ss_custom_audio_lbl.config(text=f"  {Path(f).name}", fg=self.C["text"])

    def _ss_render(self):
        if not self.ss_base_pmv:
            return messagebox.showwarning("Splitscreen", "Select a base PMV first!")
        if not self.ss_center_media:
            return messagebox.showwarning("Splitscreen", "Add media for the center column!")
        if not self.ffmpeg_backend:
            return messagebox.showwarning("Splitscreen", "Configure FFmpeg first (FFmpeg tab)!")
        if self.ss_audio_mode.get() == "custom" and not self.ss_custom_audio:
            return messagebox.showwarning("Splitscreen", "Select a custom audio file!")
        out = filedialog.asksaveasfilename(title="Save Splitscreen As",
            defaultextension=".mp4", filetypes=[("MP4","*.mp4")],
            initialfile="pmv_splitscreen.mp4")
        if not out: return
        res = self.ss_res_var.get().split("x"); tw, th = int(res[0]), int(res[1])
        fps = int(self.ss_fps_var.get()); quality = self.ss_qual_var.get()
        audio_mode = self.ss_audio_mode.get()
        custom_audio = self.ss_custom_audio if audio_mode == "custom" else None
        self.ss_render_btn.set_enabled(False)
        self.ss_progress["value"] = 0
        def _run():
            try:
                build_splitscreen(
                    backend=self.ffmpeg_backend,
                    base_pmv=self.ss_base_pmv,
                    center_media=self.ss_center_media,
                    output_path=out,
                    audio_mode=audio_mode, custom_audio=custom_audio,
                    target_w=tw, target_h=th, fps=fps, quality=quality,
                    progress_cb=lambda v: self.after(0, lambda val=v: self.ss_progress.__setitem__("value", val)),
                    log_cb=lambda m: self.after(0, self._log, m))
                self.after(0, lambda: messagebox.showinfo("Done!", f"Splitscreen saved:\n{out}"))
            except Exception as exc:
                err = str(exc)
                self.after(0, lambda: self._log(f"❌ Splitscreen: {err}"))
                self.after(0, lambda: messagebox.showerror("Splitscreen Error", err))
            finally:
                self.after(0, lambda: self.ss_render_btn.set_enabled(True))
        threading.Thread(target=_run, daemon=True).start()


class _Mixin:
    C = PMVCreatorApp.C
    def _init_app(self):
        self.title("PMV Creator Pro"); self.geometry("1040x900")
        self.configure(bg=self.C["bg"]); self.resizable(True, True); self.minsize(820, 680)
        self.media_paths = []; self.audio_path = ""
        self.ffmpeg_backend = None; self.rendering = False
        self._apply_styles(); self._build_ui(); self._auto_detect_ffmpeg()

for _n in dir(PMVCreatorApp):
    if _n.startswith("_") and not _n.startswith("__"):
        _m = getattr(PMVCreatorApp, _n)
        if callable(_m): setattr(_Mixin, _n, _m)

def create_app():
    try:
        from tkinterdnd2 import TkinterDnD
        class App(_Mixin, TkinterDnD.Tk):
            def __init__(self): TkinterDnD.Tk.__init__(self); self._init_app()
        return App()
    except ImportError:
        return PMVCreatorApp()

if __name__ == "__main__":
    create_app().mainloop()
