# Multietapa: las ruedas se compilan una vez en una imagen con compilador y
# se copian a un runtime limpio. La imagen final no lleva nada con lo que
# compilar codigo.

# ---- build ----------------------------------------------------------------
FROM python:3.12-slim AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /wheels
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ---- runtime --------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# curl solo para el healthcheck de Compose.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 atalaya

WORKDIR /app

COPY --from=build /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY --chown=atalaya:atalaya app ./app

# Nunca como root. Si el sondeo alguna vez es enganado, que sea enganado
# como usuario sin privilegios.
USER atalaya

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
