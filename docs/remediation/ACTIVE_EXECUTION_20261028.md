# Güncel CRMT yürütme ve kanıt indeksi — 28 Ekim 2026

PR: https://github.com/ErcanErkalkan/confidence-aware-robust-edge-ems/pull/4

Mühendislik koşuları ile bilimsel onay birbirinden ayrıdır. Tarihsel R18–R30,
özgün ham veriler ve v12/v13 bu değişikliklerle yeniden yazılmaz. Eksik özgün
execution SHA halen UNRECORDED_LOCAL_SHA'dır. R19 locked=false kalır.

Kurulum ve test:

```powershell
python -m pip install -e ".[dev,remediation]"
python -m pytest --junitxml=reports/test_results/junit.xml
```

Gerçek EMS kontrolcü/simülatörünü, sentetik tam gün mühendislik profilinde çalıştır:

```powershell
python experiments/runner/run_backend_smoke.py --out reports/engineering
```

Bu komut 4 aday, iki DISCOVERY ve iki AUDIT bloğu üzerinde toplam16 simülasyon
olayı planlar; her blok720 adet2-dakikalık adım içerir. Sonuç dosyaları mevcut
olmadan bu olaylar yürütülmüş sayılmaz. Dört amaç geleceğe özgü METRICS-v2
hesabı kullanır; tarihsel metriklerle sayısal eşitlik beklenmez.

Aynı planı aşamalı ve checkpoint doğrulayarak yürütmek için:

```powershell
python experiments/runner/run.py prepare --engineering --ems-plan reports/engineering/fixture/plan.json --data-root reports/engineering/fixture --out reports/staged
python experiments/runner/run.py report --engineering --ems-plan reports/engineering/fixture/plan.json --data-root reports/engineering/fixture --out reports/staged
```

Aşamalar: prepare, verify, gate-check, discovery, archive-build, shortlist-select,
audit, analyze, report. Her aşama önceki çıktı hashlerine bağlanır. Başarısız
veya yarıda kalmış aşama otomatik yeniden denenmez; tahsis edilmiş bütçe korunur.
Tamamlanmış checkpoint kaynak/plan/ortam/çıktı bağları değişirse reddedilir.
independent-test ve prospective çalıştırma dış yetki olmadan kapalıdır.

Ayrı mühendislik kanıtları:

```powershell
python tools/audit_source_history.py --out reports/source_audit
python experiments/calibration/run_conservative_v2.py --out reports/calibration_v2 --repetitions 80
python experiments/ablations/run_strict_factorial.py --out reports/strict_factorial
python experiments/compute/run_full256.py --out reports/compute_full256
python tools/build_final_evidence.py --out reports/final --junit reports/test_results/junit.xml
```

CAL-v2 yalnız önceden bilinen sınırlara sahip IID gün vektörleri için koşullu
bir muhafazakâr yöntemdir; gerçek verinin bu varsayımları sağladığı onaylanmadı.
Elemesiz yöntemin kapasite aşımı da açıkça raporlanır.

Faktöriyel tanılama iki optimizer seedinde C/F/A mekanizmasını inceler. Seedler
bağımsız fiziksel site değildir. F mevcut kodda yalnız son arşivi değiştirir.
Bu çalışma adaptive allocation'ın bağımsız operasyonel faydasını kanıtlamaz.

256-aday benchmarkı iki yöntem kolunda aynı512'şer gerçek EMS simülasyonunu
ayrı yürütür; kısa sentetik destek ve süreç içi yerleşik kontrolcü kullanır.
Süreç supervisor başlangıç/IPC maliyetini veya tam R19 maliyetini ölçmez.
Eşit simülatör bütçesi eşit uçtan uca hesaplama bütçesi anlamına gelmez.

CI altı Windows/Ubuntu ve Python3.11/3.12/3.14 ortamını ayrı test eder; kurulan
doğrudan/transitif paket sürümleri artifact içindeki pip-freeze.txt dosyalarında
kayıtlıdır. Bu ortam kayıtları platformlar arası tek evrensel bağımlılık kilidi
değildir. Main required-check yönetimi ayrıca yetki gerektirir.

Kalıcı kanıtlar reports/final ve Actions artifact'ındadır. Drive kanonik yeni kök:
https://drive.google.com/drive/folders/1w0H2OUWIS4nRDKYvcXI2UeeaNAvlDmFS
Artifact upload ve Drive readback kaydı ayrı doğrulanır.

Gönderim, dış TEST, HIL, saha, gerçek batarya ömrü ve hard-real-time
sertifikasyonu mevcut mühendislik koşularından çıkarılamaz.
