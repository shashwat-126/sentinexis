FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src

COPY src/result-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy shared library
COPY src/shared /app/src/shared
# Copy service code
COPY src/result-service /app/src/result-service

EXPOSE 8002

# Create a non-root user
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

CMD ["uvicorn", "result-service.main:app", "--host", "0.0.0.0", "--port", "8002"]
