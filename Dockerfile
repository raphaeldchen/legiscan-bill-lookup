FROM python:3.12-slim

WORKDIR /app

# Install system deps (needed by psycopg2-binary on slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

# Install Python deps first — separate layer so Docker cache survives app-code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
