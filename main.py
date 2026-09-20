from dotenv import load_dotenv

from utils.audio_processor import (process_input, fetch_youtube_transcript)

from core.transcriber import transcribe_all

from core.summarizer import (summarize, generate_title)

from core.extractor import (extract_action_items, extract_key_decisions,
                            extract_questions)

from core.rag_engine import (build_rag_chain, ask_question)

load_dotenv()

# ============================================================
# MAIN PIPELINE
# ============================================================


def run_pipeline(source: str, language: str = "english") -> dict:

    print("=" * 60)
    print("STARTING AI VIDEO ASSISTANT")
    print("=" * 60)

    transcript = ""
    segments = []

    is_url = source.startswith(("http://", "https://"))

    # ========================================================
    # YOUTUBE URL
    # ========================================================

    if is_url:

        print("Source detected: YouTube URL")

        # ----------------------------------------------------
        # First attempt:
        # Direct YouTube transcript
        # ----------------------------------------------------

        print("Attempting direct YouTube transcript...")

        try:

            direct_result = fetch_youtube_transcript(source, language)

        except Exception as e:

            print(f"Direct transcript error: {e}")

            direct_result = None

        # ----------------------------------------------------
        # Transcript successfully obtained
        # ----------------------------------------------------

        if (direct_result and direct_result.get("text")):

            print("YouTube transcript extracted successfully.")

            transcript = direct_result.get("text", "")

            segments = direct_result.get("segments", [])

        # ----------------------------------------------------
        # Transcript unavailable
        # ----------------------------------------------------

        else:

            print("Direct transcript unavailable.")

            print("Falling back to YouTube audio extraction...")

    # ========================================================
    # LOCAL FILE OR YOUTUBE FALLBACK
    # ========================================================

    if not transcript:

        try:

            chunks = process_input(source)

            print(f"Audio processing complete. "
                  f"{len(chunks)} chunk(s) created.")

            # ------------------------------------------------
            # Whisper / speech-to-text
            # ------------------------------------------------

            transcription_result = transcribe_all(chunks, language)

            if isinstance(transcription_result, dict):

                transcript = transcription_result.get("text", "")

                segments = transcription_result.get("segments", [])

            else:

                transcript = str(transcription_result)

                segments = []

        except ValueError:

            raise

        except RuntimeError as e:

            print(f"Audio processing failed: {e}")

            if is_url:

                raise ValueError(str(e))

            raise

        except Exception as e:

            print(f"Unexpected audio processing error: {e}")

            if is_url:

                raise RuntimeError(
                    "Unable to process this YouTube video. "
                    "YouTube may be blocking automated access. "
                    "Please upload the video/audio file directly.")

            raise

    # ========================================================
    # CHECK TRANSCRIPT
    # ========================================================

    if not transcript or not transcript.strip():

        raise ValueError("No transcript could be generated from this video.")

    print("=" * 60)
    print("TRANSCRIPTION COMPLETE")
    print("=" * 60)

    print("Transcript preview:")

    print(transcript[:500])

    # ========================================================
    # GENERATE TITLE
    # ========================================================

    print("Generating title...")

    title = generate_title(transcript)

    # ========================================================
    # SUMMARY
    # ========================================================

    print("Generating summary...")

    summary = summarize(transcript)

    # ========================================================
    # ACTION ITEMS
    # ========================================================

    print("Extracting action items...")

    action_items = extract_action_items(transcript)

    # ========================================================
    # KEY DECISIONS
    # ========================================================

    print("Extracting key decisions...")

    key_decisions = extract_key_decisions(transcript)

    # ========================================================
    # OPEN QUESTIONS
    # ========================================================

    print("Extracting open questions...")

    open_questions = extract_questions(transcript)

    # ========================================================
    # RAG
    # ========================================================

    print("Building RAG chain...")

    rag_chain = build_rag_chain(transcript)

    # ========================================================
    # FINAL RESULT
    # ========================================================

    result = {
        "title": title,
        "summary": summary,
        "action_items": action_items,
        "key_decisions": key_decisions,
        "open_questions": open_questions,
        "transcript": transcript,
        "segments": segments,
        "rag_chain": rag_chain
    }

    print("=" * 60)
    print("AI VIDEO ASSISTANT PIPELINE COMPLETE")
    print("=" * 60)

    return result


# ============================================================
# CLI MODE
# ============================================================

if __name__ == "__main__":

    source = input("Enter YouTube URL or local file path: ").strip()

    language = input("Language (english/hinglish): ").strip() or "english"

    result = run_pipeline(source, language)

    print("\n")
    print("=" * 60)

    print(f"📌 Title:\n{result['title']}")

    print(f"\n📋 Summary:\n{result['summary']}")

    print(f"\n✅ Action Items:\n{result['action_items']}")

    print(f"\n🔑 Key Decisions:\n{result['key_decisions']}")

    print(f"\n❓ Open Questions:\n{result['open_questions']}")

    print("=" * 60)

    # ========================================================
    # RAG CHAT
    # ========================================================

    print("\n💬 Chat with your video")

    print("Type 'exit' to quit.\n")

    rag_chain = result["rag_chain"]

    while True:

        question = input("You: ").strip()

        if question.lower() in ["exit", "quit", "q"]:

            print("👋 Goodbye!")

            break

        if not question:
            continue

        answer = ask_question(rag_chain, question)

        print(f"\n🤖 Assistant: {answer}\n")
