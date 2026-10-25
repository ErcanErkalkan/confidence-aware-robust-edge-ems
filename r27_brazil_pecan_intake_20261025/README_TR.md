# R27 — Brazil STAR + Pecan Street kaynak gerçeklik / erişim denetimi

**Statü:** Resmî kamu metadata incelemesi + çalıştırılabilir kaynak inceleyici; **ham veri indirilmedi**; **TEST NO-GO**.

## Dosyalar
- `docs/R27_BRAZIL_STAR_PECAN_KANIT_RAPORU_TR.md`: kaynak kanıtı, fiziksel 4 hedef eşlemesi, sınırlamalar.
- `docs/PECAN_STREET_ACADEMIC_INQUIRY_EN.md`: **gönderilmemiş** üniversite erişimi/lisans talebi.
- `config/R27_VERIFIED_PUBLISHER_METADATA.json`: kaynak kanıtlarının makine-okunur sürümü.
- `tools/brazil_zip_audit.py`: lisans izinleri alınarak indirilen orijinal Brazil STAR ZIP'in yayıncı MD5 / gerçek SHA-256 / sensör yapısını denetleme.
- `tools/access_gate.py`: dış haklar ve fiziksel uyum başvurusu için fail-closed durum kaydı.
- `reference/`: R26 özgün 8-kaynak katalog ve NO-GO durum JSON kopyaları.
- `tests/test_r27.py`: sentetik ZIP güvenliği ve hak/kanıt sınırlarının otomatik testi.
- `results/`: karar ve bütünlük özeti.

`python -m pytest tests -q` 

`python tools/brazil_zip_audit.py /path/to/original.zip --out inspection.json`

**Uyarı:** Paket **gerçek Brazil STAR ZIP dosyasını içermez**; ham ölçüm lisansı ve edinimi ayrıca doğrulanmalıdır. R26 kaynak dosyaları ve R19/R25 proje statüsü değiştirilmemiştir. Hiçbir TEST koşusu yapılmamıştır.
