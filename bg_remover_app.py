"""
Background Remover & Enhancer - Desktop App
---------------------------------------------
Two tools in one window:
  - Remove Background: drop image(s) in, get transparent PNG(s) back
  - Enhance Quality: upscale small/blurry images using local AI super-resolution,
    with precise target width/height in pixels, inches, cm, or mm.

Both support single images or batch (multiple files at once).
The whole window scrolls, so nothing is ever hidden regardless of screen size.

Run with:
    python bg_remover_app.py
"""

import os
import sys
import threading
import urllib.request
from pathlib import Path
from io import BytesIO

try:
    import tkinterdnd2 as tkdnd
    from tkinterdnd2 import DND_FILES
except ImportError:
    print("Missing package. Please run:\n    pip install tkinterdnd2")
    sys.exit(1)

import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

try:
    from PIL import Image, ImageTk
    from rembg import remove
except ImportError as e:
    print("Missing packages. Please run:")
    print("    pip install rembg pillow onnxruntime")
    print(f"\nActual error: {e}")
    import traceback
    traceback.print_exc()
    input("\nPress Enter to close...")
    sys.exit(1)

# cv2 is only needed for the Enhance tab; degrade gracefully if missing
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

VALID_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
UPSCALE_MODEL_PATH = MODELS_DIR / "FSRCNN_x4.pb"
UPSCALE_MODEL_URL = (
    "https://raw.githubusercontent.com/Saafke/FSRCNN_Tensorflow/master/models/FSRCNN_x4.pb"
)

BG = "#1e1e1e"
PANEL_BG = "#2a2a2a"
ACCENT = "#00875a"
ACCENT_HOVER = "#00693f"

UNIT_TO_INCHES = {
    "Pixels": None,
    "Inches": 1.0,
    "Centimeters": 1 / 2.54,
    "Millimeters": 1 / 25.4,
}


def ensure_upscale_model():
    """Download the super-resolution model once, if not already present."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if UPSCALE_MODEL_PATH.exists():
        return True
    try:
        urllib.request.urlretrieve(UPSCALE_MODEL_URL, UPSCALE_MODEL_PATH)
        return True
    except Exception:
        return False


class ScrollableFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = tk.Frame(canvas, bg=BG)

        self.inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)


class FileQueue(tk.Frame):
    """Drop zone + list of queued files, shared by both tabs."""

    def __init__(self, parent, on_files_added):
        super().__init__(parent, bg=BG)
        self.on_files_added = on_files_added
        self.files = []

        self.drop_frame = tk.Frame(
            self, bg=PANEL_BG, highlightbackground="#555", highlightthickness=2,
            height=120
        )
        self.drop_frame.pack(fill="x", pady=(0, 8))
        self.drop_frame.pack_propagate(False)

        self.drop_label = tk.Label(
            self.drop_frame,
            text="⬇  Drag image(s) here, or click to browse\n(you can select more than one file)",
            font=("Segoe UI", 11), bg=PANEL_BG, fg="#aaaaaa", justify="center"
        )
        self.drop_label.pack(expand=True)
        self.drop_label.bind("<Button-1>", lambda e: self.browse_files())
        self.drop_frame.bind("<Button-1>", lambda e: self.browse_files())

        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind("<<Drop>>", self.on_drop)
        self.drop_label.drop_target_register(DND_FILES)
        self.drop_label.dnd_bind("<<Drop>>", self.on_drop)

        list_frame = tk.Frame(self, bg=BG)
        list_frame.pack(fill="both", expand=False)

        self.listbox = tk.Listbox(
            list_frame, height=4, bg=PANEL_BG, fg="white",
            selectbackground=ACCENT, borderwidth=0, highlightthickness=1,
            highlightbackground="#444"
        )
        self.listbox.pack(side="left", fill="both", expand=True)

        clear_btn = tk.Button(
            list_frame, text="Clear", font=("Segoe UI", 9),
            bg="#3a3a3a", fg="white", relief="flat", command=self.clear
        )
        clear_btn.pack(side="left", padx=(6, 0), fill="y")

    def browse_files(self):
        paths = filedialog.askopenfilenames(
            title="Choose image(s)",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp")]
        )
        if paths:
            self._add_files([Path(p) for p in paths])

    def on_drop(self, event):
        raw = event.data
        parts = []
        current = ""
        in_brace = False
        for ch in raw:
            if ch == "{":
                in_brace = True
                current = ""
            elif ch == "}":
                in_brace = False
                parts.append(current)
                current = ""
            elif ch == " " and not in_brace:
                if current:
                    parts.append(current)
                    current = ""
            else:
                current += ch
        if current:
            parts.append(current)

        new_paths = [Path(p) for p in parts if Path(p).suffix.lower() in VALID_EXTENSIONS]
        if new_paths:
            self._add_files(new_paths)

    def _add_files(self, paths):
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                self.listbox.insert("end", p.name)
        self.on_files_added(self.files)

    def clear(self):
        self.files = []
        self.listbox.delete(0, "end")
        self.on_files_added(self.files)


class RemoveBgTab(ScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent)
        c = self.inner
        self.output_image = None
        self.input_path = None
        self.result_imgtk = None

        self.queue = FileQueue(c, self.on_files_changed)
        self.queue.pack(fill="x", padx=15, pady=(15, 5))

        preview_frame = tk.Frame(c, bg=BG)
        preview_frame.pack(pady=10)

        self.result_panel = tk.Frame(
            preview_frame, width=300, height=200, bg=PANEL_BG,
            highlightbackground="#555", highlightthickness=2
        )
        self.result_panel.pack()
        self.result_panel.pack_propagate(False)
        self.result_label = tk.Label(
            self.result_panel, text="Result preview\n(single image mode)",
            font=("Segoe UI", 10), bg=PANEL_BG, fg="#666666", justify="center"
        )
        self.result_label.pack(expand=True)

        self.status_var = tk.StringVar(value="Add one or more images above to start.")
        tk.Label(c, textvariable=self.status_var, font=("Segoe UI", 9),
                 bg=BG, fg="#00c07f").pack(pady=(5, 5))

        self.progress = ttk.Progressbar(c, mode="determinate", length=320)
        self.progress.pack(pady=(0, 10))

        btn_row = tk.Frame(c, bg=BG)
        btn_row.pack(pady=(5, 20))

        self.process_btn = tk.Button(
            btn_row, text="Remove Background", font=("Segoe UI", 11, "bold"),
            bg=ACCENT, fg="white", activebackground=ACCENT_HOVER,
            relief="flat", padx=20, pady=8, command=self.start_processing,
            state="disabled"
        )
        self.process_btn.pack(side="left", padx=5)

        self.save_btn = tk.Button(
            btn_row, text="Save Result As...", font=("Segoe UI", 11, "bold"),
            bg="#3a3a3a", fg="white", relief="flat", padx=20, pady=8,
            command=self.save_single, state="disabled"
        )
        self.save_btn.pack(side="left", padx=5)

    def on_files_changed(self, files):
        self.process_btn.config(state="normal" if files else "disabled")
        self.save_btn.config(state="disabled")
        self.output_image = None
        if len(files) == 1:
            self.status_var.set(f"Ready: {files[0].name}")
        elif len(files) > 1:
            self.status_var.set(f"Ready: {len(files)} images queued (batch mode)")
        else:
            self.status_var.set("Add one or more images above to start.")

    def start_processing(self):
        files = list(self.queue.files)
        if not files:
            return
        self.process_btn.config(state="disabled")
        if len(files) == 1:
            threading.Thread(target=self._process_single, args=(files[0],), daemon=True).start()
        else:
            out_dir = filedialog.askdirectory(title="Choose a folder to save all results")
            if not out_dir:
                self.process_btn.config(state="normal")
                return
            threading.Thread(target=self._process_batch, args=(files, Path(out_dir)), daemon=True).start()

    def _process_single(self, path):
        self.status_var.set("Processing...")
        self.progress.config(mode="indeterminate")
        self.progress.start(12)
        try:
            with open(path, "rb") as f:
                result = remove(f.read())
            img = Image.open(BytesIO(result)).convert("RGBA")
            self.output_image = img
            self.input_path = path
            preview = img.copy()
            preview.thumbnail((280, 180))
            self.result_imgtk = ImageTk.PhotoImage(preview)
            self.after(0, self._on_single_done, None)
        except Exception as e:
            self.after(0, self._on_single_done, str(e))

    def _on_single_done(self, error):
        self.progress.stop()
        self.progress.config(mode="determinate")
        self.progress["value"] = 100 if not error else 0
        self.process_btn.config(state="normal")
        if error:
            self.status_var.set("Failed.")
            messagebox.showerror("Error", f"Processing failed: {error}")
            return
        self.result_label.config(image=self.result_imgtk, text="")
        self.status_var.set("Done! Background removed.")
        self.save_btn.config(state="normal")

    def _process_batch(self, files, out_dir):
        total = len(files)
        for i, path in enumerate(files, start=1):
            self.after(0, lambda i=i, n=path.name: self.status_var.set(f"Processing {i}/{total}: {n}"))
            try:
                with open(path, "rb") as f:
                    result = remove(f.read())
                img = Image.open(BytesIO(result)).convert("RGBA")
                img.save(out_dir / f"{path.stem}_no_bg.png")
            except Exception as e:
                self.after(0, lambda n=path.name, err=e: self.status_var.set(f"Failed on {n}: {err}"))
                continue
            self.after(0, lambda i=i: self.progress.config(value=int(i / total * 100)))
        self.after(0, self._on_batch_done, out_dir)

    def _on_batch_done(self, out_dir):
        self.process_btn.config(state="normal")
        self.status_var.set(f"Batch done! Saved to {out_dir}")
        messagebox.showinfo("Batch complete", f"All images processed.\nSaved to:\n{out_dir}")

    def save_single(self):
        if self.output_image is None:
            return
        default_name = self.input_path.stem + "_no_bg.png"
        save_path = filedialog.asksaveasfilename(
            title="Save result", initialfile=default_name,
            defaultextension=".png", filetypes=[("PNG Image", "*.png")]
        )
        if save_path:
            self.output_image.save(save_path)
            messagebox.showinfo("Saved", f"Saved to:\n{save_path}")


class EnhanceTab(ScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent)
        c = self.inner
        self.output_image = None
        self.input_path = None
        self.result_imgtk = None
        self.orig_w = None
        self.orig_h = None
        self._updating = False

        if not CV2_AVAILABLE:
            tk.Label(
                c, text="Enhance Quality needs an extra package.\n\n"
                        "Run this in your terminal, then restart the app:\n"
                        "    pip install opencv-contrib-python",
                font=("Segoe UI", 11), bg=BG, fg="#ff8080", justify="center"
            ).pack(expand=True, pady=60)
            return

        self.queue = FileQueue(c, self.on_files_changed)
        self.queue.pack(fill="x", padx=15, pady=(15, 5))

        dim_frame = tk.LabelFrame(
            c, text=" Target Size ", font=("Segoe UI", 10, "bold"),
            bg=BG, fg="#aaaaaa", labelanchor="n", bd=1, relief="groove"
        )
        dim_frame.pack(fill="x", padx=15, pady=(5, 10))

        row1 = tk.Frame(dim_frame, bg=BG)
        row1.pack(pady=(10, 6), padx=10, fill="x")
        tk.Label(row1, text="Unit:", font=("Segoe UI", 10), bg=BG, fg="white").pack(side="left")
        self.unit_var = tk.StringVar(value="Pixels")
        unit_menu = ttk.Combobox(
            row1, textvariable=self.unit_var, state="readonly", width=14,
            values=["Pixels", "Inches", "Centimeters", "Millimeters"]
        )
        unit_menu.pack(side="left", padx=(8, 20))
        unit_menu.bind("<<ComboboxSelected>>", self._on_unit_change)

        tk.Label(row1, text="DPI:", font=("Segoe UI", 10), bg=BG, fg="white").pack(side="left")
        self.dpi_var = tk.StringVar(value="300")
        self.dpi_entry = tk.Entry(row1, textvariable=self.dpi_var, width=6,
                                   bg=PANEL_BG, fg="white", insertbackground="white")
        self.dpi_entry.pack(side="left", padx=(8, 0))
        self.dpi_hint = tk.Label(row1, text="(used to convert inches/cm/mm to pixels)",
                                  font=("Segoe UI", 8), bg=BG, fg="#777777")
        self.dpi_hint.pack(side="left", padx=(8, 0))

        row2 = tk.Frame(dim_frame, bg=BG)
        row2.pack(pady=(0, 6), padx=10, fill="x")
        tk.Label(row2, text="Width:", font=("Segoe UI", 10), bg=BG, fg="white").pack(side="left")
        self.width_var = tk.StringVar(value="")
        self.width_entry = tk.Entry(row2, textvariable=self.width_var, width=10,
                                     bg=PANEL_BG, fg="white", insertbackground="white")
        self.width_entry.pack(side="left", padx=(8, 20))
        self.width_entry.bind("<KeyRelease>", lambda e: self._on_dim_edit("width"))

        tk.Label(row2, text="Height:", font=("Segoe UI", 10), bg=BG, fg="white").pack(side="left")
        self.height_var = tk.StringVar(value="")
        self.height_entry = tk.Entry(row2, textvariable=self.height_var, width=10,
                                      bg=PANEL_BG, fg="white", insertbackground="white")
        self.height_entry.pack(side="left", padx=(8, 20))
        self.height_entry.bind("<KeyRelease>", lambda e: self._on_dim_edit("height"))

        self.lock_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            row2, text="Keep aspect ratio", variable=self.lock_var,
            bg=BG, fg="white", selectcolor="#3a3a3a",
            activebackground=BG, activeforeground="white"
        ).pack(side="left", padx=(10, 0))

        self.dim_info_var = tk.StringVar(value="Add an image to see its original size.")
        tk.Label(dim_frame, textvariable=self.dim_info_var, font=("Segoe UI", 8),
                 bg=BG, fg="#777777").pack(pady=(0, 8), padx=10, anchor="w")

        preview_frame = tk.Frame(c, bg=BG)
        preview_frame.pack(pady=10)
        self.result_panel = tk.Frame(
            preview_frame, width=300, height=200, bg=PANEL_BG,
            highlightbackground="#555", highlightthickness=2
        )
        self.result_panel.pack()
        self.result_panel.pack_propagate(False)
        self.result_label = tk.Label(
            self.result_panel, text="Enhanced preview\n(single image mode)",
            font=("Segoe UI", 10), bg=PANEL_BG, fg="#666666", justify="center"
        )
        self.result_label.pack(expand=True)

        self.status_var = tk.StringVar(value="Add one or more images above to start.")
        tk.Label(c, textvariable=self.status_var, font=("Segoe UI", 9),
                 bg=BG, fg="#00c07f").pack(pady=(5, 5))

        self.progress = ttk.Progressbar(c, mode="determinate", length=320)
        self.progress.pack(pady=(0, 10))

        btn_row = tk.Frame(c, bg=BG)
        btn_row.pack(pady=(5, 20))

        self.preview_btn = tk.Button(
            btn_row, text="Preview Enhancement", font=("Segoe UI", 11, "bold"),
            bg=ACCENT, fg="white", activebackground=ACCENT_HOVER,
            relief="flat", padx=18, pady=8, command=self.start_processing,
            state="disabled"
        )
        self.preview_btn.pack(side="left", padx=5)

        self.save_btn = tk.Button(
            btn_row, text="Save Result As...", font=("Segoe UI", 11, "bold"),
            bg="#3a3a3a", fg="white", relief="flat", padx=18, pady=8,
            command=self.save_single, state="disabled"
        )
        self.save_btn.pack(side="left", padx=5)

    def _on_unit_change(self, event=None):
        show_dpi = self.unit_var.get() != "Pixels"
        if show_dpi:
            self.dpi_entry.pack(side="left", padx=(8, 0))
            self.dpi_hint.pack(side="left", padx=(8, 0))
        else:
            self.dpi_entry.pack_forget()
            self.dpi_hint.pack_forget()
        if self.orig_w:
            self._set_dims_from_pixels(self.orig_w, self.orig_h)

    def _unit_to_pixels(self, value):
        unit = self.unit_var.get()
        if unit == "Pixels":
            return value
        try:
            dpi = float(self.dpi_var.get())
        except ValueError:
            dpi = 300
        inches = value * UNIT_TO_INCHES[unit]
        return inches * dpi

    def _pixels_to_unit(self, px):
        unit = self.unit_var.get()
        if unit == "Pixels":
            return px
        try:
            dpi = float(self.dpi_var.get())
        except ValueError:
            dpi = 300
        inches = px / dpi
        return inches / UNIT_TO_INCHES[unit]

    def _set_dims_from_pixels(self, w_px, h_px):
        self._updating = True
        self.width_var.set(f"{self._pixels_to_unit(w_px):.2f}".rstrip("0").rstrip("."))
        self.height_var.set(f"{self._pixels_to_unit(h_px):.2f}".rstrip("0").rstrip("."))
        self._updating = False

    def _on_dim_edit(self, which):
        if self._updating or not self.lock_var.get() or not self.orig_w:
            return
        aspect = self.orig_h / self.orig_w
        try:
            if which == "width":
                w = float(self.width_var.get())
                w_px = self._unit_to_pixels(w)
                h_px = w_px * aspect
                self._updating = True
                self.height_var.set(f"{self._pixels_to_unit(h_px):.2f}".rstrip("0").rstrip("."))
                self._updating = False
            else:
                h = float(self.height_var.get())
                h_px = self._unit_to_pixels(h)
                w_px = h_px / aspect
                self._updating = True
                self.width_var.set(f"{self._pixels_to_unit(w_px):.2f}".rstrip("0").rstrip("."))
                self._updating = False
        except ValueError:
            pass

    def on_files_changed(self, files):
        self.preview_btn.config(state="normal" if files else "disabled")
        self.save_btn.config(state="disabled")
        self.output_image = None
        if len(files) == 1:
            self.status_var.set(f"Ready: {files[0].name}")
            try:
                with Image.open(files[0]) as im:
                    self.orig_w, self.orig_h = im.size
                self.dim_info_var.set(f"Original size: {self.orig_w} x {self.orig_h} px")
                self._set_dims_from_pixels(self.orig_w, self.orig_h)
            except Exception:
                pass
        elif len(files) > 1:
            self.status_var.set(f"Ready: {len(files)} images queued (batch mode)")
            self.dim_info_var.set("Batch mode: target size below applies to all images.")
        else:
            self.status_var.set("Add one or more images above to start.")
            self.dim_info_var.set("Add an image to see its original size.")

    def _get_target_pixels(self):
        w = float(self.width_var.get())
        h = float(self.height_var.get())
        return int(round(self._unit_to_pixels(w))), int(round(self._unit_to_pixels(h)))

    def _get_sr(self, scale):
        if not ensure_upscale_model():
            raise RuntimeError(
                "Could not download the enhancement model. Check your internet "
                "connection, or manually place FSRCNN_x4.pb in the 'models' folder."
            )
        sr = cv2.dnn_superres.DnnSuperResImpl_create()
        sr.readModel(str(UPSCALE_MODEL_PATH))
        sr.setModel("fsrcnn", scale)
        return sr

    def start_processing(self):
        files = list(self.queue.files)
        if not files:
            return
        try:
            target_w, target_h = self._get_target_pixels()
            if target_w <= 0 or target_h <= 0:
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid size", "Please enter a valid width and height.")
            return

        self.preview_btn.config(state="disabled")
        if len(files) == 1:
            threading.Thread(target=self._process_single, args=(files[0], target_w, target_h), daemon=True).start()
        else:
            out_dir = filedialog.askdirectory(title="Choose a folder to save all results")
            if not out_dir:
                self.preview_btn.config(state="normal")
                return
            threading.Thread(target=self._process_batch, args=(files, Path(out_dir), target_w, target_h), daemon=True).start()

    def _pad_to_multiple(self, img, multiple):
        """Pad image so both dimensions divide evenly by `multiple`.
        Some OpenCV super-resolution models error on odd dimensions;
        padding (then cropping back after) works around that."""
        h, w = img.shape[:2]
        pad_h = (multiple - h % multiple) % multiple
        pad_w = (multiple - w % multiple) % multiple
        if pad_h or pad_w:
            img = cv2.copyMakeBorder(img, 0, pad_h, 0, pad_w, cv2.BORDER_REPLICATE)
        return img, pad_h, pad_w

    def _ai_upsample_step(self, img, step):
        """Run one AI upsampling pass. Falls back to a plain high-quality
        resize if the model errors out on this particular image."""
        try:
            padded, pad_h, pad_w = self._pad_to_multiple(img, step)
            sr = self._get_sr(step)
            result = sr.upsample(padded)
            new_h = result.shape[0] - pad_h * step
            new_w = result.shape[1] - pad_w * step
            return result[0:new_h, 0:new_w]
        except cv2.error:
            h, w = img.shape[:2]
            return cv2.resize(img, (w * step, h * step), interpolation=cv2.INTER_CUBIC)

    def _upscale_to_target(self, path, target_w, target_h):
        img_bgr = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise RuntimeError("Could not read image file.")
        h, w = img_bgr.shape[:2]
        needed_factor = max(target_w / w, target_h / h)

        if needed_factor <= 1.0:
            # Downscaling or same size - plain high-quality resize, no AI needed
            resized = cv2.resize(img_bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)
        else:
            # Pick the smallest supported model factor that covers what's needed,
            # chaining passes for very large factors. Each pass falls back to a
            # plain resize automatically if the AI model can't handle this image.
            current = img_bgr
            remaining = needed_factor
            while remaining > 1.0:
                step = 2 if remaining <= 2 else (3 if remaining <= 3 else 4)
                current = self._ai_upsample_step(current, step)
                remaining = remaining / step
            resized = cv2.resize(current, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)

        result_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        return Image.fromarray(result_rgb)

    def _process_single(self, path, target_w, target_h):
        self.status_var.set("Enhancing... (first run downloads the model, ~10MB)")
        self.progress.config(mode="indeterminate")
        self.progress.start(12)
        try:
            img = self._upscale_to_target(path, target_w, target_h)
            self.output_image = img
            self.input_path = path
            preview = img.copy()
            preview.thumbnail((280, 180))
            self.result_imgtk = ImageTk.PhotoImage(preview)
            self.after(0, self._on_single_done, None)
        except Exception as e:
            self.after(0, self._on_single_done, str(e))

    def _on_single_done(self, error):
        self.progress.stop()
        self.progress.config(mode="determinate")
        self.preview_btn.config(state="normal")
        if error:
            self.status_var.set("Failed.")
            messagebox.showerror("Error", f"Enhancement failed: {error}")
            return
        self.result_label.config(image=self.result_imgtk, text="")
        self.status_var.set(f"Preview ready at {self.output_image.width} x {self.output_image.height} px. Review it, then save.")
        self.save_btn.config(state="normal")

    def _process_batch(self, files, out_dir, target_w, target_h):
        total = len(files)
        for i, path in enumerate(files, start=1):
            self.after(0, lambda i=i, n=path.name: self.status_var.set(f"Enhancing {i}/{total}: {n}"))
            try:
                img = self._upscale_to_target(path, target_w, target_h)
                img.save(out_dir / f"{path.stem}_enhanced.png")
            except Exception as e:
                self.after(0, lambda n=path.name, err=e: self.status_var.set(f"Failed on {n}: {err}"))
                continue
            self.after(0, lambda i=i: self.progress.config(value=int(i / total * 100)))
        self.after(0, self._on_batch_done, out_dir)

    def _on_batch_done(self, out_dir):
        self.preview_btn.config(state="normal")
        self.status_var.set(f"Batch done! Saved to {out_dir}")
        messagebox.showinfo("Batch complete", f"All images enhanced.\nSaved to:\n{out_dir}")

    def save_single(self):
        if self.output_image is None:
            return
        default_name = self.input_path.stem + "_enhanced.png"
        save_path = filedialog.asksaveasfilename(
            title="Save result", initialfile=default_name,
            defaultextension=".png", filetypes=[("PNG Image", "*.png")]
        )
        if save_path:
            self.output_image.save(save_path)
            messagebox.showinfo("Saved", f"Saved to:\n{save_path}")


def main():
    root = tkdnd.TkinterDnD.Tk()
    root.title("Background Remover & Enhancer")
    root.geometry("900x750")
    root.minsize(600, 400)
    root.configure(bg=BG)

    try:
        root.state("zoomed")
    except tk.TclError:
        try:
            root.attributes("-zoomed", True)
        except tk.TclError:
            pass

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=PANEL_BG, foreground="white", padding=(16, 8))
    style.map("TNotebook.Tab", background=[("selected", ACCENT)])

    title = tk.Label(
        root, text="Background Remover & Enhancer", font=("Segoe UI", 18, "bold"),
        bg=BG, fg="white"
    )
    title.pack(pady=(15, 10))

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    remove_tab = RemoveBgTab(notebook)
    enhance_tab = EnhanceTab(notebook)
    notebook.add(remove_tab, text="Remove Background")
    notebook.add(enhance_tab, text="Enhance Quality")

    root.mainloop()


if __name__ == "__main__":
    main()