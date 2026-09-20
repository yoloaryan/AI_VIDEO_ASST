import os
import requests
from pydub import AudioSegment

# ============================================================
# CONFIGURATION
# ============================================================

# Sarvam sync API accepts audio <= 30 seconds.
# 25 seconds gives us a safety margin.
SARVAM_PIECE_SECONDS = 25

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

SARVAM_STT_TRANSLATE_URL = ("https://api.sarvam.ai/speech-to-text-translate")

SARVAM_MODEL = os.getenv("SARVAM_STT_MODEL", "saaras:v2.5")

# ============================================================
# TRANSCRIPTION ENGINE
# ============================================================

# Options:
#
# sarvam  -> always use Sarvam
# whisper  -> always use local Whisper
# auto     -> Sarvam when API key exists, otherwise Whisper
#
# Railway should use "sarvam" to avoid loading Whisper
# into container memory.

TRANSCRIPTION_ENGINE = os.getenv("TRANSCRIPTION_ENGINE",
                                 "sarvam").strip().lower()

# ============================================================
# WHISPER
# ============================================================

_model = None


def load_whisper_model():

    global _model

    if _model is None:

        print("[Whisper] Loading Whisper model...")

        import whisper

        _model = whisper.load_model(os.getenv("WHISPER_MODEL", "tiny"))

        print("[Whisper] Whisper model loaded.")

    return _model


# ============================================================
# WHISPER TRANSCRIPTION
# ============================================================


def transcribe_chunk_whisper(chunk_path: str,
                             offset_seconds: float = 0.0) -> dict:

    model = load_whisper_model()

    print(f"[Whisper] Transcribing: {chunk_path}")

    result = model.transcribe(chunk_path, task="transcribe", fp16=False)

    raw_text = (result.get("text", "").strip())

    segments = []

    for seg in result.get("segments", []):

        start = round(seg.get("start", 0.0) + offset_seconds, 2)

        end = round(seg.get("end", 0.0) + offset_seconds, 2)

        text = (seg.get("text", "").strip())

        if text:

            segments.append({
                "start": start,
                "end": end,
                "speaker": "Speaker",
                "text": text,
            })

    return {
        "text": raw_text,
        "segments": segments,
    }


# ============================================================
# SARVAM API
# ============================================================


def _send_to_sarvam(piece_path: str) -> str:

    if not SARVAM_API_KEY:

        raise RuntimeError("SARVAM_API_KEY is not configured.")

    headers = {"api-subscription-key": SARVAM_API_KEY}

    with open(piece_path, "rb") as f:

        files = {"file": (os.path.basename(piece_path), f, "audio/wav")}

        data = {
            "model": SARVAM_MODEL,
            "with_diarization": "false",
        }

        response = requests.post(
            SARVAM_STT_TRANSLATE_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=120,
        )

    if not response.ok:

        print("[Sarvam] API error: "
              f"{response.status_code}")

        print(f"[Sarvam] Response: "
              f"{response.text}")

        response.raise_for_status()

    result = response.json()

    return (result.get("transcript", "") or "")


# ============================================================
# SARVAM TRANSCRIPTION
# ============================================================


def transcribe_chunk_sarvam(chunk_path: str,
                            offset_seconds: float = 0.0) -> dict:

    if not SARVAM_API_KEY:

        raise RuntimeError("SARVAM_API_KEY is not configured. "
                           "Set SARVAM_API_KEY in Railway Variables.")

    print("[Sarvam] Preparing audio:"
          f" {chunk_path}")

    audio = AudioSegment.from_wav(chunk_path)

    piece_ms = (SARVAM_PIECE_SECONDS * 1000)

    full_text = ""
    segments = []

    total_pieces = (len(audio) + piece_ms - 1) // piece_ms

    for i, start_ms in enumerate(range(0, len(audio), piece_ms)):

        piece = audio[start_ms:start_ms + piece_ms]

        piece_path = (f"{chunk_path}_sv_{i}.wav")

        piece.export(piece_path, format="wav")

        piece_start = round(offset_seconds + (start_ms / 1000.0), 2)

        piece_end = round(
            offset_seconds + (min(len(audio), start_ms + piece_ms) / 1000.0),
            2)

        try:

            print("[Sarvam] "
                  f"Processing piece "
                  f"{i + 1}/{total_pieces}...")

            piece_text = (_send_to_sarvam(piece_path).strip())

            if piece_text:

                full_text += (piece_text + " ")

                segments.append({
                    "start": piece_start,
                    "end": piece_end,
                    "speaker": "Speaker",
                    "text": piece_text,
                })

        finally:

            if os.path.exists(piece_path):

                os.remove(piece_path)

    return {
        "text": full_text.strip(),
        "segments": segments,
    }


# ============================================================
# TRANSCRIPTION ROUTER
# ============================================================


def transcribe_chunk(chunk_path: str,
                     language: str = "english",
                     offset_seconds: float = 0.0) -> dict:

    engine = TRANSCRIPTION_ENGINE

    print("[Transcription] "
          f"Engine: {engine}")

    # --------------------------------------------------------
    # SARVAM
    # --------------------------------------------------------

    if engine == "sarvam":

        return transcribe_chunk_sarvam(chunk_path, offset_seconds)

    # --------------------------------------------------------
    # WHISPER
    # --------------------------------------------------------

    if engine == "whisper":

        return transcribe_chunk_whisper(chunk_path, offset_seconds)

    # --------------------------------------------------------
    # AUTO
    # --------------------------------------------------------

    if engine == "auto":

        if SARVAM_API_KEY:

            print("[Transcription] "
                  "SARVAM_API_KEY detected. "
                  "Using Sarvam.")

            return transcribe_chunk_sarvam(chunk_path, offset_seconds)

        print("[Transcription] "
              "SARVAM_API_KEY unavailable. "
              "Falling back to Whisper.")

        return transcribe_chunk_whisper(chunk_path, offset_seconds)

    raise RuntimeError("Invalid TRANSCRIPTION_ENGINE: "
                       f"{engine}. Use sarvam, whisper, or auto.")


# ============================================================
# TRANSCRIBE ALL CHUNKS
# ============================================================


def transcribe_all(chunks: list, language: str = "english") -> dict:

    full_transcript = ""

    all_segments = []

    print("=" * 60)

    print("[Transcription] "
          f"Engine: {TRANSCRIPTION_ENGINE}")

    print(f"[Transcription] "
          f"Chunks: {len(chunks)}")

    print("=" * 60)

    # Each audio chunk is at most 10 minutes.
    chunk_duration_seconds = 600.0

    for i, chunk in enumerate(chunks):

        offset = (i * chunk_duration_seconds)

        print("[Transcription] "
              f"Transcribing chunk "
              f"{i + 1}/{len(chunks)} "
              f"(offset {offset}s)...")

        chunk_res = transcribe_chunk(chunk,
                                     language=language,
                                     offset_seconds=offset)

        if isinstance(chunk_res, dict):

            text = (chunk_res.get("text", ""))

            all_segments.extend(chunk_res.get("segments", []))

        else:

            text = str(chunk_res)

        if text:

            full_transcript += (text + " ")

    print("[Transcription] "
          "Transcription complete.")

    return {
        "text": full_transcript.strip(),
        "segments": all_segments,
    }
