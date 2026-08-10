FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and models
COPY app /app/app
COPY run.py /app/run.py
COPY ../cow_ml_models /app/cow_ml_models

ENV PORT=8000
EXPOSE 8000

CMD ["python", "run.py"]
