from flask import Flask, request, send_file, render_template, jsonify
import os, uuid, shutil
from werkzeug.utils import secure_filename
from PIL import Image
import numpy as np
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips, concatenate_audioclips

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD = os.path.join(BASE, "uploads")
OUTPUT = os.path.join(BASE, "outputs")
os.makedirs(UPLOAD, exist_ok=True)
os.makedirs(OUTPUT, exist_ok=True)

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/create", methods=["POST"])
def create():
    photos = request.files.getlist("photos")
    times = request.form.getlist("times")
    music = request.files.get("music")
    if not photos or not times or len(photos) != len(times):
        return jsonify({"error": "photos and times count mismatch"}), 400
    try:
        durations = [float(t) for t in times]
    except ValueError:
        return jsonify({"error": "invalid time value"}), 400
    if any(d <= 0 for d in durations):
        return jsonify({"error": "times must be > 0 ms"}), 400

    job = uuid.uuid4().hex
    jobdir = os.path.join(UPLOAD, job)
    os.makedirs(jobdir)
    try:
        photo_paths = []
        for f in photos:
            if not f or not f.filename:
                return jsonify({"error": "missing photo file"}), 400
            p = os.path.join(jobdir, secure_filename(f.filename))
            f.save(p)
            photo_paths.append(p)

        video_name = (request.form.get('videoname') or '').strip()
        music_path = None
        if music and music.filename:
            music_path = os.path.join(jobdir, secure_filename(music.filename))
            music.save(music_path)

        imgs = [Image.open(p).convert("RGB") for p in photo_paths]
        w, h = imgs[0].size
        scale = min(1920 / w, 1080 / h, 1.0)
        w = int(w * scale)
        h = int(h * scale)
        w = w - (w % 2)
        h = h - (h % 2)
        if w == 0 or h == 0:
            raise ValueError("invalid image size")

        clips = []
        for im, dur in zip(imgs, durations):
            resized = im.resize((w, h), Image.LANCZOS)
            arr = np.array(resized)
            clips.append(ImageClip(arr).with_duration(dur))
        video = concatenate_videoclips(clips, method="compose")

        if music_path:
            audio = AudioFileClip(music_path)
            if audio.duration < video.duration:
                n = int(video.duration // audio.duration) + 1
                audio = concatenate_audioclips([audio] * n).subclipped(0, video.duration)
            else:
                audio = audio.subclipped(0, video.duration)
            video = video.with_audio(audio)

        if video_name:
            safe = secure_filename(video_name)
            if not safe:
                safe = job
            if not safe.lower().endswith('.mp4'):
                safe = safe + '.mp4'
            outname = safe
        else:
            outname = job + '.mp4'
        outpath = os.path.join(OUTPUT, outname)
        video.write_videofile(outpath, fps=24, codec="libx264", audio_codec="aac", threads=4, preset="ultrafast", logger=None)
        video.close()
        shutil.rmtree(jobdir, ignore_errors=True)
        return jsonify({"download": "/download/" + outname})
    except Exception as e:
        shutil.rmtree(jobdir, ignore_errors=True)
        return jsonify({"error": str(e)}), 500

@app.route("/download/<filename>")
def download(filename):
    path = os.path.join(OUTPUT, secure_filename(filename))
    if not os.path.exists(path):
        return "not found", 404
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
