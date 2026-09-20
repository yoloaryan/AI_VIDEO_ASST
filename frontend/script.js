/* ============================================================
   AI VIDEO ASSISTANT
   COMPLETE FRONTEND SCRIPT
============================================================ */

/* ============================================================
   APPLICATION STATE
============================================================ */

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


/* ============================================================
   UTILITY HELPERS
============================================================ */

function escapeHTML(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function formatDisplayTimestamp(seconds) {
    const s = Math.max(0, Number(seconds) || 0);

    const hours = Math.floor(s / 3600);
    const minutes = Math.floor((s % 3600) / 60);
    const secs = Math.floor(s % 60);

    if (hours > 0) {
        return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
    }

    return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}


function formatSRTTime(seconds) {
    const s = Math.max(0, Number(seconds) || 0);

    const hours = Math.floor(s / 3600);
    const minutes = Math.floor((s % 3600) / 60);
    const secs = Math.floor(s % 60);
    const milliseconds = Math.floor((s % 1) * 1000);

    return (
        `${String(hours).padStart(2, "0")}:` +
        `${String(minutes).padStart(2, "0")}:` +
        `${String(secs).padStart(2, "0")},` +
        `${String(milliseconds).padStart(3, "0")}`
    );
}


function formatVTTTime(seconds) {
    const s = Math.max(0, Number(seconds) || 0);

    const hours = Math.floor(s / 3600);
    const minutes = Math.floor((s % 3600) / 60);
    const secs = Math.floor(s % 60);
    const milliseconds = Math.floor((s % 1) * 1000);

    return (
        `${String(hours).padStart(2, "0")}:` +
        `${String(minutes).padStart(2, "0")}:` +
        `${String(secs).padStart(2, "0")}.` +
        `${String(milliseconds).padStart(3, "0")}`
    );
}


/* ============================================================
   THEME MANAGER
============================================================ */

function setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);

    try {
        localStorage.setItem("ai_video_theme", theme);
    } catch (error) {
        console.warn("Unable to save theme preference:", error);
    }
}


function initTheme() {
    const themeToggleBtn = document.getElementById("themeToggleBtn");

    if (!themeToggleBtn) {
        return;
    }

    if (themeToggleBtn.dataset.bound === "true") {
        return;
    }

    themeToggleBtn.dataset.bound = "true";

    let currentTheme = "dark";

    try {
        currentTheme = localStorage.getItem("ai_video_theme") || "dark";
    } catch (error) {
        currentTheme = "dark";
    }

    setTheme(currentTheme);

    themeToggleBtn.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();

        const activeTheme =
            document.documentElement.getAttribute("data-theme") || "dark";

        const nextTheme =
            activeTheme === "dark" ? "light" : "dark";

        setTheme(nextTheme);
    });
}


/* ============================================================
   TOAST NOTIFICATIONS
============================================================ */

function showToast(message, type = "info", duration = 3500) {
    const container = document.getElementById("toastContainer");

    if (!container) {
        console.log(message);
        return;
    }

    const existingToasts = container.querySelectorAll(".toast");

    for (const toast of existingToasts) {
        if (toast.textContent.includes(message)) {
            return;
        }
    }

    const toast = document.createElement("div");

    toast.className = `toast toast-${type}`;

    let icon = "ℹ️";

    if (type === "error") {
        icon = "⚠️";
    }

    if (type === "success") {
        icon = "✓";
    }

    toast.innerHTML = `
        <span>${icon}</span>
        <span>${escapeHTML(message)}</span>
    `;

    container.appendChild(toast);

    setTimeout(function () {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(8px)";
        toast.style.transition = "all 200ms ease";

        setTimeout(function () {
            toast.remove();
        }, 200);
    }, duration);
}


/* ============================================================
   MARKDOWN RENDERING
============================================================ */

function renderMarkdownSafely(text) {
    if (!text) {
        return "";
    }

    /*
     * Preferred:
     * marked + DOMPurify
     */

    if (
        typeof marked !== "undefined" &&
        typeof DOMPurify !== "undefined"
    ) {
        try {
            marked.setOptions({
                breaks: true,
                gfm: true
            });

            const rawHTML = marked.parse(String(text));

            return DOMPurify.sanitize(rawHTML);
        } catch (error) {
            console.warn(
                "Markdown rendering failed. Using fallback.",
                error
            );
        }
    }

    /*
     * Fallback parser
     */

    let clean = escapeHTML(text);

    clean = clean.replace(
        /^### (.*$)/gim,
        '<h4>$1</h4>'
    );

    clean = clean.replace(
        /^## (.*$)/gim,
        '<h3>$1</h3>'
    );

    clean = clean.replace(
        /^# (.*$)/gim,
        '<h2>$1</h2>'
    );

    clean = clean.replace(
        /\*\*\*(.*?)\*\*\*/gim,
        "<strong><em>$1</em></strong>"
    );

    clean = clean.replace(
        /\*\*(.*?)\*\*/gim,
        "<strong>$1</strong>"
    );

    clean = clean.replace(
        /\*(.*?)\*/gim,
        "<em>$1</em>"
    );

    clean = clean.replace(
        /`([^`]+)`/gim,
        "<code>$1</code>"
    );

    clean = clean.replace(
        /^\s*[-•*]\s+(.*$)/gim,
        "<li>$1</li>"
    );

    clean = clean.replace(
        /^\s*(\d+)\.\s+(.*$)/gim,
        "<li><strong>$1.</strong> $2</li>"
    );

    clean = clean.replace(
        /\n\n+/g,
        "<br><br>"
    );

    clean = clean.replace(
        /\n/g,
        "<br>"
    );

    return clean;
}


/* ============================================================
   PIPELINE
============================================================ */

function setPipelineStep(stepIndex) {
    const steps = [
        document.getElementById("pipeStep1"),
        document.getElementById("pipeStep2"),
        document.getElementById("pipeStep3"),
        document.getElementById("pipeStep4"),
        document.getElementById("pipeStep5"),
        document.getElementById("pipeStep6")
    ];

    steps.forEach(function (step, index) {
        if (!step) {
            return;
        }

        step.classList.remove("active");
        step.classList.remove("completed");

        if (index < stepIndex) {
            step.classList.add("completed");
        }

        if (index === stepIndex) {
            step.classList.add("active");
        }
    });
}


function resetPipeline() {
    for (let i = 1; i <= 6; i++) {
        const step = document.getElementById(`pipeStep${i}`);

        if (step) {
            step.classList.remove("active");
            step.classList.remove("completed");
        }
    }
}


/* ============================================================
   RESULTS RENDERING
============================================================ */

function renderResults(data) {
    if (!data) {
        return;
    }

    /* -----------------------------------------
       TITLE + STATUS
    ----------------------------------------- */

    const titleEl = document.getElementById("analysisTitle");
    const statusEl = document.getElementById("analysisStatus");

    if (titleEl) {
        titleEl.textContent =
            data.title || "Video Analysis";
    }

    if (statusEl) {
        statusEl.textContent = "● ANALYSIS COMPLETE";
        statusEl.style.color = "var(--success)";
    }


    /* -----------------------------------------
       SUMMARY
    ----------------------------------------- */

    const summaryEl =
        document.getElementById("summaryText");

    if (summaryEl) {
        summaryEl.innerHTML = renderMarkdownSafely(
            data.summary || "No summary was generated."
        );
    }


    /* -----------------------------------------
       ACTION ITEMS
    ----------------------------------------- */

    const actionContainer =
        document.getElementById("actionItemsContainer");

    if (actionContainer) {
        const actionItems =
            data.action_items || "";

        if (
            !actionItems ||
            actionItems
                .toLowerCase()
                .includes("no action items")
        ) {
            actionContainer.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">—</div>
                    <h3>No action items found.</h3>
                    <p>
                        No action items were explicitly
                        mentioned in this video.
                    </p>
                </div>
            `;
        } else {
            actionContainer.innerHTML =
                renderMarkdownSafely(actionItems);
        }
    }


    /* -----------------------------------------
       KEY DECISIONS
    ----------------------------------------- */

    const decisionsContainer =
        document.getElementById("keyDecisionsContainer");

    if (decisionsContainer) {
        const decisions =
            data.key_decisions || "";

        if (
            !decisions ||
            decisions
                .toLowerCase()
                .includes("no key decisions")
        ) {
            decisionsContainer.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">—</div>
                    <h3>No key decisions recorded.</h3>
                    <p>
                        No explicit decisions were
                        identified in the transcript.
                    </p>
                </div>
            `;
        } else {
            decisionsContainer.innerHTML =
                renderMarkdownSafely(decisions);
        }
    }


    /* -----------------------------------------
       OPEN QUESTIONS
    ----------------------------------------- */

    const questionsContainer =
        document.getElementById("openQuestionsContainer");

    if (questionsContainer) {
        const questions =
            data.open_questions || "";

        if (
            !questions ||
            questions
                .toLowerCase()
                .includes("no open questions")
        ) {
            questionsContainer.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">—</div>
                    <h3>No open questions found.</h3>
                    <p>
                        No unresolved questions were
                        identified in the video.
                    </p>
                </div>
            `;
        } else {
            questionsContainer.innerHTML =
                renderMarkdownSafely(questions);
        }
    }


    /* -----------------------------------------
       TRANSCRIPT
    ----------------------------------------- */

    transcriptData.title =
        data.title || "video-transcript";

    transcriptData.rawTranscript =
        data.transcript || "";

    transcriptData.segments =
        Array.isArray(data.segments)
            ? data.segments
            : [];


    /*
     * If backend doesn't provide segments,
     * create approximate segments.
     */

    if (
        transcriptData.segments.length === 0 &&
        transcriptData.rawTranscript
    ) {
        const sentences =
            transcriptData.rawTranscript
                .split(/(?<=[.!?])\s+/)
                .filter(sentence => sentence.trim());

        transcriptData.segments =
            sentences.map(function (sentence, index) {
                return {
                    start: index * 10,
                    end: (index + 1) * 10,
                    speaker: "Speaker",
                    text: sentence.trim()
                };
            });
    }


    /* -----------------------------------------
       TRANSCRIPT UI
    ----------------------------------------- */

    const transcriptContainer =
        document.getElementById("transcriptContainer");

    if (
        transcriptContainer &&
        transcriptData.segments.length > 0
    ) {
        transcriptContainer.innerHTML =
            transcriptData.segments.map(function (segment) {
                return `
                    <div class="transcript-segment">

                        <div class="timestamp">
                            ${escapeHTML(
                                formatDisplayTimestamp(segment.start)
                            )}
                        </div>

                        <div>
                            <span class="speaker">
                                ${escapeHTML(
                                    segment.speaker || "SPEAKER"
                                )}
                            </span>

                            <p>
                                ${escapeHTML(
                                    segment.text || ""
                                )}
                            </p>
                        </div>

                    </div>
                `;
            }).join("");
    } else if (transcriptContainer) {
        transcriptContainer.innerHTML = `
            <div class="transcript-empty-state">
                <p>
                    No transcript segments are available.
                </p>
            </div>
        `;
    }


    /* -----------------------------------------
       WORD COUNT
    ----------------------------------------- */

    const words =
        (data.transcript || "")
            .trim()
            .split(/\s+/)
            .filter(Boolean)
            .length;

    const wordsEl =
        document.getElementById("metaWords");

    if (wordsEl) {
        wordsEl.textContent =
            `${words.toLocaleString()} WORDS`;
    }


    /* -----------------------------------------
       DURATION
    ----------------------------------------- */

    const lastSegment =
        transcriptData.segments[
            transcriptData.segments.length - 1
        ];

    const duration =
        lastSegment
            ? Number(lastSegment.end) || 0
            : 0;

    transcriptData.duration = duration;

    const durationEl =
        document.getElementById("metaDuration");

    if (durationEl) {
        durationEl.textContent =
            formatDisplayTimestamp(duration);
    }


    /* -----------------------------------------
       LANGUAGE
    ----------------------------------------- */

    const languageEl =
        document.getElementById("metaLanguage");

    if (languageEl) {
        languageEl.textContent =
            (transcriptData.language || "english")
                .toUpperCase();
    }


    /* -----------------------------------------
       SCROLL TO ANALYSIS
    ----------------------------------------- */

    const analysisSection =
        document.getElementById("analysis");

    if (analysisSection) {
        setTimeout(function () {
            analysisSection.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
        }, 150);
    }
}


/* ============================================================
   FILE UPLOAD
============================================================ */

function initUploadHandlers() {
    const uploadButton =
        document.getElementById("uploadButton");

    const videoInput =
        document.getElementById("videoInput");

    const dropzone =
        document.getElementById("dropzone");

    const fileSelectedCard =
        document.getElementById("fileSelectedCard");

    const selectedFileName =
        document.getElementById("selectedFileName");

    const selectedFileSize =
        document.getElementById("selectedFileSize");

    const processFileBtn =
        document.getElementById("processFileBtn");


    /* -----------------------------------------
       OPEN FILE SELECTOR
    ----------------------------------------- */

    if (uploadButton && videoInput) {
        uploadButton.addEventListener(
            "click",
            function () {
                videoInput.click();
            }
        );
    }


    /* -----------------------------------------
       HANDLE FILE
    ----------------------------------------- */

    function handleFile(file) {
        if (!file) {
            return;
        }

        /*
         * 200 MB validation
         */

        if (file.size > MAX_FILE_SIZE_BYTES) {
            showToast(
                "File too large. Please upload a video or audio file under 200 MB.",
                "error",
                5000
            );

            selectedFile = null;

            if (fileSelectedCard) {
                fileSelectedCard.style.display = "none";
            }

            return;
        }


        /*
         * Validate extension
         */

        const allowedExtensions = [
            ".mp4",
            ".mov",
            ".mp3",
            ".wav",
            ".m4a",
            ".webm"
        ];

        const fileName =
            file.name.toLowerCase();

        const validExtension =
            allowedExtensions.some(
                extension =>
                    fileName.endsWith(extension)
            );

        if (!validExtension) {
            showToast(
                "Unsupported file format. Use MP4, MOV, MP3, WAV, M4A or WEBM.",
                "error",
                5000
            );

            selectedFile = null;

            if (fileSelectedCard) {
                fileSelectedCard.style.display = "none";
            }

            return;
        }


        /*
         * Store selected file
         */

        selectedFile = file;

        const sizeMb =
            (file.size / (1024 * 1024))
                .toFixed(2);


        if (selectedFileName) {
            selectedFileName.textContent =
                file.name;
        }


        if (selectedFileSize) {
            selectedFileSize.textContent =
                `${sizeMb} MB`;
        }


        if (fileSelectedCard) {
            fileSelectedCard.style.display =
                "flex";
        }


        showToast(
            `File selected: ${file.name} (${sizeMb} MB)`,
            "info"
        );
    }


    /* -----------------------------------------
       FILE INPUT CHANGE
    ----------------------------------------- */

    if (videoInput) {
        videoInput.addEventListener(
            "change",
            function (event) {
                if (
                    event.target.files &&
                    event.target.files[0]
                ) {
                    handleFile(
                        event.target.files[0]
                    );
                }
            }
        );
    }


    /* -----------------------------------------
       DRAG & DROP
    ----------------------------------------- */

    if (dropzone) {

        ["dragenter", "dragover"].forEach(
            function (eventName) {

                dropzone.addEventListener(
                    eventName,
                    function (event) {
                        event.preventDefault();
                        event.stopPropagation();

                        dropzone.classList.add(
                            "dragover"
                        );
                    }
                );
            }
        );


        ["dragleave", "drop"].forEach(
            function (eventName) {

                dropzone.addEventListener(
                    eventName,
                    function (event) {
                        event.preventDefault();
                        event.stopPropagation();

                        dropzone.classList.remove(
                            "dragover"
                        );
                    }
                );
            }
        );


        dropzone.addEventListener(
            "drop",
            function (event) {

                const files =
                    event.dataTransfer.files;

                if (
                    files &&
                    files.length > 0
                ) {
                    handleFile(files[0]);
                }
            }
        );
    }


    /* -----------------------------------------
       PROCESS FILE
    ----------------------------------------- */

    if (processFileBtn) {

        processFileBtn.addEventListener(
            "click",
            async function () {

                if (!selectedFile) {
                    showToast(
                        "Please select a file first.",
                        "error"
                    );

                    return;
                }


                if (isProcessing) {
                    return;
                }


                isProcessing = true;

                processFileBtn.disabled = true;

                processFileBtn.textContent =
                    "Processing...";


                const statusEl =
                    document.getElementById(
                        "analysisStatus"
                    );


                if (statusEl) {
                    statusEl.textContent =
                        "⏳ PROCESSING VIDEO FILE...";
                }


                resetPipeline();

                setPipelineStep(0);


                setTimeout(function () {
                    if (isProcessing) {
                        setPipelineStep(1);
                    }
                }, 1500);


                const formData =
                    new FormData();

                formData.append(
                    "file",
                    selectedFile
                );

                formData.append(
                    "language",
                    "english"
                );


                try {

                    showToast(
                        "Uploading and extracting audio...",
                        "info"
                    );


                    const response =
                        await fetch(
                            "/api/process-file",
                            {
                                method: "POST",
                                body: formData
                            }
                        );


                    let data;

                    try {
                        data =
                            await response.json();
                    } catch (jsonError) {
                        throw new Error(
                            "The server returned an invalid response."
                        );
                    }


                    if (!response.ok) {
                        throw new Error(
                            data.detail ||
                            "Failed to process video."
                        );
                    }


                    setPipelineStep(3);


                    setTimeout(
                        function () {
                            setPipelineStep(4);
                        },
                        300
                    );


                    renderResults(data);


                    setPipelineStep(5);


                    showToast(
                        "Video processing complete!",
                        "success",
                        4000
                    );

                } catch (error) {

                    console.error(
                        "File processing error:",
                        error
                    );


                    showToast(
                        error.message ||
                        "Failed to process the video.",
                        "error",
                        6000
                    );


                    if (statusEl) {
                        statusEl.textContent =
                            "❌ PROCESSING FAILED";
                    }

                    resetPipeline();

                } finally {

                    isProcessing = false;

                    processFileBtn.disabled =
                        false;

                    processFileBtn.textContent =
                        "Process Video →";
                }
            }
        );
    }
}


/* ============================================================
   YOUTUBE PROCESSING
============================================================ */

function initYouTubeHandler() {
    const youtubeUrlInput =
        document.getElementById(
            "youtubeUrlInput"
        );

    const processYoutubeBtn =
        document.getElementById(
            "processYoutubeBtn"
        );


    async function handleProcessYouTube() {

        const url =
            youtubeUrlInput
                ? youtubeUrlInput.value.trim()
                : "";


        if (!url) {
            showToast(
                "Please enter a valid YouTube URL.",
                "error"
            );

            return;
        }


        /*
         * Basic URL validation
         */

        if (
            !url.includes("youtube.com") &&
            !url.includes("youtu.be")
        ) {
            showToast(
                "Please enter a valid YouTube link (youtube.com or youtu.be).",
                "error"
            );

            return;
        }


        if (isProcessing) {
            return;
        }


        isProcessing = true;


        if (processYoutubeBtn) {
            processYoutubeBtn.disabled = true;

            processYoutubeBtn.textContent =
                "Processing...";
        }


        const statusEl =
            document.getElementById(
                "analysisStatus"
            );


        if (statusEl) {
            statusEl.textContent =
                "⏳ DOWNLOADING & TRANSCRIBING YOUTUBE VIDEO...";
        }


        resetPipeline();

        setPipelineStep(0);


        setTimeout(function () {
            if (isProcessing) {
                setPipelineStep(1);
            }
        }, 2000);


        try {

            showToast(
                "Downloading audio from YouTube...",
                "info"
            );


            const response =
                await fetch(
                    "/api/process-url",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify({
                            url: url,
                            language: "english"
                        })
                    }
                );


            let data;

            try {
                data =
                    await response.json();
            } catch (jsonError) {
                throw new Error(
                    "The server returned an invalid response."
                );
            }


            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    "Failed to process YouTube URL."
                );
            }


            setPipelineStep(2);


            setTimeout(
                function () {
                    setPipelineStep(3);
                },
                500
            );


            renderResults(data);


            setPipelineStep(5);


            showToast(
                "YouTube video analysis ready!",
                "success",
                4000
            );

        } catch (error) {

            console.error(
                "YouTube processing error:",
                error
            );


            showToast(
                error.message ||
                "Failed to process YouTube video.",
                "error",
                6000
            );


            if (statusEl) {
                statusEl.textContent =
                    "❌ YOUTUBE PROCESSING FAILED";
            }


            resetPipeline();

        } finally {

            isProcessing = false;


            if (processYoutubeBtn) {

                processYoutubeBtn.disabled =
                    false;

                processYoutubeBtn.textContent =
                    "Process Video →";
            }
        }
    }


    /* -----------------------------------------
       BUTTON
    ----------------------------------------- */

    if (processYoutubeBtn) {
        processYoutubeBtn.addEventListener(
            "click",
            handleProcessYouTube
        );
    }


    /* -----------------------------------------
       ENTER KEY
    ----------------------------------------- */

    if (youtubeUrlInput) {

        youtubeUrlInput.addEventListener(
            "keydown",
            function (event) {

                if (event.key === "Enter") {

                    event.preventDefault();

                    handleProcessYouTube();
                }
            }
        );
    }
}


/* ============================================================
   ASK AI
============================================================ */

function initAskAI() {

    const askButton =
        document.getElementById(
            "askButton"
        );

    const questionInput =
        document.getElementById(
            "questionInput"
        );

    const chatMessages =
        document.getElementById(
            "chatMessages"
        );


    async function sendQuestion() {

        if (
            !questionInput ||
            !chatMessages
        ) {
            return;
        }


        if (isProcessing) {
            return;
        }


        const question =
            questionInput.value.trim();


        if (!question) {
            return;
        }


        /* -----------------------------------------
           USER MESSAGE
        ----------------------------------------- */

        const userDiv =
            document.createElement("div");

        userDiv.className =
            "chat-message user";


        userDiv.innerHTML = `
            <span class="chat-label">
                YOU
            </span>

            <div class="markdown-body">
                <p>
                    ${escapeHTML(question)}
                </p>
            </div>
        `;


        chatMessages.appendChild(userDiv);


        questionInput.value = "";

        questionInput.style.height =
            "auto";


        /* -----------------------------------------
           THINKING MESSAGE
        ----------------------------------------- */

        const assistantDiv =
            document.createElement("div");

        assistantDiv.className =
            "chat-message assistant";


        assistantDiv.innerHTML = `
            <span class="chat-label">
                AI ASSISTANT
            </span>

            <div class="markdown-body">
                <p>
                    <em>
                        Thinking and searching video context...
                    </em>
                </p>
            </div>
        `;


        chatMessages.appendChild(
            assistantDiv
        );


        chatMessages.scrollTop =
            chatMessages.scrollHeight;


        if (askButton) {
            askButton.disabled = true;
        }


        try {

            const response =
                await fetch(
                    "/api/ask",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify({
                            question: question
                        })
                    }
                );


            let data;

            try {
                data =
                    await response.json();
            } catch (jsonError) {
                throw new Error(
                    "The server returned an invalid response."
                );
            }


            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    "Error querying AI assistant."
                );
            }


            assistantDiv.innerHTML = `
                <span class="chat-label">
                    AI ASSISTANT
                </span>

                <div class="markdown-body">
                    ${renderMarkdownSafely(
                        data.answer || "No answer generated."
                    )}
                </div>
            `;

        } catch (error) {

            console.error(
                "Ask AI error:",
                error
            );


            assistantDiv.innerHTML = `
                <span class="chat-label">
                    AI ASSISTANT
                </span>

                <div
                    class="markdown-body"
                    style="color: var(--error);"
                >
                    <p>
                        ${escapeHTML(
                            error.message ||
                            "Failed to generate answer."
                        )}
                    </p>
                </div>
            `;

        } finally {

            if (askButton) {
                askButton.disabled = false;
            }

            chatMessages.scrollTop =
                chatMessages.scrollHeight;
        }
    }


    /* -----------------------------------------
       ASK BUTTON
    ----------------------------------------- */

    if (askButton) {
        askButton.addEventListener(
            "click",
            sendQuestion
        );
    }


    /* -----------------------------------------
       ENTER / SHIFT+ENTER
    ----------------------------------------- */

    if (questionInput) {

        questionInput.addEventListener(
            "keydown",
            function (event) {

                if (
                    event.key === "Enter" &&
                    !event.shiftKey
                ) {
                    event.preventDefault();

                    sendQuestion();
                }
            }
        );


        /* -----------------------------------------
           AUTO RESIZE
        ----------------------------------------- */

        questionInput.addEventListener(
            "input",
            function () {

                questionInput.style.height =
                    "auto";

                questionInput.style.height =
                    Math.min(
                        questionInput.scrollHeight,
                        120
                    ) + "px";
            }
        );
    }
}


/* ============================================================
   TRANSCRIPT ACTIONS
============================================================ */

function initTranscriptActions() {

    const copyBtn =
        document.getElementById(
            "copyTranscript"
        );

    const downloadBtn =
        document.getElementById(
            "downloadButton"
        );

    const downloadMenu =
        document.getElementById(
            "downloadMenu"
        );


    /* -----------------------------------------
       COPY TRANSCRIPT
    ----------------------------------------- */

    if (copyBtn) {

        copyBtn.addEventListener(
            "click",
            async function () {

                const text =
                    transcriptData.rawTranscript;


                if (!text) {

                    showToast(
                        "No transcript available to copy.",
                        "error"
                    );

                    return;
                }


                try {

                    await navigator.clipboard.writeText(
                        text
                    );


                    const originalText =
                        copyBtn.textContent;


                    copyBtn.textContent =
                        "Copied ✓";


                    showToast(
                        "Transcript copied to clipboard.",
                        "success"
                    );


                    setTimeout(
                        function () {
                            copyBtn.textContent =
                                originalText;
                        },
                        2000
                    );

                } catch (error) {

                    console.error(
                        "Clipboard error:",
                        error
                    );


                    showToast(
                        "Failed to copy transcript.",
                        "error"
                    );
                }
            }
        );
    }


    /* -----------------------------------------
       DOWNLOAD MENU
    ----------------------------------------- */

    if (
        downloadBtn &&
        downloadMenu
    ) {

        downloadBtn.addEventListener(
            "click",
            function (event) {

                event.stopPropagation();

                const isOpen =
                    downloadMenu.classList.toggle(
                        "open"
                    );


                downloadBtn.setAttribute(
                    "aria-expanded",
                    isOpen
                        ? "true"
                        : "false"
                );
            }
        );


        document.addEventListener(
            "click",
            function (event) {

                if (
                    !downloadMenu.contains(
                        event.target
                    ) &&
                    !downloadBtn.contains(
                        event.target
                    )
                ) {

                    downloadMenu.classList.remove(
                        "open"
                    );

                    downloadBtn.setAttribute(
                        "aria-expanded",
                        "false"
                    );
                }
            }
        );


        document.addEventListener(
            "keydown",
            function (event) {

                if (event.key === "Escape") {

                    downloadMenu.classList.remove(
                        "open"
                    );

                    downloadBtn.setAttribute(
                        "aria-expanded",
                        "false"
                    );
                }
            }
        );
    }


    /* -----------------------------------------
       DOWNLOAD FUNCTION
    ----------------------------------------- */

    function triggerDownload(
        filename,
        content,
        mimeType
    ) {

        const blob =
            new Blob(
                [content],
                { type: mimeType }
            );


        const url =
            URL.createObjectURL(blob);


        const anchor =
            document.createElement("a");


        anchor.href = url;

        anchor.download = filename;

        document.body.appendChild(anchor);

        anchor.click();

        anchor.remove();


        setTimeout(
            function () {
                URL.revokeObjectURL(url);
            },
            100
        );
    }


    /* -----------------------------------------
       DOWNLOAD OPTIONS
    ----------------------------------------- */

    document
        .querySelectorAll("[data-download]")
        .forEach(function (button) {

            button.addEventListener(
                "click",
                function () {

                    const format =
                        button.dataset.download;


                    if (
                        !transcriptData.segments ||
                        transcriptData.segments.length === 0
                    ) {

                        showToast(
                            "No processed transcript to download yet.",
                            "error"
                        );

                        return;
                    }


                    const titleSlug =
                        (
                            transcriptData.title ||
                            "transcript"
                        )
                            .toLowerCase()
                            .replace(
                                /[^a-z0-9]+/g,
                                "-"
                            )
                            .replace(
                                /^-|-$/g,
                                ""
                            );


                    /* -------------------------------
                       TXT
                    ------------------------------- */

                    if (format === "txt") {

                        const content =
                            transcriptData.segments
                                .map(function (segment) {

                                    return (
                                        `[${formatDisplayTimestamp(
                                            segment.start
                                        )}] ` +
                                        `${segment.speaker || "Speaker"}:\n` +
                                        `${segment.text || ""}`
                                    );
                                })
                                .join("\n\n");


                        triggerDownload(
                            `${titleSlug}.txt`,
                            content,
                            "text/plain"
                        );


                        showToast(
                            "Downloaded TXT transcript.",
                            "success"
                        );
                    }


                    /* -------------------------------
                       SRT
                    ------------------------------- */

                    else if (format === "srt") {

                        const content =
                            transcriptData.segments
                                .map(function (
                                    segment,
                                    index
                                ) {

                                    return (
                                        `${index + 1}\n` +
                                        `${formatSRTTime(
                                            segment.start
                                        )} --> ` +
                                        `${formatSRTTime(
                                            segment.end
                                        )}\n` +
                                        `${segment.text || ""}\n`
                                    );
                                })
                                .join("\n");


                        triggerDownload(
                            `${titleSlug}.srt`,
                            content,
                            "application/x-subrip"
                        );


                        showToast(
                            "Downloaded SRT subtitles.",
                            "success"
                        );
                    }


                    /* -------------------------------
                       VTT
                    ------------------------------- */

                    else if (format === "vtt") {

                        const content =
                            "WEBVTT\n\n" +
                            transcriptData.segments
                                .map(function (
                                    segment,
                                    index
                                ) {

                                    return (
                                        `${index + 1}\n` +
                                        `${formatVTTTime(
                                            segment.start
                                        )} --> ` +
                                        `${formatVTTTime(
                                            segment.end
                                        )}\n` +
                                        `${segment.text || ""}\n`
                                    );
                                })
                                .join("\n");


                        triggerDownload(
                            `${titleSlug}.vtt`,
                            content,
                            "text/vtt"
                        );


                        showToast(
                            "Downloaded WebVTT captions.",
                            "success"
                        );
                    }


                    /* -------------------------------
                       JSON
                    ------------------------------- */

                    else if (format === "json") {

                        const payload = {
                            title:
                                transcriptData.title,

                            duration:
                                transcriptData.duration,

                            language:
                                transcriptData.language,

                            segments:
                                transcriptData.segments
                        };


                        triggerDownload(
                            `${titleSlug}.json`,
                            JSON.stringify(
                                payload,
                                null,
                                2
                            ),
                            "application/json"
                        );


                        showToast(
                            "Downloaded JSON transcript data.",
                            "success"
                        );
                    }


                    /* -------------------------------
                       CLOSE MENU
                    ------------------------------- */

                    if (downloadMenu) {

                        downloadMenu.classList.remove(
                            "open"
                        );
                    }


                    if (downloadBtn) {

                        downloadBtn.setAttribute(
                            "aria-expanded",
                            "false"
                        );
                    }
                }
            );
        });
}


/* ============================================================
   MOBILE MENU
============================================================ */

function initMobileMenu() {

    const mobileMenuButton =
        document.getElementById(
            "mobileMenuButton"
        );

    const mobileMenu =
        document.getElementById(
            "mobileMenu"
        );


    if (
        !mobileMenuButton ||
        !mobileMenu
    ) {
        return;
    }


    mobileMenuButton.addEventListener(
        "click",
        function () {

            mobileMenu.classList.toggle(
                "open"
            );
        }
    );


    document
        .querySelectorAll(
            ".mobile-menu a"
        )
        .forEach(function (link) {

            link.addEventListener(
                "click",
                function () {

                    mobileMenu.classList.remove(
                        "open"
                    );
                }
            );
        });
}


/* ============================================================
   NAVBAR
============================================================ */

function initNavbar() {

    const navbar =
        document.getElementById(
            "navbar"
        );


    if (!navbar) {
        return;
    }


    function updateNavbar() {

        if (window.scrollY > 20) {
            navbar.classList.add(
                "scrolled"
            );
        } else {
            navbar.classList.remove(
                "scrolled"
            );
        }
    }


    window.addEventListener(
        "scroll",
        updateNavbar,
        { passive: true }
    );


    updateNavbar();
}


/* ============================================================
   NEW VIDEO BUTTON
============================================================ */

function initNewVideoButton() {

    const newVideoBtn =
        document.getElementById(
            "newVideoBtn"
        );


    if (!newVideoBtn) {
        return;
    }


    newVideoBtn.addEventListener(
        "click",
        function () {

            window.scrollTo({
                top: 0,
                behavior: "smooth"
            });


            setTimeout(
                function () {

                    const input =
                        document.getElementById(
                            "youtubeUrlInput"
                        );


                    if (input) {
                        input.focus();
                    }

                },
                500
            );
        }
    );
}


/* ============================================================
   LOADER
============================================================ */

/*
 * IMPORTANT:
 *
 * The previous version could leave the loader visible
 * if JavaScript failed during initialization.
 *
 * This implementation removes the loader reliably after
 * the page has loaded.
 */

function hideLoader() {

    const loader =
        document.getElementById(
            "loader"
        );


    if (!loader) {
        return;
    }


    setTimeout(
        function () {

            loader.classList.add(
                "hidden"
            );

        },
        500
    );
}


/* ============================================================
   GLOBAL INITIALIZATION
============================================================ */

function initializeApplication() {

    console.log(
        "AI Video Assistant initializing..."
    );


    /*
     * Initialize each feature independently.
     *
     * One feature failing should not prevent
     * the rest of the application from loading.
     */

    try {
        initTheme();
    } catch (error) {
        console.error(
            "Theme initialization error:",
            error
        );
    }


    try {
        initUploadHandlers();
    } catch (error) {
        console.error(
            "Upload initialization error:",
            error
        );
    }


    try {
        initYouTubeHandler();
    } catch (error) {
        console.error(
            "YouTube initialization error:",
            error
        );
    }


    try {
        initAskAI();
    } catch (error) {
        console.error(
            "Ask AI initialization error:",
            error
        );
    }


    try {
        initTranscriptActions();
    } catch (error) {
        console.error(
            "Transcript initialization error:",
            error
        );
    }


    try {
        initMobileMenu();
    } catch (error) {
        console.error(
            "Mobile menu initialization error:",
            error
        );
    }


    try {
        initNavbar();
    } catch (error) {
        console.error(
            "Navbar initialization error:",
            error
        );
    }


    try {
        initNewVideoButton();
    } catch (error) {
        console.error(
            "New video initialization error:",
            error
        );
    }


    /*
     * Hide loader after initialization.
     */

    hideLoader();


    console.log(
        "AI Video Assistant initialized successfully."
    );
}


/* ============================================================
   START APPLICATION
============================================================ */

/*
 * DOMContentLoaded
 */

if (document.readyState === "loading") {

    document.addEventListener(
        "DOMContentLoaded",
        initializeApplication,
        { once: true }
    );

} else {

    initializeApplication();
}


/*
 * Safety fallback:
 * Even if another unexpected problem occurs,
 * don't leave the splash screen forever.
 */

window.addEventListener(
    "load",
    function () {

        const loader =
            document.getElementById(
                "loader"
            );


        if (loader) {

            setTimeout(
                function () {

                    loader.classList.add(
                        "hidden"
                    );

                },
                1000
            );
        }
    },
    { once: true }
);