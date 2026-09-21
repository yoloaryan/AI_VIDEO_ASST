import os
import re
import base64
import tempfile
import shutil

from typing import Optional
from urllib.parse import urlparse, parse_qs

import yt_dlp
from pydub import AudioSegment

# ============================================================
# CONFIGURATION
# ============================================================

DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

MAX_YOUTUBE_DURATION_SECONDS = 10 * 60

# ============================================================
# YOUTUBE VIDEO ID
# ============================================================


def extract_youtube_video_id(url: str) -> str:
    """
    Extract an 11-character YouTube video ID from common
    YouTube URL formats.
    """

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

        if hostname in (
                "youtube.com",
                "www.youtube.com",
                "m.youtube.com",
        ):

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
        print(f"[YouTube] Video ID parsing error: {e}")

    # --------------------------------------------------------
    # Regex fallback
    # --------------------------------------------------------

    match = re.search(
        r"(?:v=|\/|embed\/|youtu\.be\/|\/v\/|\/shorts\/)"
        r"([0-9A-Za-z_-]{11})",
        url,
    )

    if match:
        return match.group(1)

    return ""


# ============================================================
# YOUTUBE PROXY
# ============================================================


def get_youtube_proxy() -> Optional[str]:

    proxy = os.getenv("YOUTUBE_PROXY", "").strip()

    if proxy:
        print("[YouTube Config] "
              "YOUTUBE_PROXY is configured.")

        return proxy

    print("[YouTube Config] "
          "No YOUTUBE_PROXY configured.")

    return None


# ============================================================
# YOUTUBE COOKIES
# ============================================================


def get_youtube_cookie_file() -> Optional[str]:
    """
    Decode YOUTUBE_COOKIES_BASE64 into a temporary
    Netscape-format cookie file.

    IMPORTANT:
    Cookie contents are never printed to logs.
    """

    cookies_b64 = os.getenv("YOUTUBE_COOKIES_BASE64", "").strip()

    if not cookies_b64:

        print("[YouTube Config] "
              "YOUTUBE_COOKIES_BASE64 is NOT configured.")

        return None

    try:

        # Remove accidental whitespace/newlines.
        cookies_b64 = re.sub(r"\s+", "", cookies_b64)

        decoded = base64.b64decode(cookies_b64, validate=True)

        if not decoded:
            raise ValueError("Decoded cookie file is empty.")

        # ----------------------------------------------------
        # Validate Netscape cookie format
        # ----------------------------------------------------

        decoded_text = decoded.decode("utf-8", errors="replace")

        if not decoded_text.startswith("# Netscape HTTP Cookie File"):
            print("[YouTube Config] WARNING: "
                  "Cookie file does not start with the "
                  "Netscape cookie header.")

        # ----------------------------------------------------
        # Temporary cookie file
        # ----------------------------------------------------

        cookie_path = os.path.join(tempfile.gettempdir(),
                                   "youtube_cookies.txt")

        with open(cookie_path, "wb") as f:

            f.write(decoded)

        print("[YouTube Config] "
              f"YouTube cookie file loaded "
              f"({len(decoded)} bytes).")

        return cookie_path

    except Exception as e:

        print("[YouTube Config] "
              f"Failed to decode YOUTUBE_COOKIES_BASE64: {e}")

        return None


# ============================================================
# DIRECT YOUTUBE TRANSCRIPT
# ============================================================


def fetch_youtube_transcript(url: str,
                             language: str = "english") -> Optional[dict]:

    video_id = extract_youtube_video_id(url)

    if not video_id:

        print("[Transcript] "
              "Could not extract YouTube video ID.")

        return None

    print("[Transcript] "
          f"Attempting transcript for video: {video_id}")

    try:

        from youtube_transcript_api import (YouTubeTranscriptApi)

        proxy = get_youtube_proxy()

        proxies = None

        if proxy:
            proxies = {
                "http": proxy,
                "https": proxy,
            }

        transcript_snippets = None

        # ====================================================
        # LANGUAGE PREFERENCE
        # ====================================================

        if language.lower() in ("hinglish", "hindi"):

            languages = [
                "hi",
                "en",
                "en-US",
                "en-GB",
            ]

        else:

            languages = [
                "en",
                "en-US",
                "en-GB",
                "hi",
            ]

        # ====================================================
        # NEW API
        # ====================================================

        try:

            if proxies:

                api = YouTubeTranscriptApi(proxies=proxies)

            else:

                api = YouTubeTranscriptApi()

            if hasattr(api, "fetch"):

                try:

                    transcript_snippets = api.fetch(video_id,
                                                    languages=languages)

                except TypeError:

                    transcript_snippets = api.fetch(video_id)

            elif hasattr(api, "list"):

                transcript_list = api.list(video_id)

                transcript = (transcript_list.find_transcript(languages))

                transcript_snippets = (transcript.fetch())

        except Exception as e:

            print("[Transcript] "
                  f"New API failed: {e}")

        # ====================================================
        # LEGACY API
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

                print("[Transcript] "
                      f"Legacy API failed: {e}")

        # ====================================================
        # NO TRANSCRIPT
        # ====================================================

        if not transcript_snippets:

            print("[Transcript] "
                  "No direct YouTube transcript available.")

            return None

        # ====================================================
        # BUILD TRANSCRIPT
        # ====================================================

        full_text = []
        segments = []

        for snippet in transcript_snippets:

            if isinstance(snippet, dict):

                text = snippet.get("text", "").strip()

                start = round(float(snippet.get("start", 0.0)), 2)

                duration = round(float(snippet.get("duration", 0.0)), 2)

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
                    "text": text,
                })

        if not full_text:
            return None

        result = {
            "text": " ".join(full_text),
            "segments": segments,
        }

        print("[Transcript] "
              "Direct YouTube transcript successfully extracted.")

        return result

    except Exception as e:

        print("[Transcript] "
              f"Transcript extraction failed for "
              f"{video_id}: {e}")

        return None


# ============================================================
# YT-DLP OPTIONS
# ============================================================


def get_ytdlp_options(download: bool = False) -> dict:

    proxy = get_youtube_proxy()
    cookie_file = get_youtube_cookie_file()

    options = {

        # ----------------------------------------------------
        # General
        # ----------------------------------------------------
        "quiet": False,
        "no_warnings": False,
        "noplaylist": True,

        # ----------------------------------------------------
        # Network / Retry
        # ----------------------------------------------------
        "socket_timeout": 45,
        "retries": 5,
        "fragment_retries": 5,
        "extractor_retries": 5,
        "concurrent_fragment_downloads": 1,

        # ----------------------------------------------------
        # Network / Geo
        # ----------------------------------------------------
        "nocheckcertificate": True,
        "geo_bypass": True,
        "geo_bypass_country": "IN",

        # ----------------------------------------------------
        # YouTube JavaScript Challenge Solver
        # ----------------------------------------------------
        # Required for modern YouTube bot/challenge checks.
        # Deno is already installed in your Dockerfile.
        "remote_components": ["ejs:github"],

        # ----------------------------------------------------
        # Browser-like Headers
        # ----------------------------------------------------
        "http_headers": {
            "User-Agent": ("Mozilla/5.0 "
                           "(X11; Linux x86_64) "
                           "AppleWebKit/537.36 "
                           "(KHTML, like Gecko) "
                           "Chrome/131.0.0.0 "
                           "Safari/537.36"),
            "Accept-Language":
            "en-US,en;q=0.9",
            "Accept":
            "*/*",
            "Sec-Fetch-Mode":
            "navigate",
        },
    }

    # ========================================================
    # DOWNLOAD CONFIGURATION
    # ========================================================

    if download:

        options.update({
            "format":
            "bestaudio/best",
            "outtmpl":
            os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }],
        })

    # ========================================================
    # PROXY
    # ========================================================

    if proxy:

        options["proxy"] = proxy

        print("[YouTube Config] "
              "yt-dlp will use the configured proxy.")

    # ========================================================
    # COOKIES
    # ========================================================

    if cookie_file:

        options["cookiefile"] = cookie_file

        print("[YouTube Config] "
              "yt-dlp will use the configured YouTube cookies.")

    else:

        print("[YouTube Config] "
              "yt-dlp will run without cookies.")

    # ========================================================
    # FINAL CONFIG LOG
    # ========================================================

    print("[YouTube Config] "
          "EJS remote components enabled: ejs:github")

    return options


# ============================================================
# SAFE ERROR CLASSIFICATION
# ============================================================


def classify_youtube_error(error_text: str) -> str:

    error_lower = error_text.lower()

    # --------------------------------------------------------
    # Bot / authentication
    # --------------------------------------------------------

    if ("sign in to confirm you're not a bot" in error_lower
            or "sign in to confirm you're not a bot" in error_lower
            or "not a bot" in error_lower):

        return ("YouTube is blocking automated access from "
                "the Railway server.")

    # --------------------------------------------------------
    # PO Token / 403
    # --------------------------------------------------------

    if ("po token" in error_lower or "pytokens" in error_lower
            or "http error 403" in error_lower
            or "403 forbidden" in error_lower):

        return ("YouTube returned HTTP 403. "
                "The Railway server may require updated "
                "YouTube authentication or PO-token support.")

    # --------------------------------------------------------
    # JavaScript runtime
    # --------------------------------------------------------

    if ("javascript runtime" in error_lower or "js runtime" in error_lower
            or "deno" in error_lower
            or "node" in error_lower and "javascript" in error_lower):

        return ("yt-dlp requires a JavaScript runtime on "
                "the Railway server.")

    # --------------------------------------------------------
    # Cookies
    # --------------------------------------------------------

    if ("cookies" in error_lower
            and ("invalid" in error_lower or "expired" in error_lower
                 or "authentication" in error_lower)):

        return ("The configured YouTube cookies appear to be "
                "invalid or expired.")

    # --------------------------------------------------------
    # Video unavailable
    # --------------------------------------------------------

    if ("video unavailable" in error_lower or "private video" in error_lower
            or "age-restricted" in error_lower):

        return ("This YouTube video is unavailable to the "
                "Railway downloader.")

    return ("YouTube could not be downloaded from the "
            "Railway server.")


# ============================================================
# DOWNLOAD YOUTUBE AUDIO
# ============================================================


def download_youtube_audio(url: str) -> str:

    print("=" * 70)
    print("[YouTube] STARTING YOUTUBE DOWNLOAD")
    print("=" * 70)

    video_id = extract_youtube_video_id(url)

    if not video_id:

        raise ValueError("Invalid YouTube URL.")

    print(f"[YouTube] Video ID: {video_id}")

    cookie_configured = bool(os.getenv("YOUTUBE_COOKIES_BASE64", "").strip())

    print("[YouTube] Cookies configured: "
          f"{cookie_configured}")

    print("[YouTube] yt-dlp version: "
          f"{yt_dlp.version.__version__}")

    ydl_opts = get_ytdlp_options(download=True)

    try:

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            # =================================================
            # METADATA
            # =================================================

            print("[YouTube] Getting video information...")

            info = ydl.extract_info(url, download=False)

            if not info:

                raise RuntimeError("YouTube did not return video information.")

            # =================================================
            # DURATION
            # =================================================

            duration = (info.get("duration") or 0)

            print("[YouTube] Duration: "
                  f"{duration:.0f} seconds")

            if (duration > MAX_YOUTUBE_DURATION_SECONDS):

                raise ValueError("This YouTube video is longer than "
                                 "10 minutes. Please choose a video "
                                 "within the 10-minute limit.")

            # =================================================
            # VIDEO ID
            # =================================================

            video_id = info.get("id")

            if not video_id:

                raise RuntimeError("Could not determine the YouTube video ID.")

            # =================================================
            # DOWNLOAD
            # =================================================

            print("[YouTube] Downloading audio...")

            result = ydl.download([url])

            print("[YouTube] yt-dlp download result: "
                  f"{result}")

            # =================================================
            # EXPECTED WAV
            # =================================================

            expected_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.wav")

            if os.path.exists(expected_path):

                print("[YouTube] Audio ready: "
                      f"{expected_path}")

                return expected_path

            # =================================================
            # FALLBACK SEARCH
            # =================================================

            print("[YouTube] Expected WAV not found. "
                  "Searching downloads directory...")

            for filename in os.listdir(DOWNLOAD_DIR):

                if (filename.startswith(video_id)
                        and filename.endswith(".wav")):

                    fallback_path = os.path.join(DOWNLOAD_DIR, filename)

                    print("[YouTube] Audio ready: "
                          f"{fallback_path}")

                    return fallback_path

            raise RuntimeError("YouTube audio was downloaded, but "
                               "the WAV file could not be found.")

    except ValueError:
        raise

    except Exception as e:

        error_text = str(e)

        print("=" * 70)
        print("[YouTube] YT-DLP FINAL ERROR")
        print("=" * 70)

        # IMPORTANT:
        # Never print cookie values.
        print(error_text)

        print("=" * 70)

        friendly_reason = classify_youtube_error(error_text)

        print("[YouTube] Classified error: "
              f"{friendly_reason}")

        print("=" * 70)

        raise RuntimeError(f"{friendly_reason} "
                           "Check Railway logs for the exact yt-dlp error.")


# ============================================================
# CONVERT LOCAL FILE TO WAV
# ============================================================


def convert_to_wav(input_path: str) -> str:

    print("[Audio] Converting local media to WAV...")

    output_path = (os.path.splitext(input_path)[0] + "_converted.wav")

    try:

        audio = AudioSegment.from_file(input_path)

        audio = (audio.set_channels(1).set_frame_rate(16000))

        audio.export(output_path, format="wav")

        print("[Audio] Converted: "
              f"{output_path}")

        return output_path

    except Exception as e:

        raise RuntimeError("Failed to convert the uploaded "
                           f"file to WAV: {e}")


# ============================================================
# CHUNK AUDIO
# ============================================================


def chunk_audio(wav_path: str, chunk_minutes: int = 10) -> list:

    print("[Audio] Chunking audio...")

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

        print("[Audio] Created "
              f"{len(chunks)} audio chunk(s).")

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

        print("[Pipeline] Detected YouTube URL.")

        wav_path = download_youtube_audio(source)

    # ========================================================
    # LOCAL FILE
    # ========================================================

    else:

        print("[Pipeline] Detected local file.")

        wav_path = convert_to_wav(source)

    # ========================================================
    # CHUNK
    # ========================================================

    chunks = chunk_audio(wav_path)

    print("[Pipeline] Audio processing complete.")

    return chunks
