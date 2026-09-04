# Auto 15 Sec Video Maker

यह starter website image + script लेकर 15 सेकंड की 720x1280 vertical MP4 बनाती है।

## क्या चाहिए
- Python 3.10+
- FFmpeg
- OpenAI API key

## Setup

### 1. FFmpeg install करें
Ubuntu/Debian:
```bash
sudo apt update
sudo apt install ffmpeg
```

Windows पर FFmpeg install करके PATH में जोड़ें।

### 2. Python dependencies
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

### 3. API key
`.env.example` को देखकर environment variable सेट करें:
```bash
OPENAI_API_KEY=your_key
```

Linux/macOS:
```bash
export OPENAI_API_KEY="your_key"
```

Windows PowerShell:
```powershell
$env:OPENAI_API_KEY="your_key"
```

### 4. Run
```bash
python app.py
```
फिर browser में:
`http://localhost:5000`

## Video template
- 720x1280
- 15 seconds
- image पर slow zoom
- नीचे rounded caption box
- AI voice
- MP4 download

## आगे आसानी से जोड़ सकते हैं
- कई images/slideshow
- अलग-अलग voice options
- automatic subtitles
- logo/watermark
- background music
- 9:16 / 1:1 / 16:9 presets
- script को AI से 15-sec में छोटा करना
- एक साथ कई videos बनाना
- login और cloud storage
