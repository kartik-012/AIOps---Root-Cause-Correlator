FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn prometheus-client httpx

COPY service_template.py /app/main.py

ENV PORT=8080
EXPOSE 8080

CMD ["python", "main.py"]
