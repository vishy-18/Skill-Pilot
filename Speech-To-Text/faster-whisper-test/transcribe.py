"""
faster-whisper transcription test.

Records audio from the system microphone, transcribes it using
the faster-whisper library, and saves the result to transcript.txt.
"""

import os
import sys
import time

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write as write_wav
from faster_whisper import WhisperModel


# --------------- configuration ---------------
MODEL_SIZE = "base"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
AUDIO_DIR = "audio"
RECORDING_FILE = os.path.join(AUDIO_DIR, "recording.wav")
OUTPUT_FILE = "transcript.txt"
SAMPLE_RATE = 16000  # 16 kHz – what Whisper expects
# ----------------------------------------------


def record_audio(duration: int, output_path: str):
    """Record audio from the default microphone and save as WAV."""
    print(f"\n>>> Recording for {duration} seconds ... Speak now!\n")

    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
    )
    sd.wait()  # block until recording is finished

    print("Recording complete.\n")

    # Make sure the output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Save as 16-bit WAV
    write_wav(output_path, SAMPLE_RATE, audio)
    print(f"Saved recording to {output_path}")


def main():
    # 1. Ask how long to record
    try:
        duration = int(input("Enter recording duration in seconds (e.g. 5): "))
        if duration <= 0:
            raise ValueError
    except ValueError:
        print("Error: Please enter a positive whole number.")
        sys.exit(1)

    # 2. Get target language
    lang = input("Enter language code (e.g. en, ta, hi, fr) [default: en]: ").strip().lower()
    if not lang:
        lang = "en"
    print(f"Language set to: {lang}\n")

    # 3. Record from the microphone
    try:
        record_audio(duration, RECORDING_FILE)
    except Exception as e:
        print(f"Error: Could not record audio – {e}")
        print("Make sure a microphone is connected and accessible.")
        sys.exit(1)

    # 4. Load the model
    print(f"Loading model '{MODEL_SIZE}' on {DEVICE} ({COMPUTE_TYPE}) ...")
    model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    print("Model loaded.\n")

    # 5. Transcribe
    print("Transcribing ...")
    start_time = time.time()

    try:
        segments, info = model.transcribe(RECORDING_FILE, language=lang)
    except Exception as e:
        print(f"Error during transcription: {e}")
        sys.exit(1)

    # Collect all segment texts (the generator must be consumed)
    segment_texts = []
    for segment in segments:
        segment_texts.append(segment.text)

    elapsed = time.time() - start_time

    # 5. Build the full transcript
    transcript = "".join(segment_texts).strip()

    # 6. Print results
    print(f"\nDetected language : {info.language} (probability {info.language_probability:.2f})")
    print(f"Processing time   : {elapsed:.2f} seconds")
    print("-" * 50)
    print("Transcript:\n")
    print(transcript)
    print("-" * 50)

    # 7. Save to file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(transcript + "\n")

    print(f"\nTranscript saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
