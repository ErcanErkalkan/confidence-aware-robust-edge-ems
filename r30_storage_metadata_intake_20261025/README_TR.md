# CRMT R30 — Pecan Street depolama metadata kohortu ve dış kaynak denetimi

Bu sürüm, **R19 C1/A1/B=K10** doğrulama çerçevesini değiştirmeden Pecan Street kamu metadata adaylarından depolama işaretli kümeyi analiz eder. 385 kamu metadata adayında `battery1=yes` 6, `energy_storage_system=yes` 1, kesişim 0, birleşim 7; bunlardan ≥%90 bildirilmiş 1-dk erişim 5, ≥%95 4 kayıttır. `dataid`, benzersiz fiziksel ev değil, konut-sakin eşleşmesi tanımıdır.

**Kaynak kanıt düzeyi:** Orijinal CSV dosyasının baytları indirilemedi; sayılar üçüncü taraf **normalize edilmiş kamu CSV metninin** R29 ve R30'da incelenmesinden gelir. Bu paket **özgün kamu CSV baytlarını veya lisanslı ev zaman serilerini içermez**. Testler sentetik örnek CSV'ler kullanır. Bağımsız yeni TEST yapılmamıştır.

## İçindekiler

- `tools/r30_metadata_gate.py`: özgün *yerel kamu metadata CSV* veya düzleştirilmiş kamu metin dökümünü kabul eden, hataları reddeden ve **yalnız anonim toplu sayım** üreten CLI
- `tools/verify_release.py`: bütünlük ve NO-GO doğrulayıcı
- `tests/`: sentetik veri ile otomatik testler
- `results/`: yeni, kimliksiz kamu metadata birleşimi; değişmemiş R29 sonuçları; Zenodo ZIP erişim kaydı
- `docs/`: Türkçe bilimsel inceleme ve sağlayıcı lisans sorgulaması taslağı
- `config/`: değiştirilmemiş bilimsel engel durumu

### Kullanım

```bash
python -m pytest -q tests
python tools/verify_release.py
python tools/r30_metadata_gate.py /path/to/authorized_public_metadata.csv --mode original_csv --out /tmp/r30_public_aggregate.json
```

`normalized_extractor_text` modu yalnız üçüncü taraf kamu metadata metin çıkarımlarını açıklamak içindir; yerel dosyanın SHA-256 değeri **sağlayıcı dosyasının kanıtı değildir**. Katılımcı site kimlikleri ve ham güç/SOC dizileri asla çıktı olarak üretilmez.

**GATES:** R30 public metadata DESCRIPTIVE; fiziksel dört amaç **NOT VERIFIED**; yeni 30 optimizer tohumu **NOT RUN**; dış ön kayıt **NOT VERIFIED**; kör bağımsız TEST **NO-GO**; gerçek HIL/saha güvenliği **NO-GO**.
