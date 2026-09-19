import yt_dlp
from pydub import AudioSegment
import os

DOWNLOAD_DIR = 'downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


import re
from urllib.parse import urlparse, parse_qs

def extract_youtube_video_id(url: str) -> str:
    url = url.strip()
    try:
        parsed = urlparse(url)
        if parsed.hostname in ('youtu.be', 'www.youtu.be'):
            return parsed.path.lstrip('/')
        if parsed.hostname in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
            if parsed.path == '/watch':
                return parse_qs(parsed.query).get('v', [''])[0]
            if parsed.path.startswith(('/embed/', '/v/', '/shorts/')):
                return parsed.path.split('/')[2]
    except Exception:
        pass
    
    match = re.search(r'(?:v=|\/|embed\/|youtu\.be\/|\/v\/|\/shorts\/)([0-9A-Za-z_-]{11})', url)
    return match.group(1) if match else ""


from typing import Optional

def get_youtube_proxy() -> Optional[str]:
    """
    Retrieve explicitly configured YOUTUBE_PROXY.
    Never falls back to ambient HTTP_PROXY, HTTPS_PROXY, or system proxies.
    Logs proxy status safely without exposing credentials or full URL.
    """
    proxy = os.getenv("YOUTUBE_PROXY", "").strip()
    if proxy:
        print("[YouTube Config] Explicit YOUTUBE_PROXY is configured (proxy enabled).")
        return proxy
    else:
        print("[YouTube Config] No YOUTUBE_PROXY configured — using direct connection.")
        return None


def fetch_youtube_transcript(url: str, language: str = "english") -> dict:
    """Attempt to fetch YouTube transcript directly via youtube-transcript-api across all API versions."""
    video_id = extract_youtube_video_id(url)
    if not video_id:
        return None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        proxy = get_youtube_proxy()
        proxies = {"http": proxy, "https": proxy} if proxy else None
        transcript_snippets = None
        
        # Method 1: New youtube-transcript-api instance method (v1.2+)
        try:
            api = YouTubeTranscriptApi(proxies=proxies) if proxies else YouTubeTranscriptApi()
            if hasattr(api, 'fetch'):
                transcript_snippets = api.fetch(video_id)
            elif hasattr(api, 'list'):
                t_list = api.list(video_id)
                langs = ['hi', 'en'] if language.lower() in ['hinglish', 'hindi'] else ['en', 'en-US', 'en-GB', 'hi']
                transcript_snippets = t_list.find_transcript(langs).fetch()
        except Exception as e1:
            print(f"Direct API instance fetch note: {e1}")

        # Method 2: Legacy class method fallback
        if not transcript_snippets:
            try:
                if hasattr(YouTubeTranscriptApi, 'get_transcript'):
                    langs = ['hi', 'en'] if language.lower() in ['hinglish', 'hindi'] else ['en', 'en-US', 'en-GB', 'hi']
                    if proxies:
                        transcript_snippets = YouTubeTranscriptApi.get_transcript(video_id, languages=langs, proxies=proxies)
                    else:
                        transcript_snippets = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
            except Exception as e2:
                print(f"Direct API get_transcript fallback note: {e2}")

        if not transcript_snippets:
            return None

        full_text = []
        segments = []
        for snippet in transcript_snippets:
            if isinstance(snippet, dict):
                text = snippet.get('text', '').strip()
                start = round(float(snippet.get('start', 0.0)), 2)
                duration = round(float(snippet.get('duration', 0.0)), 2)
            else:
                text = getattr(snippet, 'text', '').strip()
                start = round(float(getattr(snippet, 'start', 0.0)), 2)
                duration = round(float(getattr(snippet, 'duration', 0.0)), 2)
            
            if text:
                full_text.append(text)
                segments.append({
                    'start': start,
                    'end': round(start + duration, 2),
                    'speaker': 'Speaker',
                    'text': text
                })

        if full_text:
            return {
                'text': ' '.join(full_text),
                'segments': segments
            }
    except Exception as e:
        print(f"Direct transcript extraction note for {video_id}: {e}")
    return None


def check_youtube_duration(url: str, max_minutes: int = 10) -> float:
    """Verify that the YouTube video does not exceed the maximum allowed duration."""
    proxy = get_youtube_proxy()
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "noplaylist": True,
    }
    # Explicitly manage proxy: use YOUTUBE_PROXY if present, otherwise disable ambient proxies
    if proxy:
        ydl_opts["proxy"] = proxy
    else:
        ydl_opts["proxy"] = ""

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as e:
            # If duration check fails due to bot block, allow pipeline to proceed to transcript extraction
            print(f"Duration check warning: {e}")
            return 0.0
        
        duration = info.get("duration")
        if duration and duration > (max_minutes * 60):
            raise ValueError(
                f"This video is longer than {max_minutes} minutes ({int(duration // 60)}m {int(duration % 60)}s). Please choose a video within the {max_minutes}-minute limit."
            )
        return float(duration) if duration else 0.0


def download_youtube_audio(url: str) -> str:
    # First validate duration without downloading
    check_youtube_duration(url, max_minutes=10)

    proxy = get_youtube_proxy()
    output_tmpl = os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_tmpl,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    # Explicitly manage proxy: use YOUTUBE_PROXY if present, otherwise disable ambient proxies
    if proxy:
        ydl_opts["proxy"] = proxy
    else:
        ydl_opts["proxy"] = ""

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info.get("id") or "audio"
        filename = os.path.join(DOWNLOAD_DIR, f"{video_id}.wav")
        if not os.path.exists(filename):
            # Fallback check for any converted file with that id
            for f in os.listdir(DOWNLOAD_DIR):
                if f.startswith(video_id) and f.endswith(".wav"):
                    filename = os.path.join(DOWNLOAD_DIR, f)
                    break
    return filename




def convert_to_wav(input_path: str) -> str:
    """Convert any audio/video file to WAV format using pydub."""
    output_path = os.path.splitext(input_path)[0] + "_converted.wav"
    audio = AudioSegment.from_file(
        input_path)  #it detect what is the type of the audio file
    audio = audio.set_channels(1).set_frame_rate(16000)  #16khz
    audio.export(output_path, format="wav")
    return output_path





def chunk_audio(wav_path: str, chunk_minutes: int = 10) -> list:
    audio = AudioSegment.from_file(wav_path)
    #CHUNK IS IN MILLISECONDS
    chunk_ms = chunk_minutes * 60 * 1000  #60 is to covert into the minutes nad. the 1000 is to convert into the milliseconds
    chunks = []  # for saving the chunks
    #enumerate is give to seperate the index and the  value

    for i, start in enumerate(
            range(0, len(audio), chunk_ms)
    ):  # len(audio) is the total duration of the audio in milliseconds
        chunk = audio[start:start + chunk_ms]
        chunk_path = f"{wav_path}_chunk_{i}.wav"
        chunk.export(chunk_path, format="wav")
        chunks.append(chunk_path)
    return chunks

def process_input(source: str) -> list:
    if source.startswith("http://") or source.startswith("https://"):
        print("Detected YouTube URL. Downloading audio...")
        wav_path = download_youtube_audio(source)
    else:
        print("Detected local file. Converting to WAV...")
        wav_path = convert_to_wav(source)

    print("Chunking audio...")
    chunks = chunk_audio(wav_path)
    print(f"Audio ready — {len(chunks)} chunk(s) created.")
    return chunks