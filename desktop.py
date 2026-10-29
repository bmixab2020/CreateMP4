import os
import threading
from tkinter import Tk, Label, Entry, Button, Frame, Canvas, Scrollbar, filedialog, messagebox, StringVar, VERTICAL, RIGHT, Y, LEFT, BOTH, TOP
from PIL import Image, ImageOps
import numpy as np
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips, concatenate_audioclips

class PhotoRow:
    def __init__(self, parent, remove_cb):
        self.parent = parent
        self.remove_cb = remove_cb
        self.path = None
        self.time_var = StringVar(value="7")
        self.frame = Frame(parent)
        self.frame.pack(fill="x", pady=2)
        self.name_label = Label(self.frame, text="No file selected", width=32, anchor="w")
        self.name_label.pack(side=LEFT)
        Button(self.frame, text="Browse", command=self.browse).pack(side=LEFT, padx=4)
        Entry(self.frame, textvariable=self.time_var, width=8).pack(side=LEFT, padx=4)
        Button(self.frame, text="Remove", command=self.remove).pack(side=LEFT, padx=4)

    def browse(self):
        path = filedialog.askopenfilename(title="Select photo", filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.gif *.webp"), ("All", "*.*")])
        if path:
            self.path = path
            self.name_label.config(text=os.path.basename(path))

    def remove(self):
        self.frame.destroy()
        self.remove_cb(self)

class App:
    def __init__(self, root):
        self.root = root
        root.title("CreateMP4")
        self.rows = []
        self.music_path = None

        Label(root, text="Video name:").pack(anchor="w", padx=8, pady=(8, 0))
        self.name_var = StringVar(value="video")
        Entry(root, textvariable=self.name_var, width=40).pack(fill="x", padx=8)

        mf = Frame(root)
        mf.pack(fill="x", padx=8, pady=8)
        Button(mf, text="Select Music (mp3)", command=self.select_music).pack(side=LEFT)
        self.music_label = Label(mf, text="No music selected")
        self.music_label.pack(side=LEFT, padx=8)

        pf = Frame(root)
        pf.pack(fill="x", padx=8)
        Button(pf, text="Add photo row", command=self.add_row).pack(side=LEFT)
        Button(pf, text="Select photos (multiple)", command=self.select_photos).pack(side=LEFT, padx=8)
        Button(pf, text="Clear", command=self.clear).pack(side=LEFT, padx=8)

        Label(root, text="Photos and display time (seconds):").pack(anchor="w", padx=8, pady=(8, 0))
        container = Frame(root)
        container.pack(fill=BOTH, expand=True, padx=8, pady=4)
        self.canvas = Canvas(container, height=260)
        sb = Scrollbar(container, orient=VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=RIGHT, fill=Y)
        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.rows_frame = Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.rows_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.status_var = StringVar(value="Ready")
        Label(root, textvariable=self.status_var).pack(anchor="w", padx=8, pady=4)

        self.create_btn = Button(root, text="Create Video", command=self.create)
        self.create_btn.pack(pady=8)

    def select_music(self):
        path = filedialog.askopenfilename(title="Select music", filetypes=[("Audio", "*.mp3 *.wav *.m4a"), ("All", "*.*")])
        if path:
            self.music_path = path
            self.music_label.config(text=os.path.basename(path))

    def add_row(self):
        row = PhotoRow(self.rows_frame, self.remove_row)
        self.rows.append(row)

    def remove_row(self, row):
        if row in self.rows:
            self.rows.remove(row)

    def select_photos(self):
        paths = filedialog.askopenfilenames(title="Select photos", filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.gif *.webp"), ("All", "*.*")])
        if not paths:
            return
        for p in paths:
            row = PhotoRow(self.rows_frame, self.remove_row)
            row.path = p
            row.name_label.config(text=os.path.basename(p))
            self.rows.append(row)

    def clear(self):
        for row in list(self.rows):
            row.frame.destroy()
        self.rows = []
        self.music_path = None
        self.music_label.config(text="No music selected")
        self.status_var.set("Ready")

    def set_status(self, text):
        self.status_var.set(text)

    def _set_all_state(self, state):
        def recurse(w):
            try:
                w.config(state=state)
            except Exception:
                pass
            for c in w.winfo_children():
                recurse(c)
        recurse(self.root)

    def create(self):
        valid = [r for r in self.rows if r.path]
        if not valid:
            messagebox.showerror("Error", "Add at least one photo.")
            return
        try:
            durations = [float(r.time_var.get()) for r in valid]
        except ValueError:
            messagebox.showerror("Error", "Invalid time value.")
            return
        if any(d <= 0 for d in durations):
            messagebox.showerror("Error", "Times must be > 0.")
            return
        out_path = filedialog.asksaveasfilename(title="Save video", defaultextension=".mp4", filetypes=[("MP4", "*.mp4")], initialfile=(self.name_var.get().strip() or "video") + ".mp4")
        if not out_path:
            return
        if not out_path.lower().endswith(".mp4"):
            out_path += ".mp4"
        self._set_all_state("disabled")
        threading.Thread(target=self._run, args=(out_path, valid, durations), daemon=True).start()

    def _run(self, out_path, rows, durations):
        try:
            self.root.after(0, lambda: self.set_status("Loading images..."))
            imgs = [ImageOps.exif_transpose(Image.open(r.path)).convert("RGB") for r in rows]
            all_portrait = all(im.width < im.height for im in imgs)
            if all_portrait:
                canvas_w, canvas_h = 1080, 1920
            else:
                canvas_w, canvas_h = 1920, 1080
            canvas_w = canvas_w - (canvas_w % 2)
            canvas_h = canvas_h - (canvas_h % 2)

            def fit(im):
                scale = min(canvas_w / im.width, canvas_h / im.height)
                nw = int(im.width * scale)
                nh = int(im.height * scale)
                nw = nw - (nw % 2)
                nh = nh - (nh % 2)
                resized = im.resize((nw, nh), Image.LANCZOS)
                canvas = Image.new("RGB", (canvas_w, canvas_h), (0, 0, 0))
                canvas.paste(resized, ((canvas_w - nw) // 2, (canvas_h - nh) // 2))
                return canvas

            self.root.after(0, lambda: self.set_status("Building clips..."))
            clips = []
            for im, dur in zip(imgs, durations):
                frame = fit(im)
                arr = np.array(frame)
                clips.append(ImageClip(arr).with_duration(dur))
            video = concatenate_videoclips(clips, method="compose")

            if self.music_path:
                self.root.after(0, lambda: self.set_status("Adding audio..."))
                audio = AudioFileClip(self.music_path)
                if audio.duration < video.duration:
                    n = int(video.duration // audio.duration) + 1
                    audio = concatenate_audioclips([audio] * n).subclipped(0, video.duration)
                else:
                    audio = audio.subclipped(0, video.duration)
                video = video.with_audio(audio)

            self.root.after(0, lambda: self.set_status("Encoding video..."))
            video.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac", threads=4, preset="ultrafast", logger=None)
            video.close()
            self.root.after(0, lambda: self.set_status("Done: " + out_path))
            self.root.after(0, lambda: messagebox.showinfo("Done", "Saved to\n" + out_path))
        except Exception as e:
            self.root.after(0, lambda: self.set_status("Error: " + str(e)))
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.root.after(0, lambda: self._set_all_state("normal"))

if __name__ == "__main__":
    root = Tk()
    App(root)
    root.mainloop()
