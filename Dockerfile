# ── Stage 1 : builder ────────────────────────────────────────────────────────
# Crée un venv isolé avec toutes les dépendances
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Crée le virtual environment dans /venv
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Installe les dépendances dans le venv (setuptools inclus via pip moderne)
COPY requirements.txt .
RUN pip install --no-cache-dir "pip>=24" "setuptools>=69,<71" wheel \
 && pip install --no-cache-dir -r requirements.txt


# ── Stage 2 : runtime ────────────────────────────────────────────────────────
# Image finale légère — copie uniquement le venv
FROM python:3.11-slim AS runtime

ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=${GIT_COMMIT} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH" \
    VIRTUAL_ENV="/venv"

WORKDIR /app

# Copie le venv complet depuis le stage builder
COPY --from=builder /venv /venv

# Copie le code source (sans les fichiers ignorés par .dockerignore)
COPY . /app

EXPOSE 8000

# Utilisateur non-root pour la sécurité
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
