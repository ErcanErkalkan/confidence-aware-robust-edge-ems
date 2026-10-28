# Platform dependency constraints

Six runtime constraint files were derived from successful public GitHub Actions
run40645435132 (493 tests per environment): Ubuntu/Windows with Python3.11,
3.12 and3.14. The files exclude the editable project URI and contain public
package/version identities. They do not attest historical experiment environments.

CI installs pip26.2.2, all versions from the matching runtime file, and then the
reviewed editable source. Isolated build dependencies use build-constraints.txt
separately. PyPI identities for the selected build wheels are recorded in
BUILD_PACKAGE_IDENTITIES.json. The build backend is pinned in pyproject.toml.

Example for Ubuntu/Python3.12:

```sh
python -m pip install pip==26.2.2
python -m pip install -r reproducibility/locks/ci-ubuntu-latest-python-3.12.txt
python -m pip install -c reproducibility/locks/ci-ubuntu-latest-python-3.12.txt --build-constraint reproducibility/locks/build-constraints.txt -e ".[dev,remediation]"
python -m pip check
python -m pytest --junitxml=reports/test_results/junit.xml
```

Use the matching OS/Python file. These constraints are scoped to the stated
platforms; they are not a universal lock for future Python/platform combinations.
Reinstallation with these constraints must pass CI before merge.
