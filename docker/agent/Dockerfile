FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn openai "tappass>=0.7.0,<0.8"
COPY main.py .
RUN useradd -U -u 1000 appuser && chown -R 1000:1000 /app
USER 1000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
