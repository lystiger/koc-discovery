# syntax=docker/dockerfile:1
# KOC Discovery: web demo, tests and mock runs without API keys.
#   docker build -t koc-discovery .
#   docker run --rm -p 127.0.0.1:8765:8765 koc-discovery     # web on http://127.0.0.1:8765

# Stage 1: build the React web app
FROM node:20-slim AS web
WORKDIR /app
COPY web/package.json web/package-lock.json web/
RUN cd web && npm ci --no-audit --no-fund
COPY web web
COPY design/logo design/logo
RUN cd web && npm run build

# Stage 2: Python app with the built web
FROM python:3.12-slim
# Static ffmpeg/ffprobe (needed only for real runs): ~80 MB instead of ~450 MB from apt
COPY --from=mwader/static-ffmpeg:7.1 /ffmpeg /ffprobe /usr/local/bin/
RUN useradd --create-home koc
WORKDIR /app
COPY --chown=koc pyproject.toml ./
COPY --chown=koc src src
RUN pip install --no-cache-dir -e ".[dev]"
COPY --chown=koc . .
COPY --chown=koc --from=web /app/web/dist web/dist
RUN chown koc /app
USER koc
EXPOSE 8765
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["web"]
