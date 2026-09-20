FROM python:3.11-slim

# ============================================================
# SYSTEM DEPENDENCIES
# ============================================================

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    ca-certificates \
    unzip \
    && rm -rf /var/lib/apt/lists/*


# ============================================================
# PYTHON CONFIGURATION
# ============================================================

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


# ============================================================
# INSTALL DENO
# ============================================================

RUN curl -fsSL https://deno.land/install.sh | sh

ENV DENO_INSTALL=/root/.deno
ENV PATH="/root/.deno/bin:${PATH}"


# ============================================================
# VERIFY RUNTIMES
# ============================================================

RUN python --version
RUN ffmpeg -version
RUN deno --version


# ============================================================
# APPLICATION
# ============================================================

WORKDIR /app


# Install Python dependencies first
# This improves Docker layer caching.
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# Copy application
COPY . .


# ============================================================
# PORT
# ============================================================

ENV PORT=8000

EXPOSE 8000


# ============================================================
# START APPLICATION
# ============================================================

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]