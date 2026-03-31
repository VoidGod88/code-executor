# ==================== Stage 1: Builder (安装依赖) ====================
FROM python:3.11-slim AS builder

WORKDIR /app

# 安装系统构建依赖
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

# 复制依赖文件
COPY requirements.txt .

# 先升级 pip，然后安装所有依赖（使用 --no-cache-dir 减少体积）
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
        torch torchvision torchaudio \
        --index-url https://download.pytorch.org/whl/cpu

# ==================== Stage 2: Runtime (最终轻量镜像) ====================
FROM python:3.11-slim AS runtime

WORKDIR /app

# 只安装运行时必要的系统库（比 builder 阶段少很多）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglx-mesa0 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 阶段复制已安装的 Python 包（这是减小体积的关键）
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制你的应用代码
COPY . .

EXPOSE 8000

# 使用非 root 用户运行（提升安全性）
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]