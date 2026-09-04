import os, uuid, subprocess, textwrap, shutil
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from PIL import Image, ImageDraw, ImageFont
import requests

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"
OUTPUTS = BASE / "outputs"
TMP = BASE / "tmp"
for p in (UPLOADS, OUTPUTS, TMP):
    p.mkdir(exist_ok=True)

app = Flask(__name__)

W, H = 720, 1280
DURATION = 15

def font_path():
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    return next((p for p in candidates if os.path.exists(p)), None)

def make_caption_png(text, out):
    font_file = font_path()
    font = ImageFont.truetype(font_file, 42) if font_file else ImageFont.load_default()
    # Rough wrapping for a 720px vertical-short layout.
    lines = textwrap.wrap(text.replace("\n", " "), width=27, break_long_words=False)
    lines = lines[:4]
    pad_x, pad_y = 34, 24
    line_h = 58
    box_h = pad_y * 2 + line_h * len(lines)
    img = Image.new("RGBA", (W, box_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((12, 8, W-12, box_h-8), radius=24, fill=(0,0,0,205))
    y = pad_y
    for line in lines:
        bbox = d.textbbox((0,0), line, font=font)
        tw = bbox[2] - bbox[0]
        d.text(((W-tw)//2, y), line, font=font, fill="white")
        y += line_h
    img.save(out)

def make_video(image_path, script, output_path):
    job = uuid.uuid4().hex
    work = TMP / job
    work.mkdir(parents=True, exist_ok=True)
    audio = work / "voice.mp3"
    caption = work / "caption.png"

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    model = os.getenv("TTS_MODEL", "gpt-4o-mini-tts")
    voice = os.getenv("VOICE", "alloy")

    r = requests.post(
        "https://api.openai.com/v1/audio/speech",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "voice": voice, "input": script, "response_format": "mp3"},
        timeout=120,
    )
    if r.status_code != 200:
        raise RuntimeError(f"TTS API error: {r.status_code} {r.text[:500]}")
    audio.write_bytes(r.content)

    make_caption_png(script, caption)

    # 720x1280 vertical, 15 seconds, gentle Ken Burns zoom, caption at bottom.
    vf = (
        "scale=720:1280:force_original_aspect_ratio=increase,"
        "crop=720:1280,"
        "zoompan=z='min(zoom+0.0008,1.10)':"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        "d=450:s=720x1280:fps=30,"
        "setsar=1,"
        "format=yuv420p"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image_path),
        "-i", str(audio),
        "-loop", "1", "-i", str(caption),
        "-filter_complex",
        f"[0:v]{vf}[bg];"
        f"[2:v]scale=720:-1[cap];"
        f"[bg][cap]overlay=0:H-h-90:enable='between(t,0,15)'[v]",
        "-map", "[v]", "-map", "1:a:0",
        "-t", str(DURATION),
        "-r", "30",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    shutil.rmtree(work, ignore_errors=True)

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/generate")
def generate():
    if "image" not in request.files:
        return jsonify(error="Image upload required."), 400
    image = request.files["image"]
    script = request.form.get("script", "").strip()
    if not script:
        return jsonify(error="Script required."), 400

    ext = Path(image.filename or ".jpg").suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        return jsonify(error="Use JPG, PNG or WEBP."), 400

    job = uuid.uuid4().hex
    image_path = UPLOADS / f"{job}{ext}"
    output_name = f"short_{job}.mp4"
    output_path = OUTPUTS / output_name
    image.save(image_path)

    try:
        make_video(image_path, script, output_path)
    except FileNotFoundError:
        return jsonify(error="FFmpeg is not installed or not in PATH."), 500
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        image_path.unlink(missing_ok=True)

    return jsonify(download=f"/download/{output_name}")

@app.get("/download/<name>")
def download(name):
    return send_from_directory(OUTPUTS, name, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
