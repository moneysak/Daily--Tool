"""T2.2: Passwort-Konfiguration und -Verifikation."""
import os


def test_password_from_env(app_factory, addon_name):
    app_factory(addon_name, password="geheim")
    from auth import get_configured_password, is_open_mode, verify_password

    assert get_configured_password() == "geheim"
    assert is_open_mode() is False
    assert verify_password("geheim") is True
    assert verify_password("falsch") is False


def test_password_from_options_json(app_factory, addon_name):
    # app_factory schreibt options.json an einen Nicht-Default-Pfad und setzt
    # ALLTAGS_OPTIONS_PATH entsprechend -> deckt die Überschreibbarkeit mit ab.
    app_factory(addon_name, options={"app_password": "hunter2"})
    from auth import get_configured_password, verify_password

    assert get_configured_password() == "hunter2"
    assert verify_password("hunter2") is True
    assert verify_password("nope") is False


def test_empty_password_means_open_mode(app_factory, addon_name):
    app_factory(addon_name)
    from auth import is_open_mode, verify_password

    assert is_open_mode() is True
    assert verify_password("") is False


def test_no_plaintext_password_comparison_in_auth_sources():
    """Stellt sicher, dass auth.py konstantzeitlich vergleicht (kein ==)."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for addon in ("alltags_manager_dev", "alltags_manager"):
        path = os.path.join(repo_root, addon, "src", "backend", "auth.py")
        with open(path, "r", encoding="utf-8") as fh:
            source = fh.read()
        assert "secrets.compare_digest" in source, f"{path}: compare_digest fehlt"
        assert "== configured" not in source, f"{path}: Klartext-Vergleich gefunden"
