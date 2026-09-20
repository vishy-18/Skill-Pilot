"""
Flask web app for testing faster-whisper transcription.

Records audio from the browser microphone, sends it to the server,
transcribes it with faster-whisper, and displays the result.
"""

import os
import time
import tempfile

from flask import Flask, render_template, request, jsonify
from faster_whisper import WhisperModel

app = Flask(__name__)

# --------------- configuration ---------------
MODEL_SIZE = "base"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
OUTPUT_FILE = "transcript.txt"
# ----------------------------------------------

# Load model once at startup
print(f"Loading faster-whisper model '{MODEL_SIZE}' on {DEVICE} ({COMPUTE_TYPE}) ...")
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
print("Model loaded and ready.\n")


@app.route("/")
def index():
    """Serve the main page."""
    return render_template("index.html")


@app.route("/transcribe", methods=["POST"])
def transcribe():
    """Receive audio blob, transcribe it, and return the result."""
    if "audio" not in request.files:
        return jsonify({"error": "No audio file received."}), 400

    audio_file = request.files["audio"]
    language = request.form.get("language", "en").strip().lower() or "en"

    # Save to a temporary file
    suffix = ".webm"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        audio_file.save(tmp.name)
        tmp.close()

        # Transcribe
        start_time = time.time()
        segments, info = model.transcribe(tmp.name, language=language)

        segment_texts = []
        for segment in segments:
            segment_texts.append(segment.text)

        elapsed = time.time() - start_time
        transcript = "".join(segment_texts).strip()

        # Save transcript to file
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(transcript + "\n")

        return jsonify({
            "transcript": transcript,
            "language": info.language,
            "language_probability": round(info.language_probability, 2),
            "processing_time": round(elapsed, 2),
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        os.unlink(tmp.name)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
