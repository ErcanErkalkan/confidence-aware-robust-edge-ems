# Engineering CI baseline — 2026-10-28

The baseline source commit is `d7f772043dba5eda4c2ebfd734d052305e186eee`, Git tree `6786f88b37ae047b0d8f726f235a3c6b569921c7`. These are fresh reruns of existing software install/test workflows, requested on 2026-10-28. They do not authorize scientific experiments or establish scientific confirmation.

## Verified fresh executions

The default [tests workflow, attempt 2](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/40555895972/attempts/2) succeeded. Its [pytest job 122664196742](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/40555895972/job/122664196742) ran from 06:14:43 to 06:15:17 UTC and explicitly reported **331 passed in 10.07 s**. It uses Ubuntu and Python 3.11.

The [remediation regression workflow](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/40555895948) was rerun once for each matrix combination. All six new executions succeeded. Times below are UTC on 2026-10-28; add three hours for Europe/Istanbul. Attempts 2–7 each reran one job. GitHub carries other successful jobs into each later attempt, sometimes with new IDs but their original execution timestamps. The table identifies each actual new execution.

| Combination | Attempt | Actual executed job | UTC interval | Result |
| --- | --- | --- | --- | --- |
| ubuntu-latest, 3.11 | 2 | [122664209820](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/40555895948/job/122664209820) | 06:14:45–06:15:25 | success; 331 pass dots |
| ubuntu-latest, 3.12 | 3 | [122664515452](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/40555895948/job/122664515452) | 06:15:42–06:16:28 | success; 331 pass dots |
| ubuntu-latest, 3.14 | 4 | [122664914800](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/40555895948/job/122664914800) | 06:16:57–06:17:34 | success; 331 pass dots |
| windows-latest, 3.11 | 5 | [122665246772](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/40555895948/job/122665246772) | 06:17:59–06:19:22 | success; 331 pass dots |
| windows-latest, 3.12 | 6 | [122665806165](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/40555895948/job/122665806165) | 06:19:44–06:21:10 | success; 331 pass dots |
| windows-latest, 3.14 | 7 | [122666315782](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/40555895948/job/122666315782) | 06:21:20–06:22:36 | success; 331 pass dots |

Each matrix test log contains 331 passing test dots, reaches 100%, and has no failed/error test entries. The double quiet option suppresses the textual total in these logs. Each successful matrix job uploaded one JUnit XML file.

## JUnit artifact identities

The following are the six fresh artifacts created on 2026-10-28. Hashes are **GitHub-reported SHA-256 digests of the artifact ZIP**, not separately computed hashes of the enclosed XML. The artifact API reports all six as nonexpired.

| JUnit artifact | Artifact | Artifact ZIP SHA-256 |
| --- | --- | --- |
| regression-ubuntu-latest-3.11 | [12796133377](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/40555895948/artifacts/12796133377) | `0fbeb11ccfa42923d8f6946a21ad8eb87ab60182c4752b174cb1b1a331903e9b` |
| regression-ubuntu-latest-3.12 | [12796700107](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/40555895948/artifacts/12796700107) | `ca3b36fc7ea3e0e7c729a491a4c57e4c5515e625348730f087560ce9090a8ba1` |
| regression-ubuntu-latest-3.14 | [12796044371](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/40555895948/artifacts/12796044371) | `17f380d2ead46bd685080595d218fb974bd93c6654c942337749764f03919c51` |
| regression-windows-latest-3.11 | [12796556177](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/40555895948/artifacts/12796556177) | `3b93a97d866c1b15526be72178ff9ea9047a1cdb337eca395db8cb9483684d77` |
| regression-windows-latest-3.12 | [12796636237](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/40555895948/artifacts/12796636237) | `3b7567145448075f5defa567257d11bdbc09625be9bb03f58dcd7b7f68cde5d9` |
| regression-windows-latest-3.14 | [12796920216](https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/actions/runs/40555895948/artifacts/12796920216) | `380276b988cc27c778e6e540410f1514829093d97cffc38d55a706c1d1bf49a9` |

The default tests workflow does not upload a JUnit artifact. The source-backed machine-readable record is [CI_BASELINE_20261028.json](CI_BASELINE_20261028.json).

## Installation and test scope

Both existing workflows install the editable package with `.[dev,remediation]`. The project requires Python >=3.11, NumPy >=2.0, pandas >=2.0, SciPy >=1.13 and Matplotlib >=3.8; the dev extra supplies pytest >=8 and remediation supplies cryptography >=46. The full remediation test installation must include both extras.

These workflows resolve currently available versions satisfying the project bounds. They do not use the frozen full dependency lock. Their results demonstrate current software compatibility on the recorded source; they are not a byte-exact replay of a frozen environment. The new final-hardening workflow records `pip freeze --all`, interpreter/platform details, CI commit and run identity for every job.

`pyproject.toml` limits default pytest discovery to `tests/` (58 test modules at this baseline). Eighteen additional test modules under historical R19–R30 packages, research audits and readiness tools are outside that default scope. The earlier 419-test historical package evidence is a different, dated scope; it was not rerun by these baseline jobs. The canonical Drive datasets, historical package outputs and manuscripts were not read or changed by the connected GitHub CI audit.

The existing baseline workflows run install plus pytest. They do not run the engineering report builder or production integration CLI. New `final-hardening.yml` adds the engineering smoke, synthetic calibration/factorial and compute commands, with reports as artifacts; it does not execute a prospective scientific workflow.

## Repository permissions and scientific limits

The branch response reported `protected=false`, and `GET /rulesets?includes_parents=true` returned an empty collection. Reading detailed branch protection returned HTTP 403, `Resource not accessible by integration`. No protection setting was changed. Therefore this audit cannot claim an enforced server-side review/check policy; successful review and CI must be checked before any separately authorized merge.

The local execution backend did not return output from read-only shell probes during this session, so the baseline was inspected and rerun through connected GitHub tools. The local canonical root and attachment were not revalidated through those failed probes.

The merged P1/P2 status continues to state: prospective R19 remains unlocked, independently eligible external TEST is absent, family-wide 95% confidence coverage and adaptive superiority are not established, and physical/HIL certification or journal submission clearance is absent. Passing install/tests supplies none of these approvals.

## Documentation corrections

The root README still says main is the only remaining branch, although later reviewed feature development exists. Its full-test install example should include `.[dev,remediation]`. Keep frozen scientific dates and evidence anchors as historical records, and link the current engineering status.

The remediation README still calls the changes a local feature branch based on the premerge snapshot, reports the earlier 297-test environments as current, and says Linux CI has not run. Replace those present-tense statements with PR #3's merge/current-source anchors and the dated fresh CI evidence above. Preserve 297 and 419 only with their original dates and distinct scopes. Keep all scientific NO-GO statements until their actual gates are satisfied.
