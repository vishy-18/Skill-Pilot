"""Shared faster-whisper integration for assessment and the speech demo."""
from __future__ import annotations

import os
import tempfile
from typing import Any

_MODEL: Any = None


def _get_model() -> Any:
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel

        _MODEL = WhisperModel(
            os.getenv("WHISPER_MODEL", "base"),
            device=os.getenv("WHISPER_DEVICE", "cpu"),
            compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
        )
    return _MODEL


def transcribe_audio(audio_bytes: bytes, language: str = "en") -> dict[str, Any]:
    """Transcribe browser audio with the existing local faster-whisper model."""
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            tmp_path = tmp.name
            tmp.write(audio_bytes)
        segments, info = _get_model().transcribe(tmp_path, language=language or "en")
        return {
            "transcript": "".join(segment.text for segment in segments).strip(),
            "language": info.language,
            "language_probability": round(info.language_probability, 2),
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
