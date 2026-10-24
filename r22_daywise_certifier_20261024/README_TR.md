# CRMT R22 — Gün Bazlı Koşullu Pareto Sertifikası

**Durum:** Matematiksel olarak koşullu ve yeni günlük estimand üzerinde çalışan **sentetik araştırma prototipi**, doğrulanmış OpenCEM saha mekanizması değildir.

## Çalıştırma

```bash
cd crmt_r22_daywise
python -m pytest -q tests
python tools/run_r22.py --repetitions 60 --output-dir results
```

- `tools/day_certifier.py`: iki inverteri günlük küme düzeyinde toplayan, IID ve sınırlı destek altında DKW+union bound ile eşzamanlı marjinal risk bantları çıkaran hata denetimli algoritma.
- `tools/run_r22.py`: 7 senaryo × 60 tekrar deney, nokta-Pareto tanısı ve orijinal R16 kaynak ZIP'inden yalnız tarihsel TRAIN gün denetimi.
- `docs/R22_TURKCE_BILIMSEL_RAPOR.md`: teorem, ispat iskeleti, varsayımlar, deneyler, başarısızlıklar ve sonraki iş.
- `config/R22_GUARDRAILS.json`: bilerek açık bırakılan dış bağımsızlık/destek/TEST kapıları.
- `reference_snapshot/crmt_edge_ems/`: CRMT'nin `risk.py`, `dominance.py`, `archive.py` orijinal SHA eşleşen kopyaları (dondurulmuş kaynak değiştirilmedi).
- `reference_inputs_R16.zip`: **yalnız geçmişte incelenmiş** gerçek OpenCEM TRAIN kaynağı. Yeniden kullanılabilir kanıt; yeni TEST değildir.

## Kritik bilimsel sınırlar

1. Gerçek veri için IID günlük epizod tasarımı kanıtlanmadan herhangi bir sertifika verilmez.
2. Kullanıcıdan gelen `independence_evidence` metni bir kriptografik doğrulama veya fiziksel güvenlik yetkilendirmesi değildir. Yalnız burada kaynak kodu bilinen sentetik üretim için kullanılır. Gerçek üretimde bağımsız denetçinin imzalı protokol kanıtı ayrıca gerekir.
3. Gün içinde iki inverterin ortalaması, orijinal pooled-block CRMT riskinin aynısı değildir. Dönüştürülmüş günlük risk, farklı bir estimanddır.
4. Başarısız kapasite B=3 koşulunda arşivden keyfi kontrolcü atılmaz, yalnız araştırma kararından kaçınılır (`ABSTAIN`).
5. 60 tekrar / 0 hata, otomatik %5 FWER kanıtı değildir. Matematiksel bound ancak koşullardan gelir.
6. R19 B=10, R20 maliyet sorunları, R9 eksik eski SHA, bağımsız TEST NO-GO değişmedi.
