# Background Remover

A local, offline background removal tool built with Python. Drop in an image, get back a transparent-background PNG — no internet required after the first run, no paid API, no uploading your images anywhere.

Originally built for my own multimedia/design work (removing backgrounds locally instead of relying on Photoshop or paid tools), and shared here for free — feel free to use it, modify it, or build on it. This project is actively maintained and will keep getting updates.

Comes in two versions:

- **Desktop App** (`bg_remover_app.py`) — a proper drag-and-drop window with a live preview. Recommended.
- **Folder Watcher** (`remove_bg_watcher.py`) — a background script that watches an `input` folder and auto-processes anything dropped into it.

Both use [`rembg`](https://github.com/danielgatis/rembg), which runs an AI segmentation model locally on your machine via `onnxruntime`.

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

A window opens with a drag-and-drop panel on the left and a live result preview on the right.

1. Drag an image into the left panel (or click it to browse)
2. Wait for processing (first run downloads the AI model, ~170MB, one-time only)
3. Click **Save Result As...** to save the transparent PNG

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

---

## Notes

- Output is always saved as PNG, since transparency requires it (even if your input was JPG).
- Best results come from decently lit, higher-resolution photos — fine detail like hair is harder for the model.
- Everything runs locally after setup; no images are ever uploaded anywhere.

---

## License

This project is licensed under the [MIT License](LICENSE) — free to use, modify, and distribute, even commercially. Just keep the original copyright notice.

---

## Author

**Abdul Karim**
Software Engineering & Multimedia, Limkokwing University of Creative Technology (Sierra Leone Campus)
GitHub: [@AKK041705](https://github.com/AKK041705)
