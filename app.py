import os
import shutil
import uuid

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from main import run_pipeline
from core.rag_engine import ask_question, load_rag_chain

app = FastAPI(title="AI Video Assistant")

# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# CONFIGURATION
# ============================================================

# Maximum uploaded file size = 200 MB
MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mp3",
    ".wav",
    ".m4a",
    ".webm",
}

# ============================================================
# ACTIVE PIPELINE STATE
# ============================================================

current_state = {
    "title": "",
    "summary": "",
    "action_items": "",
    "key_decisions": "",
    "open_questions": "",
    "transcript": "",
    "segments": [],
    "rag_chain": None,
}

# ============================================================
# REQUEST MODELS
# ============================================================


class ProcessURLRequest(BaseModel):
    url: str
    language: str = "english"


class AskRequest(BaseModel):
    question: str


# ============================================================
# HEALTH CHECK
# ============================================================


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "AI Video Assistant"}


# ============================================================
# PROCESS YOUTUBE URL
# ============================================================


@app.post("/api/process-url")
def process_url_endpoint(req: ProcessURLRequest):

    global current_state

    url = req.url.strip()

    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL is required.")

    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(
            status_code=400,
            detail="Please enter a valid URL starting with http:// or https://"
        )

    try:

        print("=" * 60)
        print("Processing YouTube URL")
        print(url)
        print("=" * 60)

        result = run_pipeline(url, req.language)

        current_state = result

        return {
            "title": result.get("title", "Video Analysis"),
            "summary": result.get("summary", ""),
            "action_items": result.get("action_items", ""),
            "key_decisions": result.get("key_decisions", ""),
            "open_questions": result.get("open_questions", ""),
            "transcript": result.get("transcript", ""),
            "segments": result.get("segments", [])
        }

    except ValueError as ve:

        raise HTTPException(status_code=400, detail=str(ve))

    except RuntimeError as re:

        print(f"YouTube processing error: {re}")

        raise HTTPException(status_code=400, detail=str(re))

    except Exception as e:

        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to process the YouTube video. "
                "Please try another video or upload the video file directly."))


# ============================================================
# PROCESS UPLOADED FILE
# ============================================================


@app.post("/api/process-file")
async def process_file_endpoint(file: UploadFile = File(...),
                                language: str = Form("english")):

    global current_state

    filename = file.filename or ""

    if not filename:
        raise HTTPException(status_code=400, detail="No file was selected.")

    # --------------------------------------------------------
    # Check extension
    # --------------------------------------------------------

    _, ext = os.path.splitext(filename)

    ext = ext.lower()

    if ext not in ALLOWED_EXTENSIONS:

        raise HTTPException(
            status_code=400,
            detail=(f"Unsupported file format '{ext}'. "
                    "Allowed formats: MP4, MOV, MP3, WAV, M4A, WEBM."))

    # --------------------------------------------------------
    # Check file size
    # --------------------------------------------------------

    file.file.seek(0, 2)

    file_size = file.file.tell()

    file.file.seek(0)

    if file_size > MAX_FILE_SIZE_BYTES:

        raise HTTPException(
            status_code=400,
            detail=("File too large. "
                    "Please upload a video or audio file under 200 MB."))

    # --------------------------------------------------------
    # Create downloads directory
    # --------------------------------------------------------

    os.makedirs("downloads", exist_ok=True)

    # --------------------------------------------------------
    # Generate safe filename
    # --------------------------------------------------------

    safe_filename = (f"{uuid.uuid4().hex}{ext}")

    file_path = os.path.join("downloads", safe_filename)

    # --------------------------------------------------------
    # Save uploaded file
    # --------------------------------------------------------

    try:

        with open(file_path, "wb") as buffer:

            shutil.copyfileobj(file.file, buffer)

    except Exception as e:

        raise HTTPException(status_code=500,
                            detail="Failed to save the uploaded file.")

    # --------------------------------------------------------
    # Process file
    # --------------------------------------------------------

    try:

        print("=" * 60)
        print("Processing uploaded file")
        print(f"Original filename: {filename}")
        print(f"Saved filename: {safe_filename}")
        print(f"Size: "
              f"{file_size / (1024 * 1024):.2f} MB")
        print("=" * 60)

        result = run_pipeline(file_path, language)

        current_state = result

        return {
            "title": result.get("title", filename),
            "summary": result.get("summary", ""),
            "action_items": result.get("action_items", ""),
            "key_decisions": result.get("key_decisions", ""),
            "open_questions": result.get("open_questions", ""),
            "transcript": result.get("transcript", ""),
            "segments": result.get("segments", [])
        }

    except ValueError as ve:

        raise HTTPException(status_code=400, detail=str(ve))

    except RuntimeError as re:

        print(f"File processing error: {re}")

        raise HTTPException(status_code=400, detail=str(re))

    except Exception:

        import traceback

        traceback.print_exc()

        raise HTTPException(status_code=500,
                            detail=("Failed to process the uploaded file. "
                                    "Please check that the file is valid."))

    finally:

        # ----------------------------------------------------
        # Remove uploaded temporary file
        # ----------------------------------------------------

        try:

            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception:
            pass


# ============================================================
# ASK AI
# ============================================================


@app.post("/api/ask")
def ask_endpoint(req: AskRequest):

    global current_state

    question = req.question.strip()

    if not question:

        raise HTTPException(status_code=400,
                            detail="Question cannot be empty.")

    rag_chain = current_state.get("rag_chain")

    # --------------------------------------------------------
    # Load RAG chain if needed
    # --------------------------------------------------------

    if not rag_chain:

        try:

            rag_chain = load_rag_chain()

            current_state["rag_chain"] = rag_chain

        except Exception:

            raise HTTPException(status_code=400,
                                detail=("Please process a video or YouTube "
                                        "link first before asking questions."))

    # --------------------------------------------------------
    # Ask question
    # --------------------------------------------------------

    try:

        answer = ask_question(rag_chain, question)

        return {"answer": answer}

    except Exception:

        import traceback

        traceback.print_exc()

        raise HTTPException(status_code=500,
                            detail="Failed to generate answer.")


# ============================================================
# FRONTEND
# ============================================================

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":

    import uvicorn

    port = int(os.environ.get("PORT", 5500))

    uvicorn.run("app:app", host="0.0.0.0", port=port)
