FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src:/app/src/notification-service

COPY src/notification-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/shared /app/src/shared
COPY src/notification-service /app/src/notification-service

EXPOSE 8005

RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

WORKDIR /app/src/notification-service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8005"]
