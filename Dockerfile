FROM python:3.11.9-slim

WORKDIR /app

# Install system dependencies for Playwright, Tesseract, and other tools
RUN apt-get update && apt-get install -y \
    # Build essentials for Python packages
    gcc \
    g++ \
    make \
    # Magic file type detection
    libmagic1 \
    # PDF processing
    libpoppler-cpp-dev \
    # OCR (Tesseract)
    tesseract-ocr \
    libtesseract-dev \
    # Playwright browser dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libxshmfence1 \
    fonts-liberation \
    libappindicator3-1 \
    libnss3 \
    xdg-utils \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers with all dependencies
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p logs temp && \
    chmod 777 logs temp

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=10000

# Expose port (Render requires binding to PORT env var)
EXPOSE 10000

# Run the application
# IMPORTANT: Must bind to 0.0.0.0 and use PORT environment variable
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1
