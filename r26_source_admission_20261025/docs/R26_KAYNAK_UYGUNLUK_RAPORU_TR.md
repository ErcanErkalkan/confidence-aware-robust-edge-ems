# CRMT R26 — Bağımsız kaynak kabulü ve deney ön kayıt hazırlığı

**Tarih:** 25 Ekim 2026  
**Durum:** PUBLIC_METADATA_SCREENING_DONE / NO_NEW_SOURCE_ADMITTED / EXTERNAL_PREREGISTRATION_NOT_VERIFIED / NO-GO  
**Veri kapsamı:** Yalnız yayıncının kamuya açık açıklamaları ve önceki R25 tarihsel kanıt ZIP'i. Dış kaynağın orijinal ölçüm dosyası indirilemedi. Yeni optimizer, TRAIN-AUDIT ya da bağımsız TEST hesaplanmadı.

## 1. Amaç ve değişmezlik

R26, R19'un C=1, A=1, B=K=10, backfill yok, λ=0,5, CVaR0.9, 4 amaç, 256 kontrolcü, her kolda 12.600 DISCOVERY değerlendirmesi ve ayrı 60 AUDIT bloklu çalışma taslağını değiştirmez. 2001–2030 başlangıç tohumları güç analizi onaylanana kadar *taslaktır*. Amaç şudur: hak sahibinin izin verdiği, daha önce hiç sonuçları incelenmemiş, fiziksel anlamı uyumlu ve yeterli zaman çözünürlüğüne sahip kaynak bulunursa onu geçerli kabul süreçlerine sokabilmek.

Yalnızca yayıncı sayfası görmek veya bir veri kümesinin 'Open' etiketine sahip olması, a) gerçek ölçümlerin inmesi, b) orijinal SHA kanıtı, c) kurumsal veri hakları, d) geçmiş maruziyet ayrıklığı, e) 2 dakikalık yük/PV/şebeke/BESS eşlemesi, f) geriye dönük olmayan ön kayıt anlamına **gelmez**.

## 2. Daha önceki envanterin doğrulanması

19 Ekim 2026 tarihli Google Drive `NEW_TEST_SOURCES_CANDIDATES_TR.md` notunda Brazil STAR, SOFIE, Polytechnic of Porto, MCUT ve PVDAQ zaten araştırma adayıydı. Dolayısıyla R26 bunları 25 Ekim 2026'da ilk defa ve kör biçimde keşfedilmiş gibi sunamaz. Drive başlık aramasında Ausgrid ve Pecan adına ayrı dosya görülmemesi de tam geçmiş maruziyet taraması değildir.

## 3. Yayıncı metadatasına göre adaylar

| Aday | Kaynak açıklaması | Önemli teknik ve hak engeli | Ön karar |
|---|---|---|---|
| Brazil STAR, Zenodo 3959739 | Dört konut, PV, batarya SOC/güç, cihaz gücü. ZIP 6,7 MB; 2018–2019 | Ada tipi mikroşebekeler; mevcut grid import/export sınırının karşılığı belirsiz; zaman çözünürlüğü ve ham dosya hash'i doğrulanmadı | **İkincil mühendislik araştırması; ana TEST değil** |
| SOFIE v6, Zenodo 21699601 | 38,4 kWh BESS, PV, sekiz EV wallbox, ada tipi mikroşebeke; 708 MB DB + 2,8 GB JSON | Şebeke sınırı eşlemesi, 2 dakikalık veri kadansı, lisans/ham dosya kanıtı doğrulanmadı | **İnceleme adayı; ana TEST değil** |
| Porto, Zenodo 15394961 | PV/yük/fiyat yıllık saatlik; batarya 15 dakikalık 24 saat profil | 2 dk ramp95 ve flips bilgisini saatlik/15dk veriden ara değerleme ile yaratmak geçersiz | **Yalnız düşük frekanslı ikincil duyarlılık** |
| MCUT, Zenodo 21212713 | Ada tipi PV/ESS mikroşebekesi; 1dk ve bazı 5 sn ölçümler | Dosyalar restricted; tek önemli olay günü; şebekeye bağlı ithalat/ihracat amaçları eşdeğer değil | **NO-GO — hak sahibi erişimi gerekli** |
| PVDAQ (OEDI) | PV saha/performans ölçümleri, tipik 15 dk ve değişken çözünürlük | Yük, şebeke sınırı ve batarya SOC aynı sahada garanti değil; eski PVDAQ v3 API kapalı | **Yardımcı PV profili; ana TEST değil** |
| Pecan Street Dataport | 1dk / 1sn ölçüm örnekleri, PV, konut tüketimi | Kurumsal üniversite erişimi ve kullanım izni; gerçek grid ölçümü, BESS SOC, dönüşüm ve haklar doğrulanmalı | **Veri talebi için öncelikli erişim araştırması; NO-GO** |
| Ausgrid Solar Homes | 300 konut, 2010–2013, 30 dk PV/yük; IEEE katalogunda CC BY4.0 belirtiliyor | 30 dk, BESS SOC ve gerçek grid kontrolcü fiziği eksik | **Birincil 2 dk TEST için uygunsuz** |
| UNSW Energy Data Platform (EDP) | 951 saha, 5 dk PV/yük, kısıtlı erişim | **Sağlayıcı şartları verileri ve erişim bilgilerini AI araçlarına paylaşmayı yasaklıyor** | **Bu ChatGPT çalışma akışına alma; herhangi bir veri indirilmedi** |

**Kaynaklar:**
- https://zenodo.org/records/3959739
- https://zenodo.org/records/21699601
- https://zenodo.org/records/15394961
- https://zenodo.org/records/21212713
- https://data.openei.org/submissions/4568
- https://github.com/openEDI/documentation/blob/main/pvdaq.md
- https://www.pecanstreet.org/2025/07/public-data/
- https://www.pecanstreet.org/access/
- https://ieee-pes-data-sharing.org/datasets/detail/5795a399-f06e-4747-b518-cb9d961616a2
- https://unsw-ceem.github.io/DARTH-docs/ausgrid300/
- https://unsw-ceem.github.io/DARTH-docs/edp/

Zenodo sayfalarındaki *Open* dosya erişim etiketleri kullanımla ilgili bütün hakların otomatik doğrulandığı anlamına gelmez. Bazı sayfalarda lisans ayrıntısı boş görünür: izinler ayrıca doğrulanmalıdır.

## 4. R25 ile kaynak bütünlüğünün yeniden bağlanması

R25 ZIP içinden özgün R16 kaynak ZIP hash'i `15a1a6aff3ca4410ccad420b261f50480d89d5effb3038a461dab04fb44255bc` ve değiştirilmemiş R19 protokol JSON hash'i `47815ffe56921e11c2272341ce9320e7bd45c9337e1c5cb90cff57dde63a1a88` yeniden hesaplanmaktadır. R25 arşivi tarihsel görülmüş TRAIN verisidir. Bu doğrulama yeni kaynak SHA'sı sağlamaz.

## 5. İki aşamalı veri kabul ölçütü

**Aşama I: Kaynak kabulü (şimdi hepsi engelli).** Yetkili kurumdan tam lisans ve AI ortamında işleme yetkisi; DOI+versiyon+orijinal byte SHA ve ham örneklem veri envanteri; sahaların OpenCEM/OPSD ile geçmiş izlenim ayrıklığının bağımsız onayı; ölçüm birimleri, saat dilimi, örnekleme kadansı ve eksik veri raporu; yük/PV/grid import-export/SOC/fiziksel limitler; 2 dakikalık veriyle dört kaybın hesaba katılabilmesi.

**Aşama II: Prospektif kilit.** Güç gerekçeli seed sayısı; değişmez DISCOVERY ve 30 günlük/60 bloklu AUDIT rezervasyonu; aynı gün/site sızıntısı ve gerekçelendirilmiş embargo; F0/F1 B10 seçim kilidi; harici güvenilir zaman damgası ve bağımsız insan onayı; ayrıca bağımsız üçüncü bir kilitli TEST grubu. Aşama II, R25 Ed25519 teknik imza doğrulamasından daha güçlü **bağımsız kayıt gözetimi** gerektirir.

**Kritik:** AUDIT içinde tutulan yeni TRAIN günleri, nihai kör TEST değildir. Geçerli TEST için ayrıca daha önce görülmemiş saha veya zaman aralığı, üçüncü bölüm ve sonuçlardan önce kilit şarttır.

## 6. R26 uygulaması

- `tools/r26_source_gate.py`: sekiz adayın zorunlu alan kontrolü, SHA iddiası denetimi, koşulsuz NO-GO kanıt kararı, eski OpenCEM/OPSD etiketlerini reddetme.
- `tools/r26_schema_probe.py`: ham CSV verisi ileride erişime uygun şekilde verilirse timestamp, site, load/PV/grid/SOC ve gerçek 1/2 dakikalık kadansı kontrol eder. Şema uygunluğu **asla** lisans, fiziksel güvenlik veya yeni TEST izni sayılmaz.
- `config/R26_SOURCE_CANDIDATES.json`: sekiz kamu metadata kaydı, `raw_sha256=null` ve `raw_retrieved=false`; dosya hash'i uydurulmaz.
- `results/R26_SOURCE_GATE.json`: makinelerce okunabilir nedenli NO-GO kayıtları.
- `config/R26_EXTERNAL_REVIEW_TEMPLATE.json`: boş imza/izin/saha/maruz kalma kanıtı formu, gerçek onay değildir.
- `tests/test_r26_source_gate.py`: olumsuz kontroller ve istem dışı kabulü önleme.

## 7. Ayrı araştırma sorunu

B10'daki kaçırma oranı yalnızca kaynak/kilit koşulları onaylandıktan sonra hesaplanabilir. R23'ün sonlu-m bağımlılık teoremi de bu dış kabul koşullarından otomatik çıkmaz. Dağılım varsayımları ayrı inceleme gerektirir. Zaman serisini daha ince örneklemek veya sabit destek aralığını gözlenen min/max ile değiştirmek bilimsel garanti üretemez.

**Son karar:** **NO-GO.** Belirlenmiş kaynak araştırma adayları var; tam dört amaçlı, iki dakikalık ve bağımsız fiziksel yeni veri, uygun hak/lisans, bağımsız ön kayıt ve yeni optimizer koşuları henüz mevcut değil.
