# ---------------------------------------------------------------------------
# Stage 1 — dependency installation
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS deps

WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Copy only dependency files first (layer-cache friendly)
COPY server/pyproject.toml server/poetry.lock ./

# Install production deps only (no dev group)
RUN poetry config virtualenvs.in-project true \
    && poetry install --only main --no-root --no-interaction --no-ansi

# ---------------------------------------------------------------------------
# Stage 2 — runtime image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy the virtual environment from the deps stage
COPY --from=deps /app/.venv /app/.venv

# Copy application source
COPY server/ ./

# Ensure the venv binaries are on PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Non-root user for security
RUN addgroup --system app && adduser --system --ingroup app app
USER app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
