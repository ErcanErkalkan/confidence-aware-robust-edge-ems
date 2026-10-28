# Çalıştırma talimatı

Gerekli kaynaklar (repo ve özel Drive üzerinden):

- `SOURCE_MAIN_2dcbaa49_20261028.zip` → `source-root` içine açın.
- `CRMT_EAAI_EXACT_BIN_LINEAGE_20261020.zip` (orijinal accepted-bin kaynakları).
- `optimizer_front.csv` (seed1001 C1/A1 F0 arşivi; 18 aday).
- `optimizer_front_2.csv` (seed1001 C1/A1 F1 arşivi; 236 aday).
- `candidate_metrics.csv` (seed1001 C1/A1 F0 tarihsel TRAIN metrikleri; F1 ile eşli payload).

Paket içinde lisans/mahremiyet gerekçesiyle veri kaynaklarının kendileri bulunmaz.

```bash
python analyze_historical_metric_impact.py \
  --source-root ./SOURCE_MAIN_extracted \
  --source-zip ./SOURCE_MAIN_2dcbaa49_20261028.zip \
  --lineage-zip ./CRMT_EAAI_EXACT_BIN_LINEAGE_20261020.zip \
  --front-f0 ./optimizer_front.csv \
  --front-f1 ./optimizer_front_2.csv \
  --historic-candidate-metrics ./candidate_metrics.csv \
  --extra-f1-only 10 \
  --out ./out
```

`--extra-f1-only 0`: yalnız F0'ın 18 adayı (72 değerlendirme). `--extra-f1-only 218`: 236 üyeli tam F1 arşivi, daha uzun bir koşu; mevcut pilotun yerine geçmiş sayılmaz. Geçerli tüm koşular tarihsel, önceden maruz kalınmış TRAIN verisi olarak etiketlenir.

Gerekli Python modülleri: numpy, pandas, scipy. Kaynak kodu repo `src/` dizinindedir. Sonuç dosyaları, `--out` altında hazırlanır. Orijinal kaynak dosyalarına yazılmaz.
