
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Copy dependency metadata first for better build caching.
COPY pyproject.toml uv.lock ./

# Install dependencies without installing the project itself.
RUN uv sync --frozen --no-install-project

# Copy the backend source code.
COPY backend/ ./backend/
COPY routing/ ./routing/
COPY download_data.py ./download_data.py

# Ensure the virtual environment's executables are on PATH.
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONUTF8=1

EXPOSE 8000

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
