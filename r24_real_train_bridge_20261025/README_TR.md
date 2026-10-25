# CRMT R24 — R23'ten R19 B10 gerçek veriye köprü

- **İçerik:** kaynak SHA + gerçek OpenCEM C1/A1 TRAIN denetimi (seeds 1001,1004,1005), B10 sıralama ve gerçek aday kimlikleri, 256 adaylı ortak tam-gün sayımı, AUDIT 256×60 kapasite planı, hipotetik preflight ve 24 regresyon testi.
- **Kaynak rolü:** geçmişte incelenmiş TRAIN. Bağımsız TEST veya yeni optimizer çalıştırması yoktur.
- **Kritik yeni tespit:** B10 aday listeleri üç seed'de farklı (F0/F1 ortak aday 6,9,7); 256 kontrolcüde ortak iki-inverter günü 9,5,5.
- **Sınır:** R23 gerçek veride sertifikalanamaz; yeni veri, doğrulanmış ön-kayıt, güç ve bağımlılık kanıtları gerekiyor.

Çalıştırma:

```bash
python tools/r24_audit.py
python tools/r24_preflight.py --dry-run
python -m pytest -q tests
python tools/verify_r24.py
```

`reference_inputs/R16_ORIGINAL_SOURCE_BUNDLE.zip` SHA doğrulanmış tarihsel kaynaktır. Bu paket orijinal deney `run_summary.json` dosyalarını değiştirmez. `config/R19_PRIMARY_PROTOCOL_UNCHANGED.json` ilk R19 taslağının bir kopyasıdır, harici ön-kayıt değildir. Kapsam: yalnız C1/A1 için ham R16 kaynak dosyaları bulunan üç seed.

Ayrıntı: `docs/R24_BILIMSEL_DEGERLENDIRME_TR.md`.
