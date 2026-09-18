from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


PACKAGE_VERSION = "2020-04-15"
PACKAGE_FILENAME = "opsd-household_data-2020-04-15.zip"
PACKAGE_URL = (
    "https://data.open-power-system-data.org/household_data/"
    "opsd-household_data-2020-04-15.zip"
)
REQUIRED_BASENAMES = (
    "datapackage.json",
    "household_data_1min_singleindex.csv",
)
OOD_HOUSEHOLDS = ("residential3", "residential4", "residential6")


def sha256_file(path: Path, *, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _find_unique_basename(names: list[str], basename: str) -> str:
    matches = [n for n in names if Path(n).name == basename]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one {basename!r} in OPSD ZIP, found {len(matches)}"
        )
    return matches[0]


def verify_locked_identity(zip_path: Path, lock: dict) -> dict:
    """Verify the downloaded package against the committed immutable identity."""
    observed = inspect_opsd_package(zip_path)
    expected_bytes = int(lock["byte_size"])
    expected_sha = str(lock["sha256"])
    if int(observed["byte_size"]) != expected_bytes:
        raise RuntimeError(
            f"OPSD byte-size mismatch: {observed['byte_size']} != {expected_bytes}"
        )
    if str(observed["sha256"]) != expected_sha:
        raise RuntimeError(
            f"OPSD SHA-256 mismatch: {observed['sha256']} != {expected_sha}"
        )
    if str(observed["package_version"]) != str(lock["package_version"]):
        raise RuntimeError("OPSD package version differs from committed lock")
    return observed


def inspect_opsd_package(zip_path: Path) -> dict:
    if not zip_path.is_file():
        raise FileNotFoundError(zip_path)
    if not zipfile.is_zipfile(zip_path):
        raise RuntimeError("OPSD artifact is not a valid ZIP file")

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        resolved = {
            base: _find_unique_basename(names, base)
            for base in REQUIRED_BASENAMES
        }
        metadata = json.loads(
            zf.read(resolved["datapackage.json"]).decode("utf-8")
        )

    if metadata.get("version") != PACKAGE_VERSION:
        raise RuntimeError(
            f"OPSD package version mismatch: {metadata.get('version')!r}"
        )
    licenses = {
        str(x.get("id"))
        for x in metadata.get("licenses", [])
        if isinstance(x, dict)
    }
    if "CC-BY-4.0" not in licenses:
        raise RuntimeError("expected CC-BY-4.0 license not found in datapackage")

    schemas = metadata.get("schemas", {})
    fields = schemas.get("1min", {}).get("fields", [])
    names_1min = {
        str(field.get("name"))
        for field in fields
        if isinstance(field, dict) and field.get("name")
    }
    required_channels = []
    for household in OOD_HOUSEHOLDS:
        prefix = f"DE_KN_{household}"
        required_channels.extend(
            [
                f"{prefix}_grid_import",
                f"{prefix}_grid_export",
                f"{prefix}_pv",
            ]
        )
    missing = sorted(set(required_channels) - names_1min)
    if missing:
        raise RuntimeError(
            f"required OPSD OOD channels missing from 1min schema: {missing}"
        )

    info = zip_path.stat()
    return {
        "stage": "OPSD_OOD_ARTIFACT_ACQUISITION_ONLY",
        "claim_boundary": (
            "Byte/schema provenance only. No controller, optimizer, validation, "
            "internal-test, or OOD performance outcome is computed."
        ),
        "package_version": PACKAGE_VERSION,
        "package_filename": PACKAGE_FILENAME,
        "package_url": PACKAGE_URL,
        "byte_size": int(info.st_size),
        "sha256": sha256_file(zip_path),
        "license_ids": sorted(licenses),
        "geographical_scope": metadata.get("geographical-scope"),
        "required_households": list(OOD_HOUSEHOLDS),
        "required_channels": required_channels,
        "zip_member_count": len(names),
        "resolved_members": resolved,
    }


def main() -> int:
    p = argparse.ArgumentParser(
        description="Inspect and hash the fixed OPSD Household Data OOD package"
    )
    p.add_argument("--zip", dest="zip_path", type=Path, required=True)
    p.add_argument("--output-json", type=Path, required=True)
    args = p.parse_args()

    manifest = inspect_opsd_package(args.zip_path)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
