import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Persistente SQLite-DB unter /data/ (HA Add-on Standard).
# Das Verzeichnis ist über die Umgebungsvariable ALLTAGS_DATA_DIR überschreibbar
# (z.B. für Tests mit temporärer DB); ohne die Variable bleibt der Default /data.
# Falls das Verzeichnis nicht existiert oder nicht beschreibbar ist
# (lokale Entwicklung), Fallback auf ./data/ — außer ALLTAGS_DATA_DIR war
# explizit gesetzt, dann wird dieses Verzeichnis angelegt.
DATA_DIR = os.environ.get("ALLTAGS_DATA_DIR") or "/data"
if not os.path.exists(DATA_DIR) or not os.access(DATA_DIR, os.W_OK):
    if os.environ.get("ALLTAGS_DATA_DIR"):
        os.makedirs(DATA_DIR, exist_ok=True)
    else:
        DATA_DIR = os.path.join(os.getcwd(), "data")
        os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "alltags_manager.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI-Dependency: liefert eine DB-Session und schließt sie danach."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema(engine) -> None:
    """Mini-Migration: ergänzt fehlende Spalten in bestehenden SQLite-Tabellen.

    ``Base.metadata.create_all`` legt keine neuen Spalten in bereits
    existierenden Tabellen an. Deshalb werden per ``PRAGMA table_info`` die
    vorhandenen Spalten ermittelt und fehlende via ``ALTER TABLE ... ADD COLUMN``
    ergänzt. Idempotent — ein zweiter Aufruf ändert nichts.
    """
    migrations = {
        "tasks": {
            "due_date": "DATE",
            "completed_at": "DATETIME",
        },
        "routines": {
            "weekdays": "VARCHAR",
            "last_completed_on": "DATE",
        },
    }
    with engine.begin() as conn:
        for table, columns in migrations.items():
            rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            if not rows:
                # Tabelle existiert (noch) nicht; create_all hat sie bereits
                # vollständig angelegt -> nichts zu tun.
                continue
            existing = {row[1] for row in rows}
            for column, column_type in columns.items():
                if column not in existing:
                    conn.exec_driver_sql(
                        f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"
                    )


# Modelle registrieren, damit ``Base.metadata.create_all(bind=engine)`` die
# ``sessions``-Tabelle anlegt. Der Import steht bewusst am Dateiende, da
# ``models.session`` wiederum ``Base`` aus diesem Modul benötigt.
from models import session as _session_model  # noqa: E402,F401

