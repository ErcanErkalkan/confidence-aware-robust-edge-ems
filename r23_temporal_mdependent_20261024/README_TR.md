# CRMT R23 — Zaman Bağımlılığında Havuzlanmış CVaR Pareto

R22 sonrası **ayrı bir bilimsel prototip**; özgün CRMT risk kodu ve tarihsel sonuçlar değiştirilmedi.

## Neler var?

- `tools/r23_certifier.py`: tek-look, koşullu sabit destek ve bilinen sonlu m-bağımlılığa sahip gün vektörleri için Hoeffding ve Empirical Bernstein sertifikası. R22'nin günlük ortalama estimand'ından farklı olarak orijinal havuzlanmış controller-block risk hedefini korur.
- `tools/run_r23.py`: 8 sentetik senaryo × 30 tekrar × 2 yöntem; eski R16 TRAIN orijinal ham kaynağında üç çiftin SHA / ledger denetimi.
- `reference_snapshot/crmt_edge_ems/`: eski gerçek risk/dominance/archive kaynaklarının byte-for-byte kopyası (Git blob kimlikleri test edilir).
- `reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip`: daha önce incelenmiş tarihsel TRAIN kaynak arşivi; **yeni TEST değildir**.
- `results/`: 480 tekrar kaydı, 16 özet satırı, gerçek TRAIN FAIL-CLOSED raporu.
- `tests/test_r23.py`: 33 test. `docs/` bilimsel gerekçe/kanıt ve açık eksikler.

## Tekrar üretim

```bash
python -m pip install numpy pytest
python -m pytest -q tests/test_r23.py
OPENBLAS_NUM_THREADS=1 python tools/run_r23.py --repetitions 30 \
  --out results --source reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip
```

Yazılım bir laboratuvar prototipidir. Katı durağanlık, tam sonlu m-bağımlılık, geçerli önceden belirlenmiş kayıp sınırları ve aday havuzunun örneklemden bağımsız sabitlenmesi **haricen kanıtlanmalıdır**. Kaynak kodundaki `SyntheticDesign` saha güvenliği onayı değildir. Gerçek OpenCEM / EAAI yeni TEST **NO-GO**.
