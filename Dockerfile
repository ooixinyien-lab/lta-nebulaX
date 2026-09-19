# ==============================================================================
# Stage 1: Build the React frontend (nebula-ui)
# ==============================================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/nebula-ui

COPY nebula-ui/package*.json ./
RUN npm ci || npm install

COPY nebula-ui/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Python Backend + OR-Tools CP-SAT Solver
# ==============================================================================
FROM python:3.12-slim AS runner

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt requirements-core.txt requirements-cpsat.txt requirements-chat.txt ./
RUN pip install --no-cache-dir -r requirements-cpsat.txt -r requirements-chat.txt

# Copy backend application and dataset files
COPY backend/ ./backend/
COPY data/ ./data/

# Copy built frontend distribution from Stage 1
COPY --from=frontend-builder /app/nebula-ui/dist ./nebula-ui/dist

# Create output folder for runs
RUN mkdir -p outputs

# Cloud Run injects $PORT (default 8080)
ENV PORT=8080
ENV APP_ENV=development

EXPOSE 8080

# Start Uvicorn listening on 0.0.0.0 and the dynamically injected $PORT
CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
