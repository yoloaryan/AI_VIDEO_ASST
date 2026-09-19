# AI Video Assistant 🎙️🤖

An intelligent, full-stack meeting and video analysis platform that converts video/audio recordings and YouTube links into structured executive summaries, actionable insights, timestamped transcripts, and an interactive **RAG (Retrieval-Augmented Generation)** conversational AI.

[![Live Demo](https://img.shields.io/badge/Live_Demo-Railway-00C7B7?style=for-the-badge&logo=railway&logoColor=white)](https://aivideoasst-production.up.railway.app/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Whisper](https://img.shields.io/badge/OpenAI-Whisper-412991?style=for-the-badge&logo=openai&logoColor=white)](https://github.com/openai/whisper)
[![LangChain](https://img.shields.io/badge/LangChain-LCEL-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://www.langchain.com/)
[![ChromaDB](https://img.shields.io/badge/Chroma-Vector_DB-FF6F00?style=for-the-badge)](https://www.trychroma.com/)
[![Docker](https://img.shields.io/badge/Docker-Container-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

---

## 🚀 Live Demo

- **Production URL**: [https://aivideoasst-production.up.railway.app/](https://aivideoasst-production.up.railway.app/)

---

## 🌟 Key Features

- **Multi-Format Ingestion**:
  - Direct video/audio drag & drop file upload (`.mp4`, `.mov`, `.mp3`, `.wav`, `.m4a`, `.webm` up to 5 MB).
  - YouTube URL processing with automatic caption extraction and audio fallback.
- **Dual Transcription Engine**:
  - **OpenAI Whisper** (English): High-accuracy offline speech-to-text with word-level timestamps.
  - **Sarvam AI** (Hinglish/Hindi): Seamless multilingual translation and transcription.
- **Executive Meeting Intelligence (Groq / Mistral)**:
  - Concise **Executive Summary** in bulleted format.
  - Extracted **Action Items** with clear deliverables.
  - Key **Decisions & Conclusions**.
  - Open **Questions & Follow-ups**.
- **Contextual RAG & Q&A Chat**:
  - Chunks meeting transcripts using `RecursiveCharacterTextSplitter`.
  - Generates semantic embeddings with `sentence-transformers` (`all-MiniLM-L6-v2`).
  - Stores vectors in **ChromaDB**.
  - Powers a conversational search engine over your video content via **LangChain LCEL** & **Mistral AI**.
- **Modern SaaS UI**:
  - Sleek dark/light theme toggle.
  - Interactive 6-step real-time pipeline status tracker.
  - Clickable timestamped transcript viewer.
  - Safe Markdown and bullet-point rendering with XSS sanitization.

---

## 🏗️ Architecture & Pipeline

```mermaid
flowchart TD
    A[Video / Audio File or YouTube URL] --> B[Audio Processing & Slicing\nFFmpeg / pydub]
    B --> C{Language Selection}
    C -->|English| D[OpenAI Whisper Engine]
    C -->|Hinglish| E[Sarvam AI STT API]
    D --> F[Full Timestamped Transcript]
    E --> F
    F --> G[Groq LLM Engine]
    G --> H[Meeting Title & Executive Summary]
    G --> I[Action Items & Key Decisions]
    F --> J[Chroma Vector Store\nHuggingFace Embeddings]
    J --> K[LangChain LCEL RAG Chain]
    K --> L[Ask AI Conversational Interface\nMistral LLM]
```

---

## 📁 Repository Structure

```text
├── app.py                      # FastAPI web server and API endpoints
├── main.py                     # Core orchestration pipeline (CLI + web interface)
├── Dockerfile                  # Production multi-stage Docker build (Python 3.11 + FFmpeg)
├── requirements.txt            # Python dependencies
├── render.yaml                 # Render cloud deployment blueprint
├── Procfile                    # Process manager config
├── core/
│   ├── transcriber.py          # Whisper & Sarvam speech-to-text engines
│   ├── summarizer.py           # Map-reduce executive summarization via Groq
│   ├── extractor.py            # Extraction for action items, decisions, questions
│   ├── vector_store.py         # Chroma vector database & HuggingFace embeddings
│   └── rag_engine.py           # LangChain RAG pipeline with Mistral AI
├── utils/
│   └── audio_processor.py      # Audio conversion, chunking, YouTube fetching & proxy isolation
├── frontend/
│   ├── index.html              # Modern responsive UI
│   ├── style.css               # Clean SaaS design system & theme variables
│   ├── script.js               # Frontend API handlers, state, and RAG chat logic
│   └── assets/                 # Icons and favicon
└── storage/                    # Temporary audio slices & local ChromaDB persistence
```

---

## ⚙️ Environment Variables

Create a `.env` file in the root directory:

| Variable | Required | Description | Example / Default |
| :--- | :---: | :--- | :--- |
| `GROQ_API_KEY` | **Yes** | API key from Groq Console | `gsk_...` |
| `GROQ_MODEL` | No | LLM model for summarization | `openai/gpt-oss-120b` or `llama-3.3-70b-versatile` |
| `MISTRAL_API_KEY` | **Yes** | API key from Mistral AI Console | `...` |
| `MISTRAL_MODEL` | No | LLM model for RAG Q&A | `open-mistral-7b` |
| `WHISPER_MODEL` | No | Local Whisper model size | `tiny` *(recommended for cloud)*, `base`, `small` |
| `SARVAM_API_KEY` | No | Required only for Hinglish translation | `sk_...` |
| `SARVAM_STT_MODEL` | No | Sarvam model identifier | `saaras:v2.5` |
| `YOUTUBE_PROXY` | No | Optional proxy for datacenter YouTube scraping | `http://user:pass@host:port` |
| `PORT` | No | Web server port | `5500` (local) / `8080` (Docker) |

---

## 💻 Local Installation & Setup

### 1. Prerequisites
- **Python 3.11** installed.
- **FFmpeg** installed and added to system PATH:
  - **macOS**: `brew install ffmpeg`
  - **Ubuntu/Debian**: `sudo apt-get install ffmpeg`
  - **Windows**: `winget install Gyan.FFmpeg` or `choco install ffmpeg`

### 2. Clone the Repository
```bash
git clone https://github.com/yoloaryan/AI_VIDEO_ASST.git
cd AI_VIDEO_ASST
```

### 3. Create & Activate Virtual Environment
```bash
python3.11 -m venv .venv

# macOS / Linux:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate
```

### 4. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Run the Application
```bash
# Start FastAPI backend & UI
python app.py
```

Open your browser and navigate to:
👉 **`http://localhost:5500`**

---

## 🐳 Docker Deployment

You can build and run the entire application in a self-contained Docker container:

```bash
# Build the Docker image
docker build -t ai-video-assistant .

# Run the container with your environment variables
docker run -p 8080:8080 --env-file .env ai-video-assistant
```

Access the app at **`http://localhost:8080`**.

---

## ☁️ Cloud Deployment (Railway)

This repository includes a production-ready [`Dockerfile`](Dockerfile) optimized for Railway:

1. Create a project on [Railway.app](https://railway.app).
2. Connect your GitHub repository `AI_VIDEO_ASST`.
3. In **Variables**, add:
   - `GROQ_API_KEY`
   - `MISTRAL_API_KEY`
   - `WHISPER_MODEL=tiny`
   - `MISTRAL_MODEL=open-mistral-7b`
4. In **Settings** → **Networking**, click **Generate Domain** to get your public HTTPS URL.

---

## 📡 API Reference

### `POST /api/process-url`
Process a YouTube URL.
```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "language": "english"
}
```

### `POST /api/process-file`
Process an uploaded audio or video file (`multipart/form-data`).
- `file`: Binary file (`.mp4`, `.mov`, `.mp3`, `.wav`)
- `language`: `"english"` or `"hinglish"`

### `POST /api/ask`
Ask questions against the indexed video meeting transcript via RAG.
```json
{
  "question": "What were the main decisions made regarding the release timeline?"
}
```

---

## 🛡️ License

Distributed under the MIT License. See `LICENSE` for details.