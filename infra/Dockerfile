FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY shared ./shared
COPY services ./services

RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "uvicorn", "services.auth_service.app:app", "--host", "0.0.0.0", "--port", "8001"]
