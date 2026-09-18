from __future__ import annotations

import json
import zipfile

import pytest

import opsd_ood_acquire as acquire


def _metadata(version="2020-04-15", *, omit=None):
    omit = set(omit or [])
    fields = [
        {"name": "utc_timestamp"},
        {"name": "interpolated"},
    ]
    for household in acquire.OOD_HOUSEHOLDS:
        for feed in ("grid_import", "grid_export", "pv"):
            name = f"DE_KN_{household}_{feed}"
            if name not in omit:
                fields.append({"name": name})
    return {
        "version": version,
        "licenses": [{"id": "CC-BY-4.0"}],
        "geographical-scope": "11 households in southern Germany",
        "schemas": {"1min": {"fields": fields}},
    }


def _make_zip(path, metadata):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("package/datapackage.json", json.dumps(metadata))
        zf.writestr(
            "package/household_data_1min_singleindex.csv",
            "utc_timestamp\n",
        )


def test_opsd_acquisition_manifest_validates_version_schema_and_hash(tmp_path):
    path = tmp_path / acquire.PACKAGE_FILENAME
    _make_zip(path, _metadata())
    manifest = acquire.inspect_opsd_package(path)
    assert manifest["package_version"] == "2020-04-15"
    assert manifest["byte_size"] == path.stat().st_size
    assert len(manifest["sha256"]) == 64
    assert set(manifest["required_households"]) == {
        "residential3", "residential4", "residential6"
    }


def test_opsd_acquisition_fails_closed_on_missing_required_channel(tmp_path):
    path = tmp_path / acquire.PACKAGE_FILENAME
    _make_zip(
        path,
        _metadata(omit={"DE_KN_residential4_grid_export"}),
    )
    with pytest.raises(RuntimeError, match="required OPSD OOD channels"):
        acquire.inspect_opsd_package(path)


def test_opsd_acquisition_fails_closed_on_version_drift(tmp_path):
    path = tmp_path / acquire.PACKAGE_FILENAME
    _make_zip(path, _metadata(version="2099-01-01"))
    with pytest.raises(RuntimeError, match="version mismatch"):
        acquire.inspect_opsd_package(path)
