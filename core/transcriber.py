import whisper
import os
import requests
from pydub import AudioSegment

# Sarvam's sync STT-translate API rejects audio longer than 30s.
# We slice each chunk into 25s pieces (with a 5s safety margin) before sending.
SARVAM_PIECE_SECONDS = 25

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small").strip().lower()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
SARVAM_STT_TRANSLATE_URL = "https://api.sarvam.ai/speech-to-text-translate"
SARVAM_MODEL = os.getenv("SARVAM_STT_MODEL", "saaras:v2.5")

_model = None


def load_model():

    global _model

    if _model is None:
        print(f"Loading Whisper model: {WHISPER_MODEL} ...")
        _model = whisper.load_model(WHISPER_MODEL)
        print("Whisper model loaded.")
    return _model


def transcribe_chunk_whisper(chunk_path: str, offset_seconds: float = 0.0) -> dict:
    model = load_model()
    # fp16=False prevents CPU warning on Mac / CPU environments
    result = model.transcribe(chunk_path, task="transcribe", fp16=False)
    
    raw_text = result.get("text", "").strip()
    segments = []
    for seg in result.get("segments", []):
        start = round(seg.get("start", 0.0) + offset_seconds, 2)
        end = round(seg.get("end", 0.0) + offset_seconds, 2)
        text = seg.get("text", "").strip()
        if text:
            segments.append({
                "start": start,
                "end": end,
                "speaker": "Speaker",
                "text": text
            })
            
    return {
        "text": raw_text,
        "segments": segments
    }


def _send_to_sarvam(piece_path: str) -> str:
    """Send one ≤30s WAV file to Sarvam and return the English transcript."""
    headers = {"api-subscription-key": SARVAM_API_KEY}

    with open(piece_path, "rb") as f:
        files = {"file": (os.path.basename(piece_path), f, "audio/wav")}
        data = {"model": SARVAM_MODEL, "with_diarization": "false"}
        response = requests.post(
            SARVAM_STT_TRANSLATE_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=120,
        )

    if not response.ok:
        print(f"\n❌ Sarvam returned {response.status_code}")
        print(f"Response body: {response.text}\n")
        response.raise_for_status()

    return response.json().get("transcript", "")


def transcribe_chunk_sarvam(chunk_path: str, offset_seconds: float = 0.0) -> dict:
    """
    Sarvam sync API only accepts ≤30s audio. We split this chunk into
    25-second pieces, send each separately, and join the transcripts.
    """
    if not SARVAM_API_KEY:
        raise RuntimeError("SARVAM_API_KEY is not set in environment / .env")

    audio = AudioSegment.from_wav(chunk_path)
    piece_ms = SARVAM_PIECE_SECONDS * 1000

    full_text = ""
    segments = []
    total_pieces = (len(audio) + piece_ms - 1) // piece_ms

    for i, start_ms in enumerate(range(0, len(audio), piece_ms)):
        piece = audio[start_ms:start_ms + piece_ms]
        piece_path = f"{chunk_path}_sv_{i}.wav"
        piece.export(piece_path, format="wav")

        piece_start = round(offset_seconds + (start_ms / 1000.0), 2)
        piece_end = round(offset_seconds + (min(len(audio), start_ms + piece_ms) / 1000.0), 2)

        try:
            print(f"  → Sarvam piece {i + 1}/{total_pieces} ...")
            piece_text = _send_to_sarvam(piece_path).strip()
            if piece_text:
                full_text += piece_text + " "
                segments.append({
                    "start": piece_start,
                    "end": piece_end,
                    "speaker": "Speaker",
                    "text": piece_text
                })
        finally:
            if os.path.exists(piece_path):
                os.remove(piece_path)

    return {
        "text": full_text.strip(),
        "segments": segments
    }


def transcribe_chunk(chunk_path: str, language: str = "english", offset_seconds: float = 0.0) -> dict:
    """
    Route one chunk to Whisper or Sarvam depending on language choice.
    - english  → Whisper (local model)
    - hinglish → Sarvam (translates to English while transcribing)
    """
    if language.lower() == "hinglish":
        return transcribe_chunk_sarvam(chunk_path, offset_seconds=offset_seconds)
    return transcribe_chunk_whisper(chunk_path, offset_seconds=offset_seconds)


def transcribe_all(chunks: list, language: str = "english") -> dict:
    full_transcript = ""
    all_segments = []

    engine = "Sarvam AI" if language.lower() == "hinglish" else "Whisper"
    print(f"Using {engine} for transcription.")

    # Each chunk is at most 10 minutes (600s)
    chunk_duration_seconds = 600.0

    for i, chunk in enumerate(chunks):
        offset = i * chunk_duration_seconds
        print(f"Transcribing chunk {i + 1}/{len(chunks)} (offset {offset}s)...")

        chunk_res = transcribe_chunk(chunk, language=language, offset_seconds=offset)
        if isinstance(chunk_res, dict):
            text = chunk_res.get("text", "")
            all_segments.extend(chunk_res.get("segments", []))
        else:
            text = str(chunk_res)

        full_transcript += text + " "

    print("Transcription complete.")

    return {
        "text": full_transcript.strip(),
        "segments": all_segments
    }
