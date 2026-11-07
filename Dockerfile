# Offizielles HA Alpine Base Image verwenden
ARG BUILD_FROM=homeassistant/amd64-base-python:3.12
FROM $BUILD_FROM

# System-Abhängigkeiten installieren
RUN apk add --no-cache \
    python3 \
    py3-pip \
    build-base \
    python3-dev

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
