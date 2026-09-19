import os
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from main import run_pipeline
from core.rag_engine import ask_question, load_rag_chain

app = FastAPI(title="AI Video Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mp3", ".wav", ".m4a", ".webm"}

# In-memory storage for the active pipeline state
current_state = {
    "title": "",
    "summary": "",
    "action_items": "",
    "key_decisions": "",
    "open_questions": "",
    "transcript": "",
    "segments": [],
    "rag_chain": None
}


class ProcessURLRequest(BaseModel):
    url: str
    language: str = "english"


class AskRequest(BaseModel):
    question: str


@app.post("/api/process-url")
def process_url_endpoint(req: ProcessURLRequest):
    global current_state
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL is required.")
    
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="Please enter a valid URL starting with http:// or https://")

    try:
        print(f"Processing URL: {url}")
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
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process video: {str(e)}")


@app.post("/api/process-file")
async def process_file_endpoint(file: UploadFile = File(...), language: str = Form("english")):
    global current_state
    
    filename = file.filename or ""
    _, ext = os.path.splitext(filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Allowed formats: MP4, MOV, MP3, WAV."
        )

    # Validate file size: maximum 5 MB
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="File too large. Please upload a video under 5 MB."
        )

    os.makedirs("downloads", exist_ok=True)
    file_path = os.path.join("downloads", filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        print(f"Processing uploaded file: {file_path} ({file_size / (1024*1024):.2f} MB)")
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
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.post("/api/ask")
def ask_endpoint(req: AskRequest):
    global current_state
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    rag_chain = current_state.get("rag_chain")
    if not rag_chain:
        try:
            rag_chain = load_rag_chain()
            current_state["rag_chain"] = rag_chain
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Please process a video or YouTube link first before asking questions."
            )
    try:
        answer = ask_question(rag_chain, question)
        return {"answer": answer}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {str(e)}")


# Mount the frontend directory
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5500))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
