FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock* ./
RUN uv sync --locked --no-dev || uv sync --no-dev
COPY src/ src/
COPY mocks/ mocks/
COPY fixtures/ fixtures/
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uv", "run", "uvicorn", "reclaim.main:app", "--host", "0.0.0.0", "--port", "8000"]
