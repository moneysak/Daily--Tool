# Offizielles HA Alpine Base Image verwenden
ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base-python:3.12-alpine3.20
FROM ${BUILD_FROM}


# System-Abhängigkeiten installieren
RUN apk add --no-cache \
    python3 \
    py3-pip \
    build-base \
    python3-dev

# Container-Zeitzone (nötig für local_today()/Aggregationslogik in crud/overview.py)
ENV TZ=Europe/Berlin

# Virtual Environment erstellen
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Python-Abhängigkeiten installieren
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Anwendungscode und rootfs (s6-overlay Konfiguration) kopieren
COPY rootfs /
COPY src /app/src

# HA Build-Labels (best practice)
LABEL \
    io.hass.name="Alltags-Manager" \
    io.hass.description="FastAPI Backend für den Alltags-Manager" \
    io.hass.type="addon"

# s6-overlay deaktivieren und FastAPI direkt als PID 1 starten
ENV PYTHONPATH="/app:/app/src:/app/src/backend"
ENTRYPOINT []
CMD ["python3", "-m", "uvicorn", "src.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
