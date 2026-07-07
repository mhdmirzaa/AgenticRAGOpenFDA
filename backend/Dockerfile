# MaiStorage backend — built at M8; hardened (non-root) in security-hardening.
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e . --break-system-packages || pip install --no-cache-dir .

# Pre-download the cross-encoder reranker at BUILD time (v3.2 demo-safety) so the
# optimized path never cold-starts a HuggingFace download at demo time. This RUN
# needs network; the weights bake into the image's HF cache below.
ENV HF_HOME=/opt/hf-cache
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-base', max_length=512)"

# Force offline model loads at RUNTIME: the baked cache is authoritative, so a
# demo box with no/slow internet still runs the reranker instantly. (Runtime
# embeddings use OpenAI, not HuggingFace, so this only affects the reranker.)
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

COPY app ./app

# Run as a non-root user (security item 9). Pre-create the chroma dir so the
# named volume inherits non-root ownership on first mount.
RUN useradd -m -u 10001 appuser \
    && mkdir -p /app/chroma_db \
    && chown -R appuser:appuser /app /opt/hf-cache
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health',timeout=4).status==200 else 1)" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
