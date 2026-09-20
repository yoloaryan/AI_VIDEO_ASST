/* =====================================================
   ACTIVE APPLICATION STATE
===================================================== */

let transcriptData = {
    title: "",
    language: "english",
    duration: 0,
    rawTranscript: "",
    segments: []
};

let isProcessing = false;
let selectedFile = null;
const MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024; // 200 MB
// const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB

/* =====================================================
   THEME MANAGER (DARK / LIGHT WITH PERSISTENCE)
===================================================== */

function setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try {
        localStorage.setItem("ai_video_theme", theme);
    } catch (e) {}
}

function initTheme() {
    const themeToggleBtn = document.getElementById("themeToggleBtn");
    if (!themeToggleBtn || themeToggleBtn.dataset.bound) return;
    themeToggleBtn.dataset.bound = "true";

    // Read stored theme preference (default to dark)
    const currentTheme = localStorage.getItem("ai_video_theme") || "dark";
    setTheme(currentTheme);

    // Register ONE click listener for the theme toggle
    themeToggleBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const activeTheme = document.documentElement.getAttribute("data-theme") || "dark";
        const nextTheme = activeTheme === "dark" ? "light" : "dark";
        setTheme(nextTheme);
    });
}

/* =====================================================
   TOAST NOTIFICATION SYSTEM
===================================================== */

function showToast(message, type = "info", duration = 3500) {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    // Prevent duplicate simultaneous identical toasts
    const existing = container.querySelectorAll(".toast");
    for (const t of existing) {
        if (t.textContent.includes(message)) return;
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    
    let icon = "ℹ️";
    if (type === "error") icon = "⚠️";
    if (type === "success") icon = "✓";

    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(8px)";
        toast.style.transition = "all 200ms ease";
        setTimeout(() => toast.remove(), 200);
    }, duration);
}

/* =====================================================
   SAFE MARKDOWN PARSING
===================================================== */

function renderMarkdownSafely(text) {
    if (!text) return "";

    // 1. If marked & DOMPurify are available via CDN
    if (typeof marked !== "undefined" && typeof DOMPurify !== "undefined") {
        try {
            marked.setOptions({
                breaks: true,
                gfm: true
            });
            const rawHtml = marked.parse(text);
            return DOMPurify.sanitize(rawHtml);
        } catch (e) {
            console.warn("Marked parsing error, falling back to regex parser:", e);
        }
    }

    // 2. Pure JS Fallback parser without external dependencies
    let clean = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // Headings
    clean = clean.replace(/^### (.*$)/gim, '<h4 style="margin: 12px 0 6px 0; font-size: 15px; font-weight: 700;">$1</h4>');
    clean = clean.replace(/^## (.*$)/gim, '<h3 style="margin: 16px 0 8px 0; font-size: 17px; font-weight: 800;">$1</h3>');
    clean = clean.replace(/^# (.*$)/gim, '<h2 style="margin: 20px 0 10px 0; font-size: 19px; font-weight: 800;">$1</h2>');

    // Bold & Italics
    clean = clean.replace(/\*\*\*(.*?)\*\*\*/gim, '<strong><em>$1</em></strong>');
    clean = clean.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
    clean = clean.replace(/\*(.*?)\*/gim, '<em>$1</em>');

    // Inline Code
    clean = clean.replace(/`([^`]+)`/gim, '<code>$1</code>');

    // Bullet points (• or - or *)
    clean = clean.replace(/^\s*[-•*]\s+(.*$)/gim, '<li style="margin-left: 20px; margin-bottom: 6px;">$1</li>');

    // Numbered lists
    clean = clean.replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li style="margin-left: 20px; margin-bottom: 6px;"><span style="font-weight:600;">$1.</span> $2</li>');

    // Paragraph breaks
    clean = clean.replace(/\n\n+/g, '<br><br>');
    clean = clean.replace(/\n/g, '<br>');

    return clean;
}

/* =====================================================
   PIPELINE STEP CONTROLLER
===================================================== */

function setPipelineStep(stepIndex) {
    const steps = [
        document.getElementById("pipeStep1"),
        document.getElementById("pipeStep2"),
        document.getElementById("pipeStep3"),
        document.getElementById("pipeStep4"),
        document.getElementById("pipeStep5"),
        document.getElementById("pipeStep6")
    ];

    steps.forEach((step, idx) => {
        if (!step) return;
        if (idx < stepIndex) {
            step.classList.add("completed");
            step.classList.remove("active");
        } else if (idx === stepIndex) {
            step.classList.add("active");
            step.classList.remove("completed");
        } else {
            step.classList.remove("active", "completed");
        }
    });
}

function resetPipeline() {
    for (let i = 1; i <= 6; i++) {
        const step = document.getElementById(`pipeStep${i}`);
        if (step) step.classList.remove("active", "completed");
    }
}

/* =====================================================
   TIMESTAMP FORMATTING HELPERS FOR DOWNLOADS
===================================================== */

function formatSRTTime(seconds) {
    const s = Math.max(0, Number(seconds) || 0);
    const hrs = Math.floor(s / 3600);
    const mins = Math.floor((s % 3600) / 60);
    const secs = Math.floor(s % 60);
    const millis = Math.floor((s % 1) * 1000);

    return `${String(hrs).padStart(2, "0")}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")},${String(millis).padStart(3, "0")}`;
}

function formatVTTTime(seconds) {
    const s = Math.max(0, Number(seconds) || 0);
    const hrs = Math.floor(s / 3600);
    const mins = Math.floor((s % 3600) / 60);
    const secs = Math.floor(s % 60);
    const millis = Math.floor((s % 1) * 1000);

    return `${String(hrs).padStart(2, "0")}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${String(millis).padStart(3, "0")}`;
}

function formatDisplayTimestamp(seconds) {
    const s = Math.max(0, Number(seconds) || 0);
    const mins = Math.floor(s / 60);
    const secs = Math.floor(s % 60);
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

/* =====================================================
   RESULTS RENDERING INTO UI
===================================================== */

function renderResults(data) {
    // 1. Header & Title
    const titleEl = document.getElementById("analysisTitle");
    const statusEl = document.getElementById("analysisStatus");
    if (titleEl && data.title) titleEl.textContent = data.title;
    if (statusEl) {
        statusEl.textContent = "● ANALYSIS COMPLETE";
        statusEl.style.color = "var(--success)";
    }

    // 2. Summary
    const summaryEl = document.getElementById("summaryText");
    if (summaryEl) {
        summaryEl.innerHTML = renderMarkdownSafely(data.summary || "No summary was generated.");
    }

    // 3. Action Items
    const actionContainer = document.getElementById("actionItemsContainer");
    if (actionContainer) {
        if (!data.action_items || data.action_items.toLowerCase().includes("no action items")) {
            actionContainer.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">—</div>
                    <h3>No action items found.</h3>
                    <p>No action items were explicitly mentioned in this video.</p>
                </div>`;
        } else {
            actionContainer.innerHTML = renderMarkdownSafely(data.action_items);
        }
    }

    // 4. Key Decisions
    const decisionsContainer = document.getElementById("keyDecisionsContainer");
    if (decisionsContainer) {
        if (!data.key_decisions || data.key_decisions.toLowerCase().includes("no key decisions")) {
            decisionsContainer.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">—</div>
                    <h3>No key decisions recorded.</h3>
                    <p>No explicit decisions were identified in the transcript.</p>
                </div>`;
        } else {
            decisionsContainer.innerHTML = renderMarkdownSafely(data.key_decisions);
        }
    }

    // 5. Open Questions
    const questionsContainer = document.getElementById("openQuestionsContainer");
    if (questionsContainer) {
        if (!data.open_questions || data.open_questions.toLowerCase().includes("no open questions")) {
            questionsContainer.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">—</div>
                    <h3>No open questions found.</h3>
                </div>`;
        } else {
            questionsContainer.innerHTML = renderMarkdownSafely(data.open_questions);
        }
    }

    // 6. Transcript & Segments
    transcriptData.title = data.title || "video-transcript";
    transcriptData.rawTranscript = data.transcript || "";
    transcriptData.segments = Array.isArray(data.segments) && data.segments.length > 0
        ? data.segments
        : [];

    // Fallback segments if empty
    if (transcriptData.segments.length === 0 && transcriptData.rawTranscript) {
        const sentences = transcriptData.rawTranscript.split(". ").filter(s => s.trim());
        transcriptData.segments = sentences.map((sent, idx) => ({
            start: idx * 10.0,
            end: (idx + 1) * 10.0,
            speaker: "Speaker",
            text: sent.trim() + (sent.endsWith(".") ? "" : ".")
        }));
    }

    const transcriptContainer = document.getElementById("transcriptContainer");
    if (transcriptContainer && transcriptData.segments.length > 0) {
        transcriptContainer.innerHTML = transcriptData.segments.map(seg => `
            <div class="transcript-segment">
                <div class="timestamp">${formatDisplayTimestamp(seg.start)}</div>
                <div>
                    <span class="speaker">${seg.speaker || "SPEAKER"}</span>
                    <p>${seg.text}</p>
                </div>
            </div>
        `).join("");
    }

    // Metadata counters
    const words = (data.transcript || "").trim().split(/\s+/).filter(Boolean).length;
    const wordsEl = document.getElementById("metaWords");
    if (wordsEl) wordsEl.textContent = `${words.toLocaleString()} WORDS`;

    const lastSeg = transcriptData.segments[transcriptData.segments.length - 1];
    const durationSec = lastSeg ? lastSeg.end : 0;
    const durationEl = document.getElementById("metaDuration");
    if (durationEl) durationEl.textContent = formatDisplayTimestamp(durationSec);

    // Scroll smoothly to Analysis
    const analysisSection = document.getElementById("analysis");
    if (analysisSection) {
        analysisSection.scrollIntoView({ behavior: "smooth" });
    }
}

/* =====================================================
   FILE UPLOAD & DRAG-AND-DROP HANDLERS
===================================================== */

function initUploadHandlers() {
    const uploadButton = document.getElementById("uploadButton");
    const videoInput = document.getElementById("videoInput");
    const dropzone = document.getElementById("dropzone");
    const fileSelectedCard = document.getElementById("fileSelectedCard");
    const selectedFileName = document.getElementById("selectedFileName");
    const selectedFileSize = document.getElementById("selectedFileSize");
    const processFileBtn = document.getElementById("processFileBtn");

    if (uploadButton && videoInput) {
        uploadButton.addEventListener("click", () => videoInput.click());
    }

    function handleFile(file) {
        if (!file) return;

        // Strict 200 MB Validation
        if (file.size > MAX_FILE_SIZE_BYTES) {
            showToast(
                "File too large. Please upload a video under 200 MB.",
                "error",
                5000
            );

            selectedFile = file;
            const sizeMb = (file.size / (1024 * 1024)).toFixed(2);

            if (selectedFileName) selectedFileName.textContent = file.name;
        if (selectedFileSize) selectedFileSize.textContent = `${sizeMb} MB`;
        if (fileSelectedCard) fileSelectedCard.style.display = "flex";

        showToast(`File selected: ${file.name} (${sizeMb} MB)`, "info");
    }

    if (videoInput) {
        videoInput.addEventListener("change", (e) => {
            if (e.target.files && e.target.files[0]) {
                handleFile(e.target.files[0]);
            }
        });
    }

    // Drag and drop
    if (dropzone) {
        ["dragenter", "dragover"].forEach(evtName => {
            dropzone.addEventListener(evtName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.add("dragover");
            });
        });

        ["dragleave", "drop"].forEach(evtName => {
            dropzone.addEventListener(evtName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.remove("dragover");
            });
        });

        dropzone.addEventListener("drop", (e) => {
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                handleFile(files[0]);
            }
        });
    }

    // Process file button click
    if (processFileBtn) {
        processFileBtn.addEventListener("click", async () => {
            if (!selectedFile) {
                showToast("Please select a file first", "error");
                return;
            }

            if (isProcessing) return;
            isProcessing = true;
            processFileBtn.disabled = true;
            processFileBtn.textContent = "Processing...";

            const statusEl = document.getElementById("analysisStatus");
            if (statusEl) statusEl.textContent = "⏳ PROCESSING VIDEO FILE...";
            
            setPipelineStep(0);
            setTimeout(() => setPipelineStep(1), 1500);

            const formData = new FormData();
            formData.append("file", selectedFile);
            formData.append("language", "english");

            try {
                showToast("Uploading and extracting audio...", "info");
                const res = await fetch("/api/process-file", {
                    method: "POST",
                    body: formData
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || "Failed to process video");
                }

                setPipelineStep(3);
                const data = await res.json();
                setPipelineStep(5);
                renderResults(data);
                showToast("Video processing complete!", "success");
            } catch (err) {
                console.error("File processing error:", err);
                showToast(err.message, "error", 6000);
                if (statusEl) statusEl.textContent = "❌ PROCESSING FAILED";
            } finally {
                isProcessing = false;
                processFileBtn.disabled = false;
                processFileBtn.textContent = "Process Video →";
            }
        });
    }
}

/* =====================================================
   YOUTUBE PROCESSING HANDLER
===================================================== */

function initYouTubeHandler() {
    const youtubeUrlInput = document.getElementById("youtubeUrlInput");
    const processYoutubeBtn = document.getElementById("processYoutubeBtn");

    async function handleProcessYouTube() {
        const url = youtubeUrlInput ? youtubeUrlInput.value.trim() : "";
        if (!url) {
            showToast("Please enter a valid YouTube URL.", "error");
            return;
        }

        if (!url.includes("youtube.com") && !url.includes("youtu.be")) {
            showToast("Please enter a valid YouTube link (youtube.com or youtu.be).", "error");
            return;
        }

        if (isProcessing) return;
        isProcessing = true;
        if (processYoutubeBtn) {
            processYoutubeBtn.disabled = true;
            processYoutubeBtn.textContent = "Processing...";
        }

        const statusEl = document.getElementById("analysisStatus");
        if (statusEl) statusEl.textContent = "⏳ DOWNLOADING & TRANSCRIBING YOUTUBE VIDEO...";
        
        setPipelineStep(0);
        setTimeout(() => setPipelineStep(1), 2000);

        try {
            showToast("Downloading audio from YouTube...", "info");
            const res = await fetch("/api/process-url", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url, language: "english" })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Failed to process YouTube URL");
            }

            setPipelineStep(3);
            const data = await res.json();
            setPipelineStep(5);
            renderResults(data);
            showToast("YouTube video analysis ready!", "success");
        } catch (err) {
            console.error("YouTube error:", err);
            showToast(err.message, "error", 6000);
            if (statusEl) statusEl.textContent = "❌ YOUTUBE PROCESSING FAILED";
        } finally {
            isProcessing = false;
            if (processYoutubeBtn) {
                processYoutubeBtn.disabled = false;
                processYoutubeBtn.textContent = "Process Video →";
            }
        }
    }

    if (processYoutubeBtn) {
        processYoutubeBtn.addEventListener("click", handleProcessYouTube);
    }

    if (youtubeUrlInput) {
        youtubeUrlInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                handleProcessYouTube();
            }
        });
    }
}

/* =====================================================
   ASK AI CHAT HANDLERS
===================================================== */

function initAskAI() {
    const askButton = document.getElementById("askButton");
    const questionInput = document.getElementById("questionInput");
    const chatMessages = document.getElementById("chatMessages");

    async function sendQuestion() {
        if (!questionInput || isProcessing) return;
        const question = questionInput.value.trim();
        if (!question) return;

        // Append User Message
        const userDiv = document.createElement("div");
        userDiv.className = "chat-message user";
        userDiv.innerHTML = `
            <span class="chat-label">YOU</span>
            <div class="markdown-body"><p>${question.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</p></div>
        `;
        chatMessages.appendChild(userDiv);

        questionInput.value = "";
        questionInput.style.height = "auto";

        // Append Thinking Indicator
        const assistantDiv = document.createElement("div");
        assistantDiv.className = "chat-message assistant";
        assistantDiv.innerHTML = `
            <span class="chat-label">AI ASSISTANT</span>
            <div class="markdown-body"><p><em>Thinking and searching video context...</em></p></div>
        `;
        chatMessages.appendChild(assistantDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        if (askButton) askButton.disabled = true;

        try {
            const res = await fetch("/api/ask", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || "Error querying AI assistant");
            }

            const data = await res.json();
            assistantDiv.innerHTML = `
                <span class="chat-label">AI ASSISTANT</span>
                <div class="markdown-body">${renderMarkdownSafely(data.answer)}</div>
            `;
        } catch (err) {
            assistantDiv.innerHTML = `
                <span class="chat-label">AI ASSISTANT</span>
                <div class="markdown-body" style="color: var(--error);"><p>${err.message}</p></div>
            `;
        } finally {
            if (askButton) askButton.disabled = false;
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    if (askButton) {
        askButton.addEventListener("click", sendQuestion);
    }

    if (questionInput) {
        questionInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendQuestion();
            }
        });

        // Auto-resize textarea
        questionInput.addEventListener("input", () => {
            questionInput.style.height = "auto";
            questionInput.style.height = Math.min(questionInput.scrollHeight, 120) + "px";
        });
    }
}

/* =====================================================
   TRANSCRIPT DOWNLOADS & CLIPBOARD
==================================================== */

function initTranscriptActions() {
    const copyBtn = document.getElementById("copyTranscript");
    const downloadBtn = document.getElementById("downloadButton");
    const downloadMenu = document.getElementById("downloadMenu");

    // Copy to clipboard
    if (copyBtn) {
        copyBtn.addEventListener("click", async () => {
            const textToCopy = transcriptData.rawTranscript;
            if (!textToCopy) {
                showToast("No transcript available to copy.", "error");
                return;
            }

            try {
                await navigator.clipboard.writeText(textToCopy);
                const orig = copyBtn.textContent;
                copyBtn.textContent = "Copied ✓";
                showToast("Transcript copied to clipboard", "success");
                setTimeout(() => { copyBtn.textContent = orig; }, 2000);
            } catch (err) {
                console.error("Clipboard copy failed:", err);
                showToast("Failed to copy to clipboard", "error");
            }
        });
    }

    // Toggle download menu
    if (downloadBtn && downloadMenu) {
        downloadBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            const isOpen = downloadMenu.classList.toggle("open");
            downloadBtn.setAttribute("aria-expanded", isOpen ? "true" : "false");
        });

        document.addEventListener("click", (e) => {
            if (!downloadMenu.contains(e.target) && !downloadBtn.contains(e.target)) {
                downloadMenu.classList.remove("open");
                downloadBtn.setAttribute("aria-expanded", "false");
            }
        });

        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                downloadMenu.classList.remove("open");
                downloadBtn.setAttribute("aria-expanded", "false");
            }
        });
    }

    function triggerDownload(filename, content, mimeType) {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    }

    // Handle each download format
    document.querySelectorAll("[data-download]").forEach(btn => {
        btn.addEventListener("click", () => {
            const format = btn.dataset.download;
            const titleSlug = (transcriptData.title || "transcript")
                .toLowerCase()
                .replace(/[^a-z0-9]+/g, "-")
                .replace(/^-|-$/g, "");

            if (!transcriptData.segments || transcriptData.segments.length === 0) {
                showToast("No processed transcript to download yet.", "error");
                return;
            }

            if (format === "txt") {
                const txtContent = transcriptData.segments.map(seg => 
                    `[${formatDisplayTimestamp(seg.start)}] ${seg.speaker || 'Speaker'}:\n${seg.text}`
                ).join("\n\n");
                triggerDownload(`${titleSlug}.txt`, txtContent, "text/plain");
                showToast("Downloaded TXT transcript", "success");
            } 
            else if (format === "srt") {
                const srtContent = transcriptData.segments.map((seg, idx) => 
                    `${idx + 1}\n${formatSRTTime(seg.start)} --> ${formatSRTTime(seg.end)}\n${seg.text}\n`
                ).join("\n");
                triggerDownload(`${titleSlug}.srt`, srtContent, "application/x-subrip");
                showToast("Downloaded SRT subtitles", "success");
            } 
            else if (format === "vtt") {
                const vttContent = "WEBVTT\n\n" + transcriptData.segments.map((seg, idx) => 
                    `${idx + 1}\n${formatVTTTime(seg.start)} --> ${formatVTTTime(seg.end)}\n${seg.text}\n`
                ).join("\n");
                triggerDownload(`${titleSlug}.vtt`, vttContent, "text/vtt");
                showToast("Downloaded WebVTT captions", "success");
            } 
            else if (format === "json") {
                const jsonPayload = {
                    title: transcriptData.title,
                    duration: transcriptData.duration,
                    language: transcriptData.language,
                    segments: transcriptData.segments
                };
                triggerDownload(`${titleSlug}.json`, JSON.stringify(jsonPayload, null, 2), "application/json");
                showToast("Downloaded JSON transcript data", "success");
            }

            if (downloadMenu) {
                downloadMenu.classList.remove("open");
                if (downloadBtn) downloadBtn.setAttribute("aria-expanded", "false");
            }
        });
    });
}

/* =====================================================
   GLOBAL INITIALIZATION
===================================================== */

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initUploadHandlers();
    initYouTubeHandler();
    initAskAI();
    initTranscriptActions();

    // Loader dismissal
    window.addEventListener("load", () => {
        const loader = document.getElementById("loader");
        if (loader) {
            setTimeout(() => loader.classList.add("hidden"), 600);
        }
    });

    // Navbar scroll effect
    const navbar = document.getElementById("navbar");
    window.addEventListener("scroll", () => {
        if (!navbar) return;
        if (window.scrollY > 20) {
            navbar.classList.add("scrolled");
        } else {
            navbar.classList.remove("scrolled");
        }
    });

    // Mobile menu toggle
    const mobileMenuButton = document.getElementById("mobileMenuButton");
    const mobileMenu = document.getElementById("mobileMenu");
    if (mobileMenuButton && mobileMenu) {
        mobileMenuButton.addEventListener("click", () => {
            mobileMenu.classList.toggle("open");
        });

        document.querySelectorAll(".mobile-menu a").forEach(link => {
            link.addEventListener("click", () => mobileMenu.classList.remove("open"));
        });
    }

    // New Video action
    const newVideoBtn = document.getElementById("newVideoBtn");
    if (newVideoBtn) {
        newVideoBtn.addEventListener("click", () => {
            window.scrollTo({ top: 0, behavior: "smooth" });
            const input = document.getElementById("youtubeUrlInput");
            if (input) input.focus();
        });
    }
});