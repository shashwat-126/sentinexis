FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src:/app/src/aiops-engine

COPY src/aiops-engine/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy shared library
COPY src/shared /app/src/shared
# Copy service code
COPY src/aiops-engine /app/src/aiops-engine

# Create a non-root user
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

CMD ["python", "-m", "aiops-engine.main"]
