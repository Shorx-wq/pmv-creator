# PMV Creator Pro

A beat-synced music video (PMV) generator with a dark GUI, multi-layout support, visual effects, Ken Burns motion, and a **Splitscreen Studio** for 3-column videos.

---

## Requirements

| Software | Version | Notes |
|----------|---------|-------|
| Python | 3.9 + | [python.org](https://www.python.org/downloads/) |
| FFmpeg | any recent | must be on `PATH` or configured in the app |

### Python packages

```
moviepy>=1.0.3
librosa>=0.10.0
numpy
soundfile
Pillow
tkinterdnd2
```

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/pmv-creator.git
cd pmv-creator

# 2. (Recommended) Create a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install FFmpeg
```

### Installing FFmpeg

**Windows**
1. Download from https://www.gyan.dev/ffmpeg/builds/ (choose `ffmpeg-release-essentials.zip`)
2. Extract to `C:\ffmpeg`
3. Either add `C:\ffmpeg\bin` to your system `PATH`,  
   **or** point the app to the folder via the **FFmpeg** tab inside PMV Creator.

**macOS**
```bash
brew install ffmpeg
```

**Linux**
```bash
sudo apt install ffmpeg      # Debian / Ubuntu
sudo dnf install ffmpeg      # Fedora
```

---

## Running the app

```bash
python pmv_creator.py
```

---

## How to use

### 1. FFmpeg tab — Configure FFmpeg

Open the **FFmpeg** tab and click **Auto-Detect**.  
If that fails, click **Browse** to select your `ffmpeg/bin` folder, then click **Validate**.  
The status dot turns green when FFmpeg is ready.

---

### 2. Media tab — Add your clips

| Button | What it does |
|--------|-------------|
| **+ Add Files** | Pick individual videos / images |
| **Folder** | Import an entire folder of media |
| **Remove / Clear** | Remove selected or all entries |
| **▲ ▼** | Reorder clips |
| **Shuffle** | Randomise order |

**Drag & drop** video / image files directly onto the list.

**Select Audio** — pick an MP3, WAV, FLAC, or any other audio file.  
The total duration shown guides how long your PMV will be.

---

### 3. Layout & FX tab

| Setting | Options |
|---------|---------|
| **Template** | Fullscreen, Split 2/3 columns, Grid 2×2, Top/Bottom, PiP, Center+Wings, Letterbox Triple |
| **Color Effect** | Grayscale, Sepia, High Contrast, Vignette, Film Grain, Neon Glow, Vintage, Cold Blue, Warm Orange, Invert, Mirror, Blur, Sharpen, Emboss |
| **Beat Flash** | White flash on every cut |
| **Transition** | Hard cut, Crossfade, Fade to black |
| **Fade Duration** | 0.05 – 0.5 s |
| **Ken Burns** | Zoom in/out, Pan left/right, Random (for image clips) |

---

### 4. Beats tab — Beat detection

| Setting | What it controls |
|---------|-----------------|
| **Sensitivity** | Low = fewer beats detected; High = more |
| **Subdivision** | Cut on every beat / half beat / quarter beat |
| **Every Nth Beat** | Skip beats to cut slower (1 = every beat, 2 = every other, …) |
| **Clip Mode** | Sequential, Random, or Shuffle |
| **Random Seed** | Set a number for reproducible results; -1 = random |

---

### 5. Output tab

| Setting | Default |
|---------|---------|
| Resolution | 1920×1080 |
| FPS | 30 |
| Quality | medium (fast / medium / high / ultra) |

---

### 6. Rendering a PMV

1. Make sure FFmpeg is configured (green dot).
2. Add at least one media file.
3. Select an audio track.
4. Click **Render PMV** at the bottom of the window.
5. Choose a save path → rendering starts in the background.
6. Progress bar fills; a pop-up confirms when done.

---

### 7. Splitscreen Studio tab — 3-column overlay

This feature lets you take a **finished PMV** (or any video) and combine it with new footage in a 3-column splitscreen.

```
┌─────────────┬──────────────────┬─────────────┐
│   LEFT col  │   CENTER col     │  RIGHT col  │
│  (base PMV) │  (your new clip) │  (base PMV  │
│             │                  │   mirrored) │
└─────────────┴──────────────────┴─────────────┘
```

**Step-by-step**

1. **Base PMV** — click **Browse PMV …** and pick the source video (goes into left + right columns; right side is horizontally mirrored).
2. **Center column** — either:
   - **Drag & drop** a video or image onto the highlighted center zone, or
   - Click **Browse …** inside the center zone.
3. **Audio Source** — choose one:
   - **Keep base PMV audio** — extracts the audio track from the base PMV.
   - **Custom audio / MP4** — pick any audio file or MP4 (its audio will be used).
4. Configure **Output Settings** (resolution, FPS, quality).
5. Click **Render Splitscreen** and choose a save path.

The log output (Media tab) shows progress for both the main PMV and splitscreen renders.

---

## Project structure

```
pmv-creator/
├── pmv_creator.py   # main app
├── requirements.txt
└── README.md
```

---

## Tips & troubleshooting

| Problem | Fix |
|---------|-----|
| FFmpeg not found | Use the FFmpeg tab to point to your `ffmpeg.exe` / `ffmpeg` binary |
| Render hangs on first segment | Make sure your media files are not open in another app |
| Black columns in splitscreen | Your base PMV might have no video stream — re-check with ffprobe |
| `librosa` install fails | Install `pip install librosa --no-build-isolation` or install a C++ build tools first |
| `tkinterdnd2` missing | Run `pip install tkinterdnd2`; drag-and-drop works only when this package is installed |

---

## License

MIT — do whatever you want, just don't remove the attribution.
