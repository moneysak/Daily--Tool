"""Paritätstest: Dev- und Prod-Add-on müssen dieselben Quelldateien haben.

1. Alle Dateien unter ``src/`` beider Add-ons werden per SHA-256-Hash verglichen
   (gleicher relativer Pfad, gleicher Inhalt).
2. ``config.yaml`` darf sich nur in einer definierten Menge an Feldern
   unterscheiden (Slug, Image, Version, Ports, Panel-/Anzeigenamen ...).

Unberührt bleiben: config.yaml (nur erlaubte Felder), build.yaml, Dockerfile,
requirements.txt, rootfs.
"""
import hashlib
import os

import pytest
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEV_ADDON = "alltags_manager_dev"
PROD_ADDON = "alltags_manager"

# Felder in config.yaml, die sich zwischen Dev- und Prod-Add-on unterscheiden
# dürfen. ``ports_description`` beschreibt die Port-Belegung und wird daher
# zusammen mit ``ports`` behandelt.
ALLOWED_CONFIG_DIFFERENCES = {
    "name",
    "description",
    "version",
    "slug",
    "image",
    "panel_icon",
    "panel_title",
    "ports",
    "ports_description",
}

CHUNK_SIZE = 65536


def _sha256(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _collect_src_hashes(addon: str) -> dict:
    """relative Pfade unter src/ -> SHA-256-Hash.

    Generierte Bytecode-Caches (``__pycache__`` / ``*.pyc``) werden ignoriert,
    da sie erst durch Test-Imports entstehen und Pfad-abhängig sind.
    """
    src_root = os.path.join(REPO_ROOT, addon, "src")
    assert os.path.isdir(src_root), f"src/ nicht gefunden: {src_root}"
    hashes = {}
    for dirpath, dirnames, filenames in os.walk(src_root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in filenames:
            if filename.endswith(".pyc"):
                continue
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, src_root)
            hashes[rel_path] = _sha256(full_path)
    return hashes


def config_differences(dev_config: dict, prod_config: dict) -> dict:
    """Liefert die nicht erlaubten Schlüssel mit unterschiedlichen Werten.

    Rückgabe: {key: (dev_value, prod_value)} für alle Schlüssel außerhalb von
    ALLOWED_CONFIG_DIFFERENCES, deren Werte voneinander abweichen.
    """
    diffs = {}
    for key in set(dev_config) | set(prod_config):
        if key in ALLOWED_CONFIG_DIFFERENCES:
            continue
        dev_value = dev_config.get(key)
        prod_value = prod_config.get(key)
        if dev_value != prod_value:
            diffs[key] = (dev_value, prod_value)
    return diffs


def _load_config(addon: str) -> dict:
    with open(os.path.join(REPO_ROOT, addon, "config.yaml"), "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def test_src_files_are_identical():
    dev_hashes = _collect_src_hashes(DEV_ADDON)
    prod_hashes = _collect_src_hashes(PROD_ADDON)

    assert set(dev_hashes) == set(prod_hashes), (
        "Datei-Sätze unter src/ weichen ab: "
        f"nur Dev={sorted(set(dev_hashes) - set(prod_hashes))}, "
        f"nur Prod={sorted(set(prod_hashes) - set(dev_hashes))}"
    )

    differing = {
        rel: (dev_hashes[rel], prod_hashes[rel])
        for rel in dev_hashes
        if dev_hashes[rel] != prod_hashes[rel]
    }
    assert not differing, f"Quelldateien weichen ab: {sorted(differing)}"


def test_config_only_differs_in_allowed_fields():
    dev_config = _load_config(DEV_ADDON)
    prod_config = _load_config(PROD_ADDON)

    diffs = config_differences(dev_config, prod_config)
    assert not diffs, f"Nicht erlaubte config.yaml-Abweichungen: {diffs}"


def test_config_comparator_detects_disallowed_difference():
    """Stellt sicher, dass der Vergleich ein nicht erlaubtes Feld erkennt."""
    diffs = config_differences({"slug": "a", "ingress_port": 8000},
                               {"slug": "b", "ingress_port": 9000})
    assert diffs == {"ingress_port": (8000, 9000)}


def test_config_comparator_allows_whitelisted_difference():
    """Erlaubte Felder werden ignoriert, unerlaubte nicht."""
    diffs = config_differences(
        {"slug": "alltags_manager_dev", "ports": {"8000/tcp": 8051}, "version": "1.0.1-dev"},
        {"slug": "alltags_manager", "ports": {"8000/tcp": 8050}, "version": "1.0.0"},
    )
    assert diffs == {}
