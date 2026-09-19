import yt_dlp
from pydub import AudioSegment
import os

DOWNLOAD_DIR = 'downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


import re

def extract_youtube_video_id(url: str) -> str:
    patterns = [
        r'(?:v=|\/|embed\/|youtu\.be\/|\/v\/)([0-9A-Za-z_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return ""


def fetch_youtube_transcript(url: str, language: str = "english") -> dict:
    """Attempt to fetch YouTube transcript directly via youtube-transcript-api to bypass audio download restrictions."""
    video_id = extract_youtube_video_id(url)
    if not video_id:
        return None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        langs = ['en', 'en-US', 'en-GB', 'hi']
        if language.lower() in ['hinglish', 'hindi']:
            langs = ['hi', 'en']
            
        transcript_data = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
        if transcript_data:
            full_text = " ".join([item["text"] for item in transcript_data if item.get("text")])
            segments = []
            for item in transcript_data:
                start = round(float(item.get("start", 0.0)), 2)
                duration = round(float(item.get("duration", 0.0)), 2)
                text = item.get("text", "").strip()
                if text:
                    segments.append({
                        "start": start,
                        "end": round(start + duration, 2),
                        "speaker": "Speaker",
                        "text": text
                    })
            if full_text.strip():
                return {
                    "text": full_text.strip(),
                    "segments": segments
                }
    except Exception as e:
        print(f"Direct transcript API unavailable for {video_id}: {e}")
    return None


def check_youtube_duration(url: str, max_minutes: int = 10) -> float:
    """Verify that the YouTube video does not exceed the maximum allowed duration."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "noplaylist": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "mweb", "tvhtml5"]
            }
        },
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
    }
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
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "tvhtml5", "mweb"]
            }
        },
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
    }
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