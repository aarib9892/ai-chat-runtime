FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# -----------------------------
# Install uv
# -----------------------------

RUN pip install --no-cache-dir uv

# -----------------------------
# Install Python dependencies
# separately for Docker caching
# -----------------------------

COPY pyproject.toml uv.lock ./

RUN uv sync \
    --frozen \
    --no-dev \
    --no-install-project

# -----------------------------
# Copy application
# -----------------------------

COPY app ./app
COPY migrations ./migrations

# Install the project itself if needed.
RUN uv sync \
    --frozen \
    --no-dev

EXPOSE 8000

CMD ["uv","run","uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]