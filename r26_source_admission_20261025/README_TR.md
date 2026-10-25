# CRMT R26 — Dış veri kaynakları için kanıt tabanlı kabul kapısı

**Sonuç: 8 metadata adayı incelendi; 0/8 kaynak onaylandı; yeni bağımsız TEST yok.**

Önce `pip install pytest`; sonra `python tools/r26_source_gate.py` ve `python -m pytest tests -q`.
Gerekli kaynak: `reference_inputs/R25_ORIGINAL_EVIDENCE.zip` (orijinal, SHA korumalı tarihsel kanıt). Paket veri lisansını devralmaz.

Yeni veri hak sahibi izinleri ile ayrı bir çalışma alanına indirildiğinde yalnızca
`tools/r26_schema_probe.py` şema ön kontrolünü; `verify_raw` ham SHA denetimini yapabilirsiniz. Bu işlemler ön kayıt, deney çalışması veya bağımsız TEST onayı vermez.

**Öncelik:** Brazil STAR ve SOFIE için teknik sensör ve fiziksel arayüz uygunluğu; Pecan Street için üniversite araştırma erişimi. MCUT erişim kısıtlı. Porto, PVDAQ ve Ausgrid, dört amacın 2 dakika çözünürlüklü birincil TEST karşılaştırmasını sağlayacağı doğrulanmadığından yalnız yardımcı kaynak olarak kalır. UNSW EDP şartları AI ortamında veri paylaşımını yasaklar; veri bu projeye alınmaz.

Açık protokol: bağımsız veri sahibi/kurum, maruziyet incelemesi, güvenilir dış zaman damgası, kesin güç planı, kaynakların gerçek SHA'sı, R19 yeni optimizer koşuları, gerçek TRAIN-AUDIT ve ayrı mühürlü TEST. R23 sahada sertifikalı değil.

Orijinal R19/R25 `src` dosyaları değiştirilmemiştir. Bu yeni çalışma yalnız bağımsız R26 sürüm klasörüdür.
