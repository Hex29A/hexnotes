FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends curl fonts-dejavu-core && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY static/ ./static/
COPY scripts/ ./scripts/
COPY tests/ ./tests/

RUN python scripts/generate_icons.py

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
