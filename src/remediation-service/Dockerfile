FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src:/app/src/remediation-service

COPY src/remediation-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy shared library
COPY src/shared /app/src/shared
# Copy service code
COPY src/remediation-service /app/src/remediation-service

EXPOSE 8004

# NOTE: this service is intentionally run as root (not a non-root user like
# the other services) because it needs group access to the mounted Docker
# socket to issue container remediation actions. Restrict this at the host
# level (docker group membership / socket permissions) in production rather
# than widening it further here.

WORKDIR /app/src/remediation-service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
