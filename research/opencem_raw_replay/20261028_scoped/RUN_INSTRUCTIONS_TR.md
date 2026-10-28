# İkinci adım yeniden üretim

Gerekli: Python, numpy, pandas ve GitHub CRMT main kaynak ağacı gerektirmez (analiz kendi script'iyle çalışır). Giriş dosyalarını değiştirmeden ayrı bir klasörde bulundurun.

```bash
python validate_raw_to_replay_scoped.py --raw /path/2025-08-a.csv /path/2025-08-b.csv --lineage-zip /path/CRMT_EAAI_EXACT_BIN_LINEAGE_20261020.zip --out /new/nonexistent/output
```

Program, özgün ham dosyaların SHA-256 değerlerini donmuş kanıtla karşılaştırır; uyuşmazlıkta işi başarısız sayar. Sonuç çıktı klasörü önceden mevcut olmamalıdır. Analiz yalnız mevcut iki kaynak dosyasına ait *tam kaynak destekli* blokları karşılaştırır, tüm 19 dosyayı kapsamaz.

Başarılı sonuç yalnız tarihsel mühendislik doğrulamasıdır, R19 veya bağımsız TEST yetkisi değildir.
