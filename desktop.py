import os
import threading
from tkinter import Tk, Label, Entry, Button, Frame, Canvas, Scrollbar, filedialog, messagebox, StringVar, VERTICAL, RIGHT, Y, LEFT, BOTH
from PIL import Image, ImageOps
import numpy as np
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips, concatenate_audioclips

class App:
    def __init__(self, root):
        self.root = root
        root.title("CreateMP4")
        self.photos = []
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
        Button(pf, text="Select Photos", command=self.select_photos).pack(side=LEFT)
        Button(pf, text="Clear", command=self.clear).pack(side=LEFT, padx=8)

        Label(root, text="Photos and display time (seconds):").pack(anchor="w", padx=8, pady=(8, 0))
        container = Frame(root)
        container.pack(fill=BOTH, expand=True, padx=8, pady=4)
        self.canvas = Canvas(container, height=240)
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

    def select_photos(self):
        paths = filedialog.askopenfilenames(title="Select photos", filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.gif *.webp"), ("All", "*.*")])
        if not paths:
            return
        for child in list(self.rows_frame.children.values()):
            child.destroy()
        self.photos = []
        for p in paths:
            var = StringVar(value="7")
            self.photos.append((p, var))
        self.rebuild_rows()

    def rebuild_rows(self):
        for child in list(self.rows_frame.children.values()):
            child.destroy()
        for p, var in self.photos:
            row = Frame(self.rows_frame)
            row.pack(fill="x", pady=2)
            Label(row, text=os.path.basename(p), width=30, anchor="w").pack(side=LEFT)
            Entry(row, textvariable=var, width=8).pack(side=LEFT, padx=8)
            Button(row, text="Remove", command=lambda pp=p: self.remove_photo(pp)).pack(side=LEFT)

    def remove_photo(self, path):
        self.photos = [x for x in self.photos if x[0] != path]
        self.rebuild_rows()

    def clear(self):
        self.photos = []
        self.music_path = None
        self.music_label.config(text="No music selected")
        self.rebuild_rows()
        self.status_var.set("Ready")

    def set_status(self, text):
        self.status_var.set(text)

    def create(self):
        if not self.photos:
            messagebox.showerror("Error", "Add at least one photo.")
            return
        try:
            durations = [float(v.get()) for _, v in self.photos]
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
        self.create_btn.config(state="disabled")
        threading.Thread(target=self._run, args=(out_path, durations), daemon=True).start()

    def _run(self, out_path, durations):
        try:
            self.root.after(0, lambda: self.set_status("Loading images..."))
            imgs = [ImageOps.exif_transpose(Image.open(p)).convert("RGB") for p, _ in self.photos]
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
            self.root.after(0, lambda: self.create_btn.config(state="normal"))

if __name__ == "__main__":
    root = Tk()
    App(root)
    root.mainloop()
