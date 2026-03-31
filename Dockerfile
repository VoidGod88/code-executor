FROM python:3.11-slim

WORKDIR /app

# System dependencies for matplotlib and seaborn
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgl1 \
    libglx-mesa0 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies (Torch is commented out for faster build, you can uncomment later)
RUN pip install --no-cache-dir -r requirements.txt
# && pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]