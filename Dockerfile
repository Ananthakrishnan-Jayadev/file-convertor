# --- build the frontend ---
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- backend + system converters ---
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-writer libreoffice-calc libreoffice-impress \
        ghostscript fonts-dejavu fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/ backend/
RUN pip install --no-cache-dir -e ./backend
COPY --from=web /web/dist frontend/dist
ENV FC_DATA_DIR=/data
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
