"""
Background Remover - Desktop App
----------------------------------
A simple Windows app with a drag-and-drop window. Drop an image in,
it removes the background and shows you a preview, then you save it
wherever you like.

Run with:
    python bg_remover_app.py
"""

import os
import sys
import threading
from pathlib import Path

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

VALID_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
PREVIEW_SIZE = (340, 340)


class BgRemoverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Background Remover")
        self.root.geometry("800x680")
        self.root.minsize(700, 600)
        self.root.configure(bg="#1e1e1e")
        self.root.resizable(True, True)

        self.input_path = None
        self.output_image = None  # PIL Image, background removed
        self.original_preview_imgtk = None
        self.result_preview_imgtk = None

        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        title = tk.Label(
            self.root, text="Background Remover", font=("Segoe UI", 18, "bold"),
            bg="#1e1e1e", fg="white"
        )
        title.pack(pady=(15, 5))

        subtitle = tk.Label(
            self.root,
            text="Drag an image below, or click to browse",
            font=("Segoe UI", 10), bg="#1e1e1e", fg="#aaaaaa"
        )
        subtitle.pack(pady=(0, 10))

        # Frame holding two preview panels side by side
        panels = tk.Frame(self.root, bg="#1e1e1e")
        panels.pack(pady=5)

        # Left: drop zone / original preview
        self.drop_frame = tk.Frame(
            panels, width=PREVIEW_SIZE[0], height=PREVIEW_SIZE[1],
            bg="#2a2a2a", highlightbackground="#555", highlightthickness=2
        )
        self.drop_frame.grid(row=0, column=0, padx=15)
        self.drop_frame.pack_propagate(False)

        self.drop_label = tk.Label(
            self.drop_frame, text="⬇\n\nDrop image here\n(or click)",
            font=("Segoe UI", 12), bg="#2a2a2a", fg="#888888", justify="center"
        )
        self.drop_label.pack(expand=True)
        self.drop_label.bind("<Button-1>", lambda e: self.browse_file())
        self.drop_frame.bind("<Button-1>", lambda e: self.browse_file())

        # Right: result preview
        self.result_frame = tk.Frame(
            panels, width=PREVIEW_SIZE[0], height=PREVIEW_SIZE[1],
            bg="#2a2a2a", highlightbackground="#555", highlightthickness=2
        )
        self.result_frame.grid(row=0, column=1, padx=15)
        self.result_frame.pack_propagate(False)

        self.result_label = tk.Label(
            self.result_frame, text="Result will appear here",
            font=("Segoe UI", 11), bg="#2a2a2a", fg="#666666", justify="center"
        )
        self.result_label.pack(expand=True)

        # Register drag and drop on the drop zone
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind("<<Drop>>", self.on_drop)
        self.drop_label.drop_target_register(DND_FILES)
        self.drop_label.dnd_bind("<<Drop>>", self.on_drop)

        # Status label
        self.status_var = tk.StringVar(value="Waiting for an image...")
        status = tk.Label(
            self.root, textvariable=self.status_var, font=("Segoe UI", 9),
            bg="#1e1e1e", fg="#00c07f"
        )
        status.pack(pady=(15, 5))

        # Progress bar
        self.progress = ttk.Progressbar(self.root, mode="indeterminate", length=300)
        self.progress.pack(pady=(0, 10))

        # Save button
        self.save_btn = tk.Button(
            self.root, text="Save Result As...", font=("Segoe UI", 11, "bold"),
            bg="#00875a", fg="white", activebackground="#00693f",
            relief="flat", padx=20, pady=8, command=self.save_result,
            state="disabled"
        )
        self.save_btn.pack(pady=5)

    # ---------- Handlers ----------
    def browse_file(self):
        path = filedialog.askopenfilename(
            title="Choose an image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp")]
        )
        if path:
            self.load_image(Path(path))

    def on_drop(self, event):
        # event.data may contain multiple files wrapped in {}
        raw = event.data
        path = raw.strip("{}").split("} {")[0] if raw else None
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() not in VALID_EXTENSIONS:
            messagebox.showerror("Unsupported file", f"'{p.suffix}' is not supported.")
            return
        self.load_image(p)

    def load_image(self, path: Path):
        self.input_path = path
        self.status_var.set(f"Loaded: {path.name}")
        self.save_btn.config(state="disabled")
        self.result_label.config(image="", text="Processing...")

        # Show original preview
        try:
            img = Image.open(path)
            img.thumbnail(PREVIEW_SIZE)
            self.original_preview_imgtk = ImageTk.PhotoImage(img)
            self.drop_label.config(image=self.original_preview_imgtk, text="")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open image: {e}")
            return

        # Process in background thread so UI doesn't freeze
        self.progress.start(12)
        threading.Thread(target=self._process_image, args=(path,), daemon=True).start()

    def _process_image(self, path: Path):
        try:
            with open(path, "rb") as f:
                input_bytes = f.read()
            output_bytes = remove(input_bytes)

            from io import BytesIO
            result_img = Image.open(BytesIO(output_bytes)).convert("RGBA")
            self.output_image = result_img

            preview = result_img.copy()
            preview.thumbnail(PREVIEW_SIZE)
            self.result_preview_imgtk = ImageTk.PhotoImage(preview)

            self.root.after(0, self._on_process_done, None)
        except Exception as e:
            self.root.after(0, self._on_process_done, str(e))

    def _on_process_done(self, error):
        self.progress.stop()
        if error:
            self.status_var.set("Failed to process image.")
            messagebox.showerror("Error", f"Processing failed: {error}")
            self.result_label.config(text="Failed", image="")
            return

        self.result_label.config(image=self.result_preview_imgtk, text="")
        self.status_var.set("Done! Background removed.")
        self.save_btn.config(state="normal")

    def save_result(self):
        if self.output_image is None:
            return
        default_name = self.input_path.stem + "_no_bg.png"
        save_path = filedialog.asksaveasfilename(
            title="Save result",
            initialfile=default_name,
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")]
        )
        if save_path:
            self.output_image.save(save_path)
            self.status_var.set(f"Saved to {save_path}")
            messagebox.showinfo("Saved", f"Saved to:\n{save_path}")


def main():
    root = tkdnd.TkinterDnD.Tk()
    app = BgRemoverApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
