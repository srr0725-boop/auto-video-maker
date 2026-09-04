import os, uuid, subprocess, shutil
from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont
import requests
import imageio_ffmpeg

app = Flask(__name__)
UPLOADS, OUTPUTS = "uploads", "outputs"
os.makedirs(UPLOADS, exist_ok=True)
os.makedirs(OUTPUTS, exist_ok=True)

W, H, FPS, SECS = 720, 1280, 30, 15
BG = (187, 235, 78)  # close to the reference green

def devanagari_font(size, bold=True):
    paths = [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-ExtraCondensedBlack.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-CondensedBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)

def latin_font(size, bold=True):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(p, size)

def fit_lines(draw, text, fnt, width, max_lines=3):
    # Keep user script intact; wrap it for the 720px canvas.
    words = text.split()
    lines, cur = [], ""
    for word in words:
        candidate = (cur + " " + word).strip()
        if draw.textbbox((0,0), candidate, font=fnt)[2] <= width:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if len(lines) <= max_lines:
        return lines
    # Reduce font size upstream by returning first max lines; normally scripts fit.
    return lines[:max_lines]

def draw_alarm(draw, x=18, y=385, scale=1.0, number=15):
    # Original simple alarm illustration (not copied from the source video).
    r = int(92*scale)
    cx, cy = x+r, y+r+12
    draw.ellipse((x, y+45, x+2*r, y+45+2*r), fill=(235,25,35), outline=(25,25,25), width=4)
    draw.ellipse((x+14, y+59, x+2*r-14, y+59+2*r-28), fill=(250,250,250), outline=(30,150,70), width=10)
    draw.ellipse((x+32, y+77, x+2*r-32, y+77+2*r-64), fill=(245,245,245), outline=(230,30,40), width=4)
    # bells
    draw.ellipse((x+5,y+10,x+68,y+58), fill=(235,25,35), outline=(25,25,25), width=4)
    draw.ellipse((x+2*r-68,y+10,x+2*r-5,y+58), fill=(235,25,35), outline=(25,25,25), width=4)
    draw.line((x+48,y+28,x+28,y+2), fill=(30,30,30), width=7)
    draw.line((x+2*r-48,y+28,x+2*r-28,y+2), fill=(30,30,30), width=7)
    # hands
    draw.line((cx,cy,cx,cy-48), fill=(20,20,20), width=6)
    draw.line((cx,cy,cx+34,cy+25), fill=(20,20,20), width=6)
    nf = latin_font(64, True)
    s = str(max(0, number))
    b = draw.textbbox((0,0), s, font=nf)
    draw.text((cx-(b[2]-b[0])/2, cy-(b[3]-b[1])/2-5), s, font=nf, fill=(230,25,35))
    # feet
    draw.line((x+32,y+2*r+42,x+15,y+2*r+67), fill=(25,25,25), width=8)
    draw.line((x+2*r-32,y+2*r+42,x+2*r-15,y+2*r+67), fill=(25,25,25), width=8)

def draw_footer(draw):
    f = latin_font(48, True)
    text = "LIKE + FOLLOW"
    # white outline, pink fill
    b = draw.textbbox((0,0), text, font=f)
    x, y = 5, 1197
    for ox in (-4,-2,0,2,4):
        for oy in (-4,-2,0,2,4):
            draw.text((x+ox,y+oy), text, font=f, fill=(255,255,255))
    draw.text((x,y), text, font=f, fill=(245,95,175))

def draw_horse(draw):
    # Simple original decorative horse glyph.
    f = latin_font(76, True)
    draw.text((340,1168), "♞", font=f, fill=(20,30,40))

def make_frame(img_path, script, i, path):
    im = Image.new("RGB", (W,H), BG)
    d = ImageDraw.Draw(im)

    # Header closely follows the reference layout.
    hf = latin_font(70, True)
    header = "GK QUESTION"
    hb = d.textbbox((0,0), header, font=hf)
    d.text(((W-(hb[2]-hb[0]))/2, 8), header, font=hf, fill=(240,0,0))

    # Question block
    qf = devanagari_font(39, True)
    lines = fit_lines(d, script.strip(), qf, 675, 3)
    y = 148
    for line in lines:
        b = d.textbbox((0,0), line, font=qf)
        x = (W-(b[2]-b[0]))/2
        # subtle white edge similar to the reference text
        d.text((x+2,y+2), line, font=qf, fill=(255,255,255))
        d.text((x,y), line, font=qf, fill=(20,0,180))
        y += 61

    # Uploaded image. It is fitted into the same lower-middle zone.
    src = Image.open(img_path).convert("RGBA")
    maxw, maxh = 430, 760
    scale = min(maxw/src.width, maxh/src.height)
    nw, nh = max(1,int(src.width*scale)), max(1,int(src.height*scale))
    # tiny movement so the video is not a dead still
    pulse = 1.0 + 0.025 * ((i % 90)/90.0)
    nw2, nh2 = int(nw*pulse), int(nh*pulse)
    src = src.resize((nw2,nh2), Image.Resampling.LANCZOS)
    x = (W-nw2)//2
    y_img = max(350, min(400, H-100-nh2))
    im.paste(src, (x,y_img), src)

    # Countdown alarm appears on left for the first 12 seconds.
    remain = max(0, 15-int(i/FPS))
    if i < 13*FPS:
        draw_alarm(d, 15, 385, 0.9, remain)

    draw_footer(d)
    draw_horse(d)
    im.save(path, quality=94)

def make_tts(text, out_path):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return False
    r = requests.post(
        "https://api.openai.com/v1/audio/speech",
        headers={"Authorization": "Bearer "+key, "Content-Type":"application/json"},
        json={"model":"gpt-4o-mini-tts","voice":"alloy","input":text,"format":"mp3"},
        timeout=120
    )
    if r.status_code >= 400:
        raise RuntimeError(r.text[:500])
    with open(out_path,"wb") as f:
        f.write(r.content)
    return True

@app.route("/")
def home():
    return render_template("index.html")

@app.post("/generate")
def generate():
    image = request.files.get("image")
    script = request.form.get("script","").strip()
    if not image or not script:
        return jsonify(error="Image और script दोनों डालना जरूरी है।"), 400

    job = uuid.uuid4().hex
    ext = os.path.splitext(image.filename)[1].lower() or ".png"
    img_path = os.path.join(UPLOADS, job+ext)
    image.save(img_path)

    frames = os.path.join(UPLOADS, job+"_frames")
    os.makedirs(frames)
    for i in range(SECS*FPS):
        make_frame(img_path, script, i, os.path.join(frames, f"{i:04d}.jpg"))

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    silent = os.path.join(OUTPUTS, job+"_silent.mp4")
    final = os.path.join(OUTPUTS, job+".mp4")

    subprocess.run([
        ff,"-y","-framerate",str(FPS),"-i",os.path.join(frames,"%04d.jpg"),
        "-c:v","libx264","-preset","veryfast","-pix_fmt","yuv420p",
        "-r",str(FPS),"-t",str(SECS),"-movflags","+faststart",silent
    ], check=True)

    audio = os.path.join(OUTPUTS, job+".mp3")
    has_audio = False
    try:
        has_audio = make_tts(script, audio)
    except Exception:
        has_audio = False

    if has_audio:
        subprocess.run([
            ff,"-y","-i",silent,"-i",audio,
            "-c:v","copy","-c:a","aac","-b:a","128k",
            "-t",str(SECS),"-shortest","-movflags","+faststart",final
        ], check=True)
        os.remove(silent)
        os.remove(audio)
    else:
        os.replace(silent, final)

    shutil.rmtree(frames, ignore_errors=True)
    try: os.remove(img_path)
    except OSError: pass
    return jsonify(download="/download/"+job)

@app.get("/download/<job>")
def download(job):
    p = os.path.join(OUTPUTS, job+".mp4")
    if not os.path.exists(p):
        return "Video नहीं मिला", 404
    return send_file(p, as_attachment=True, download_name="GK_15sec_video.mp4", mimetype="video/mp4")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT","5000")))
