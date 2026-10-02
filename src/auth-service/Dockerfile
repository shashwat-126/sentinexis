FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src

COPY src/auth-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy shared library
COPY src/shared /app/src/shared
# Copy service code
COPY src/auth-service /app/src/auth-service

EXPOSE 8000

# Create a non-root user
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

CMD ["uvicorn", "auth-service.main:app", "--host", "0.0.0.0", "--port", "8000"]
