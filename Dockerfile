FROM python:3.12-slim

ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=${GIT_COMMIT}

WORKDIR /app

# (Optionnel mais clean) : git + build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
# requirements-dev.txt est optionnel, mais on le supporte
COPY requirements-dev.txt /app/requirements-dev.txt

RUN pip install --no-cache-dir -r requirements.txt && \
    if [ -f /app/requirements-dev.txt ]; then pip install --no-cache-dir -r /app/requirements-dev.txt; fi

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
