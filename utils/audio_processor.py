import os
import re

from typing import Optional
from urllib.parse import (urlparse, parse_qs)

import yt_dlp

from pydub import AudioSegment

# ============================================================
# CONFIGURATION
# ============================================================

DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ============================================================
# YOUTUBE VIDEO ID
# ============================================================


def extract_youtube_video_id(url: str) -> str:

    url = url.strip()

    try:

        parsed = urlparse(url)

        hostname = (parsed.hostname or "").lower()

        # ----------------------------------------------------
        # youtu.be
        # ----------------------------------------------------

        if hostname in ("youtu.be", "www.youtu.be"):

            return parsed.path.lstrip("/")[:11]

        # ----------------------------------------------------
        # youtube.com
        # ----------------------------------------------------

        if hostname in ("youtube.com", "www.youtube.com", "m.youtube.com"):

            # /watch?v=VIDEO_ID

            if parsed.path == "/watch":

                return parse_qs(parsed.query).get("v", [""])[0][:11]

            # /embed/VIDEO_ID
            # /v/VIDEO_ID
            # /shorts/VIDEO_ID

            if parsed.path.startswith(("/embed/", "/v/", "/shorts/")):

                parts = parsed.path.split("/")

                if len(parts) >= 3:

                    return parts[2][:11]

    except Exception as e:

        print(f"Video ID parsing error: {e}")

    # --------------------------------------------------------
    # Regex fallback
    # --------------------------------------------------------

    match = re.search(
        r"(?:v=|\/|embed\/|youtu\.be\/|\/v\/|\/shorts\/)"
        r"([0-9A-Za-z_-]{11})", url)

    if match:

        return match.group(1)

    return ""


# ============================================================
# PROXY
# ============================================================


def get_youtube_proxy() -> Optional[str]:
    """
    Only use an explicitly configured YOUTUBE_PROXY.

    We intentionally do NOT automatically use generic
    HTTP_PROXY / HTTPS_PROXY environment variables.
    """

    proxy = os.getenv("YOUTUBE_PROXY", "").strip()

    if proxy:

        print("[YouTube Config] "
              "Explicit YOUTUBE_PROXY configured.")

        return proxy

    print("[YouTube Config] "
          "No YOUTUBE_PROXY configured. "
          "Using direct connection.")

    return None


# ============================================================
# DIRECT YOUTUBE TRANSCRIPT
# ============================================================


def fetch_youtube_transcript(url: str,
                             language: str = "english") -> Optional[dict]:
    """
    Try to retrieve an existing YouTube transcript.

    If transcript extraction fails, return None so the
    pipeline can fall back to yt-dlp.
    """

    video_id = extract_youtube_video_id(url)

    if not video_id:

        print("Could not extract YouTube video ID.")

        return None

    print(f"Attempting transcript for video: {video_id}")

    try:

        from youtube_transcript_api import (YouTubeTranscriptApi)

        proxy = get_youtube_proxy()

        proxies = None

        if proxy:

            proxies = {"http": proxy, "https": proxy}

        transcript_snippets = None

        # ====================================================
        # LANGUAGE PREFERENCE
        # ====================================================

        if language.lower() in ["hinglish", "hindi"]:

            languages = ["hi", "en", "en-US", "en-GB"]

        else:

            languages = ["en", "en-US", "en-GB", "hi"]

        # ====================================================
        # METHOD 1 — NEW API
        # ====================================================

        try:

            if proxies:

                api = YouTubeTranscriptApi(proxies=proxies)

            else:

                api = YouTubeTranscriptApi()

            if hasattr(api, "fetch"):

                try:

                    transcript_snippets = (api.fetch(video_id,
                                                     languages=languages))

                except TypeError:

                    transcript_snippets = (api.fetch(video_id))

            elif hasattr(api, "list"):

                transcript_list = api.list(video_id)

                transcript = (transcript_list.find_transcript(languages))

                transcript_snippets = (transcript.fetch())

        except Exception as e:

            print("Transcript API method 1 "
                  f"failed: {e}")

        # ====================================================
        # METHOD 2 — LEGACY API
        # ====================================================

        if not transcript_snippets:

            try:

                if hasattr(YouTubeTranscriptApi, "get_transcript"):

                    if proxies:

                        transcript_snippets = (
                            YouTubeTranscriptApi.get_transcript(
                                video_id, languages=languages,
                                proxies=proxies))

                    else:

                        transcript_snippets = (
                            YouTubeTranscriptApi.get_transcript(
                                video_id, languages=languages))

            except Exception as e:

                print("Transcript API method 2 "
                      f"failed: {e}")

        # ====================================================
        # NO TRANSCRIPT
        # ====================================================

        if not transcript_snippets:

            print("No direct YouTube transcript available.")

            return None

        # ====================================================
        # BUILD TRANSCRIPT
        # ====================================================

        full_text = []

        segments = []

        for snippet in transcript_snippets:

            # ------------------------------------------------
            # Dictionary format
            # ------------------------------------------------

            if isinstance(snippet, dict):

                text = snippet.get("text", "").strip()

                start = round(float(snippet.get("start", 0.0)), 2)

                duration = round(float(snippet.get("duration", 0.0)), 2)

            # ------------------------------------------------
            # Object format
            # ------------------------------------------------

            else:

                text = getattr(snippet, "text", "").strip()

                start = round(float(getattr(snippet, "start", 0.0)), 2)

                duration = round(float(getattr(snippet, "duration", 0.0)), 2)

            if text:

                full_text.append(text)

                segments.append({
                    "start": start,
                    "end": round(start + duration, 2),
                    "speaker": "Speaker",
                    "text": text
                })

        if not full_text:

            return None

        result = {"text": " ".join(full_text), "segments": segments}

        print("Direct YouTube transcript "
              "successfully extracted.")

        return result

    except Exception as e:

        print("Direct transcript extraction "
              f"failed for {video_id}: {e}")

        return None


# ============================================================
# YT-DLP OPTIONS
# ============================================================


def get_ytdlp_options(download: bool = False) -> dict:

    proxy = get_youtube_proxy()

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 2,
        "fragment_retries": 2,
    }

    # --------------------------------------------------------
    # Download configuration
    # --------------------------------------------------------

    if download:

        options.update({
            "format":
            "bestaudio/best",
            "outtmpl":
            os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192"
            }]
        })

    # --------------------------------------------------------
    # Explicit proxy
    # --------------------------------------------------------

    if proxy:

        options["proxy"] = proxy

    return options


# ============================================================
# DOWNLOAD YOUTUBE AUDIO
# ============================================================


def download_youtube_audio(url: str) -> str:
    """
    Download YouTube audio and convert it to WAV.

    Maximum supported YouTube duration:
    10 minutes.
    """

    print("Starting YouTube audio extraction...")

    ydl_opts = get_ytdlp_options(download=True)

    try:

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            # ------------------------------------------------
            # Get metadata first
            # ------------------------------------------------

            print("Getting YouTube video information...")

            info = ydl.extract_info(url, download=False)

            if not info:

                raise RuntimeError("YouTube did not return video information.")

            # ------------------------------------------------
            # Duration check
            # ------------------------------------------------

            duration = (info.get("duration") or 0)

            print(f"YouTube duration: "
                  f"{duration:.0f} seconds")

            if duration > (10 * 60):

                raise ValueError("This video is longer than "
                                 "10 minutes. Please choose "
                                 "a video within the 10-minute limit.")

            # ------------------------------------------------
            # Video ID
            # ------------------------------------------------

            video_id = info.get("id")

            if not video_id:

                raise RuntimeError("Could not determine the "
                                   "YouTube video ID.")

            # ------------------------------------------------
            # Download
            # ------------------------------------------------

            print("Downloading YouTube audio...")

            ydl.download([url])

            # ------------------------------------------------
            # Expected WAV path
            # ------------------------------------------------

            expected_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.wav")

            if os.path.exists(expected_path):

                print(f"Audio ready: "
                      f"{expected_path}")

                return expected_path

            # ------------------------------------------------
            # Fallback search
            # ------------------------------------------------

            for filename in os.listdir(DOWNLOAD_DIR):

                if (filename.startswith(video_id)
                        and filename.endswith(".wav")):

                    fallback_path = os.path.join(DOWNLOAD_DIR, filename)

                    print(f"Audio ready: "
                          f"{fallback_path}")

                    return fallback_path

            raise RuntimeError("YouTube audio was downloaded "
                               "but the WAV file could not be found.")

    except ValueError:

        raise

    except Exception as e:

        error_text = str(e)

        print("YouTube download failed:")

        print(error_text)

        # ====================================================
        # BOT DETECTION
        # ====================================================

        if ("Sign in to confirm you're not a bot" in error_text):

            raise RuntimeError("YouTube is currently blocking "
                               "automated access from the server. "
                               "Please upload the video or audio "
                               "file directly instead.")

        # ====================================================
        # HTTP 403
        # ====================================================

        if ("HTTP Error 403" in error_text or "403 Forbidden" in error_text):

            raise RuntimeError("YouTube denied access to this video "
                               "from the server. Please upload the "
                               "video or audio file directly instead.")

        # ====================================================
        # SIGN-IN REQUIRED
        # ====================================================

        if ("Sign in" in error_text and "youtube" in error_text.lower()):

            raise RuntimeError("YouTube requires authentication for "
                               "this request. Please upload the "
                               "video or audio file directly instead.")

        # ====================================================
        # GENERIC ERROR
        # ====================================================

        raise RuntimeError("Unable to download the YouTube video. "
                           "Please try another video or upload "
                           "the video/audio file directly.")


# ============================================================
# CONVERT LOCAL FILE TO WAV
# ============================================================


def convert_to_wav(input_path: str) -> str:

    print("Converting local media to WAV...")

    output_path = (os.path.splitext(input_path)[0] + "_converted.wav")

    try:

        audio = AudioSegment.from_file(input_path)

        # ----------------------------------------------------
        # Whisper-friendly audio
        # ----------------------------------------------------

        audio = (audio.set_channels(1).set_frame_rate(16000))

        audio.export(output_path, format="wav")

        print(f"Converted audio: "
              f"{output_path}")

        return output_path

    except Exception as e:

        raise RuntimeError(f"Failed to convert the uploaded "
                           f"file to WAV: {e}")


# ============================================================
# CHUNK AUDIO
# ============================================================


def chunk_audio(wav_path: str, chunk_minutes: int = 10) -> list:

    print("Chunking audio...")

    try:

        audio = AudioSegment.from_file(wav_path)

        chunk_ms = (chunk_minutes * 60 * 1000)

        chunks = []

        for i, start in enumerate(range(0, len(audio), chunk_ms)):

            chunk = audio[start:start + chunk_ms]

            chunk_path = (f"{wav_path}"
                          f"_chunk_{i}.wav")

            chunk.export(chunk_path, format="wav")

            chunks.append(chunk_path)

        print(f"Created {len(chunks)} "
              f"audio chunk(s).")

        return chunks

    except Exception as e:

        raise RuntimeError(f"Failed to chunk audio: {e}")


# ============================================================
# PROCESS INPUT
# ============================================================


def process_input(source: str) -> list:

    is_url = source.startswith(("http://", "https://"))

    # ========================================================
    # YOUTUBE
    # ========================================================

    if is_url:

        print("Detected YouTube URL.")

        wav_path = download_youtube_audio(source)

    # ========================================================
    # LOCAL FILE
    # ========================================================

    else:

        print("Detected local file.")

        wav_path = convert_to_wav(source)

    # ========================================================
    # CHUNK
    # ========================================================

    chunks = chunk_audio(wav_path)

    print("Audio processing complete.")

    return chunks
