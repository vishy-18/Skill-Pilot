# faster-whisper transcription test

A minimal script to test **faster-whisper** transcription quality.

## Setup

```bash
cd faster-whisper-test
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Usage

1. Place an audio file (mp3, wav, m4a, webm, ogg, or flac) in the `audio/` folder.
2. Run:

```bash
python transcribe.py
```

The script will:

- Load the **base** model on CPU (int8).
- Detect the language automatically.
- Print the full transcript to the console.
- Save the transcript to `transcript.txt`.
- Display the processing time.
