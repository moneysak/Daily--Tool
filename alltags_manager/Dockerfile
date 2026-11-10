# Multi-Stage Build: Toolchain nur in der Build-Phase, nicht im finalen Image
# (Sonst landet ein ~145 MB Compiler-Layer in jedem Image → riesige Downloads
# und I/O-Bursts beim Update auf dem Raspberry Pi, die HA Core blockieren.)

ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base-python:3.12-alpine3.20

# ---------- Build-Stage: Abhängigkeiten kompilieren ----------
FROM ${BUILD_FROM} AS builder

# System-Abhängigkeiten NUR für die Compile-Phase
RUN apk add --no-cache \
    build-base \
    python3-dev

# Virtual Environment mit allen Abhängigkeiten erzeugen
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------- Runtime-Stage: sauberes Base-Image ohne Compiler ----------
FROM ${BUILD_FROM}

# Container-Zeitzone (nötig für local_today()/Aggregationslogik in crud/overview.py)
ENV TZ=Europe/Berlin

# Venv (inkl. kompilierter Abhängigkeiten) aus der Build-Stage übernehmen
COPY --from=builder /opt/venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Anwendungscode und rootfs (s6-overlay Konfiguration) kopieren
WORKDIR /app
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
