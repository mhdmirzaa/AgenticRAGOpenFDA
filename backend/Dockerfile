# MaiStorage backend — built at M8. Multi-stage kept simple for demo.
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e . --break-system-packages || pip install --no-cache-dir .
COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
