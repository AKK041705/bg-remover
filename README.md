# Background Remover

A local, offline background removal tool built with Python. Drop in an image, get back a transparent-background PNG — no internet required after the first run, no paid API, no uploading your images anywhere.

Originally built for my own multimedia/design work (removing backgrounds locally instead of relying on Photoshop or paid tools), and shared here for free — feel free to use it, modify it, or build on it. This project is actively maintained and will keep getting updates.

Comes in two versions:

- **Desktop App** (`bg_remover_app.py`) — a proper drag-and-drop window with two tools in tabs: **Remove Background** and **Enhance Quality**. Supports batch processing (drop multiple images at once). Recommended.
- **Folder Watcher** (`remove_bg_watcher.py`) — a background script that watches an `input` folder and auto-removes backgrounds from anything dropped into it.

Background removal uses [`rembg`](https://github.com/danielgatis/rembg), which runs an AI segmentation model locally via `onnxruntime`. Image enhancement (upscaling) uses OpenCV's local super-resolution (FSRCNN) — a Real-ESRGAN upgrade for noticeably sharper results is planned (see [Roadmap](ROADMAP.md)).

---

## Requirements

- Python 3.9+ (tested on 3.13)
- Windows, macOS, or Linux
- ~200MB free disk space (for the AI model + dependencies)
- Internet connection **once**, to download the AI model on first use

---

## Setup

Clone the repo and enter the folder:

```bash
git clone https://github.com/AKK041705/bg-remover.git
cd bg-remover
```

Create and activate a virtual environment:

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements_app.txt
```

> If you only want the folder-watcher version and not the GUI, `pip install -r requirements.txt` is enough instead.

---

## Usage

### Desktop App (recommended)

```bash
python bg_remover_app.py
```

A window opens with two tabs:

**Remove Background**
1. Drag one or more images into the drop zone (or click it to browse)
2. For a single image: click **Remove Background**, preview the result, then **Save Result As...**
3. For multiple images: click **Remove Background**, choose an output folder — all results save automatically as `<filename>_no_bg.png`

**Enhance Quality** (fixes images that blur when enlarged)
1. Drag in one or more images
2. Choose a unit (Pixels, Inches, Centimeters, or Millimeters) and enter a target width/height — height auto-fills if "Keep aspect ratio" is checked. DPI controls the pixel conversion for physical units (300 is a safe default for print)
3. Click **Preview Enhancement** to see the result before committing
4. Click **Save Result As...** (single image) or process straight to a folder (batch)

First use of either tool downloads its AI model automatically (~170MB for background removal, ~10MB for enhancement) — one-time only, then it's fully offline.

### Folder Watcher

```bash
python remove_bg_watcher.py
```

This creates `input` and `output` folders next to the script.

- Drop images into `input`
- Processed results land in `output` as `<filename>_no_bg.png`
- Originals are moved to `input/_processed` so they aren't reprocessed

---

## Building a standalone .exe (Windows)

To get a double-clickable app with no need for Python or a terminal:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "BackgroundRemover" --collect-all tkinterdnd2 --collect-all rembg --collect-all onnxruntime --collect-all click --collect-all pymatting bg_remover_app.py
```

The finished app will be at `dist/BackgroundRemover.exe`. It's large (200–400MB) since it bundles the AI runtime — that's normal.

> Build on the OS you're targeting — PyInstaller can't cross-build a Windows `.exe` from macOS/Linux.

---

## Project Structure

```
bg-remover/
├── bg_remover_app.py       # Desktop GUI app (drag-and-drop)
├── remove_bg_watcher.py    # Folder-watcher script
├── requirements.txt        # Deps for the folder watcher
├── requirements_app.txt    # Deps for the desktop app
└── README.md
```

---

## Notes

- Output is always saved as PNG, since transparency requires it (even if your input was JPG).
- Best results come from decently lit, higher-resolution photos — fine detail like hair is harder for the model.
- Everything runs locally after setup; no images are ever uploaded anywhere.
- The current Enhance Quality model (FSRCNN) is fast and lightweight but modest in quality. A Real-ESRGAN upgrade is planned for a much sharper result — see [ROADMAP.md](ROADMAP.md).

---

## License

This project is licensed under the [MIT License](LICENSE) — free to use, modify, and distribute, even commercially. Just keep the original copyright notice.

---

## Author

**Abdul Karim**
Software Engineering & Multimedia, Limkokwing University of Creative Technology (Sierra Leone Campus)
GitHub: [@AKK041705](https://github.com/AKK041705)
