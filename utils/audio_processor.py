import yt_dlp
from pydub import AudioSegment
import os

DOWNLOAD_DIR = 'downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def download_youtube_audio(url: str) -> str:
    # "%(title)s.%(ext)s" this will work as when we write the Team meeting . wav format( in which it save. Team metting in (title) and the .wav format in (ext)
    output_path = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")
    ydl_opts = {
        "format":
        "bestaudio/best",
        "outtmpl":
        output_path,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }],
        "quiet":
        True,  #it will remove the 
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info).replace(".webm", ".wav").replace(
            ".m4a", ".wav")
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