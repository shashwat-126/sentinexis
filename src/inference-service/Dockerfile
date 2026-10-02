FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src

COPY src/inference-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy shared library
COPY src/shared /app/src/shared
# Copy service code
COPY src/inference-service /app/src/inference-service

EXPOSE 8001

# Create a non-root user
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

CMD ["uvicorn", "inference-service.main:app", "--host", "0.0.0.0", "--port", "8001"]
