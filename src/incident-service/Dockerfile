FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src:/app/src/incident-service

COPY src/incident-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy shared library
COPY src/shared /app/src/shared
# Copy service code
COPY src/incident-service /app/src/incident-service

EXPOSE 8003

# Create a non-root user
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

WORKDIR /app/src/incident-service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
