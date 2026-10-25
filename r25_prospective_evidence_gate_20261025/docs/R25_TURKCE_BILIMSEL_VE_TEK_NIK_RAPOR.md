# CRMT R25 — Prospektif deneyin doğrulanabilir DISCOVERY/AUDIT kilidi

**Tarih:** 25 Ekim 2026  
**Durum:** ÇALIŞTIRILABİLİR GÜVENLİK KONTROLÜ TAMAM; BAĞIMSIZ ÖN KAYIT / YENİ VERİ / YENİ DENEY EKSİK  
**Kapsam:** R19 C1/A1 F1−F0 birincil B=K=10 hipotezine hazırlık, R24 gerçek tarihsel TRAIN taraması; yeni TEST değildir.

## 1. Sorunun tanımı ve gerçekten doğrulanan kaynaklar

R24'ün özgün SHA-256 ile doğrulanan ham verileri üç tohum için ortak iki inverterli gün sayısını sırasıyla 9, 5 ve 5 olarak bulmuştur. R25, R16 kaynak ZIP'inin sabit SHA'sını ve R19 protokolünün SHA'sını kontrol eder, **R24 kaynak denetleyicisini R16 ham CSV'lerinden yeniden çalıştırır**, böylece yalnız R24 JSON'una güvenmez.

| Tarihsel tohum | 256 kontrolcünün ortak günü | R19 hedefi | Aradaki fark | B10 F0/F1 ortak üye |
|---|---:|---:|---:|---:|
| 1001 | 9 | 30 | 21 | 6/10 |
| 1004 | 5 | 30 | 25 | 9/10 |
| 1005 | 5 | 30 | 25 | 7/10 |

**Önemli yorum:** Son sütun, tarihi TRAIN üzerinden seçilmiş aday listelerinin ne kadar benzediğini gösterir, hangisinin daha iyi olduğunu değil. Eski TRAIN bloklarını bir daha kullanarak bağımsız AUDIT veya yeni kör TEST kanıtı üretmek mümkün değildir.

## 2. R19 eski kodunda saptanan kanıt kökeni açığı

R19 `score_audit` işlevinin eski arayüzü, `independent_lock_receipt` içindeki kullanıcı kontrollü HTTPS URL'sine ve `committed_before_audit=true` değerine dayanarak keşifsel çıktı üretebilmektedir. R25 negatif kontrol testi bu davranışı sahte ve tamamen sentetik bir AUDIT panosuyla göstermiştir. Bu bir kriptografik dış ön kayıt doğrulaması değildir. **Orijinal R19 kodu geriye dönük değiştirilmedi**; R25 onun yanına daha sıkı ayrı bir doğrulayıcı koyar.

### R25 yeni doğrulama ilkeleri

- DISCOVERY ve AUDIT için tam *gün kümeleri* ayrılacak: aynı günün inv1 ölçümü DISCOVERY, inv2 ölçümü AUDIT olamaz.
- R25 deney şablonunda AUDIT, DISCOVERY bitiminden sonra en az **7 tam takvim günü** boşlukla başlayacak. Bu mühendislik amaçlı bir **önceden seçilecek embargo politika örneğidir**; 7 günün bağımsızlık sağlamaya yeterli olduğu ispat edilmemiştir. Nihai embargo uzunluğu saha/veri yapısına göre önceden onaylanmalıdır.
- Tek tohumda 256 kontrolcü, 60 AUDIT bloğu (30 tam gün × 2 inverter) ve **15.360 controller–block değerlendirmesi** gerekir.
- R19 DISCOVERY seçim kilidi, R25 kaynak manifesti ve R25 gün bölmesi SHA-256 zinciriyle eşleştirilir; hash uyuşmazlığında bloklanır.
- Dış kayıt için Ed25519 imzasını bir **önceden ve bağımsız olarak onaylanan açık anahtar** altında doğrular. Anahtar paket içinde tanımlı değildir; test anahtarı gerçek projede yetki sağlayamaz.
- İmza doğruysa bile yalnızca **“imza teknik olarak geçerli, imzalayan kurumun bağımsızlığı, zaman damgası ve veri maruziyeti ayrıca teyit edilmeli”** durumu döner. Testteki imzayı gerçek bir kurumsal ön kayıt gibi ilan etmez.
- AUDIT sonuçları görülmeden son seçim kilidi ve bağımsız ön kayıt yapılmadıysa, confirmatory istatistiksel iddia engellenir.
- Gerçek fiziksel güvenlik, 256 adaylı R23 koşullu teorem ve 30 tohumun güç yeterliliği hâlâ kanıtlanmamıştır.

## 3. R25'in teknik mimarisi

1. `r25_protocol_gate.assert_reference_source()` — tarihsel kaynak, değişmeyen R19 protokolü ve R24 ham kanıtının SHA doğrulaması.
2. `historical_coverage()` — özgün R24 kaynak denetimini yeniden çalıştırır; 9/5/5 ortak gün sayısını karşılaştırır.
3. `create_split_reservation()` — AUDIT sonuçlarını girdi olarak bile kabul etmeden önceden seçilmiş gün/grup ayrımını ve en az 7 tam gün embargo şemasını denetler.
4. `lock_receipt_envelope()` — gerçek R19 seçim kilidini, AUDIT günlerini, kaynak manifestini, Git SHA'yı ve protokolü değişmez hash alanlarıyla birbirine bağlar.
5. `verify_external_signature()` — yalnız bağımsız onaylı ve dışarıdan verilen Ed25519 açık anahtarıyla imzayı doğrular, **sonuç asla kendiliğinden RUN/GO değildir**.
6. `r25_cli.py` — status, reserve, request-receipt, verify-receipt komutları. Üretilen çıktılar yalnız yeni dosyaya yazılır, eski rapor üzerine yazılmaz.

### Neden yalnız imza yeterli değildir?

İmza, özel anahtara erişen birinin mesajı imzaladığını gösterir. Kaynak dosyasının hangi tarihte üretildiğini, imzalayanın gerçekten bağımsız olduğunu, veri kümesinin önceden görülmediğini, Git tarihinin sonradan değişmediğini veya gerçek OpenCEM kaynak kullanım iznini **tek başına ispatlamaz**. Ön kayıt hizmetinin doğrulanabilir kaydı, kaynak sağlayıcı/kurum onayı, bağımsız maruziyet kaydı ve kilitten **sonra** gerçekleşen veri edinimine ait kanıt ayrı gereklidir.

## 4. Kaynak kapasitesi ve maliyet hesabı (taslak)

| Girdi | Tohum başına | 30 tohum |
|---|---:|---:|
| DISCOVERY, F0 başına | 12.600 | 378.000 |
| DISCOVERY, F1 başına | 12.600 | 378.000 |
| AUDIT, 256×60 | 15.360 | 460.800 |

F0 ve F1 değerlendirme çıktıları ortak bir ledger üzerinden **tekrar kullanılabiliyorsa** en az 378.000 DISCOVERY + 460.800 AUDIT = **838.800 farklı controller–block olayı** planlanır. Yöntemlerin DISCOVERY değerlendirmeleri ayrı yürütülür ve tekrar kullanılmazsa 1.216.800 olay kaydedilir. Bu hesap **toplam CPU eşitliği, bootstrap zamanı, RAM veya daha sonra yapılacak VALIDATION maliyetini içermez.** 30 tohumun yeterli olduğu da henüz güç analiziyle doğrulanmamıştır.

## 5. İnsan/kurum denetimindeki kapanış listesi

1. Veri sağlayıcısından gerçekten yeni, daha önce araştırmacı tarafından gözlenmemiş OpenCEM-uyumlu veri için kimlik, checksum, lisans ve geçmiş kullanım/maruziyet kayıtlarını edin.
2. Veri kaynağının tesis, takvim günü, inverter/ölçüm cihazı ve amaç birimlerini bağımsız bir araştırmacıyla doğrula.
3. R19 B10, C1/A1, 4 amaç, q=0.9, lambda=0.5, 30 planlanmış tohum (güç analizi sonrası gerektiği gibi revize edilmek üzere), embargo, 60 blok, tek hipotez ve istatistik yöntemini **veri görülmeden** sonlandır.
4. Planı bağımsız, geri dönük değiştirilemeyen kayıt altyapısında kurum yetkilisinin onayıyla zaman damgala; imzacı anahtarını bu aşamadan **önce** güven kaynağına sabitle. GitHub commit'i tek başına güvenilir dış timestamp değildir.
5. Yeni veri üzerinde tüm 256 kontrolcü için aynı AUDIT zaman noktalarını re-evaluate et. 256×60 per seed kayıtlar yoksa seçim yapma.
6. F0/F1'in aynı DISCOVERY ledger'ını ve aday listesi kimliklerini açıkça kanıtla; aynı anda native arşiv RAM, bootstrap+CPU, simülatör çağrı süresini ölç.
7. Kilitli 30 tohum sonuçlarının p-değeri/CI ve %5 pratik farkını değerlendir; TRAIN sonucu bağımsız kör TEST olarak isimlendirme.
8. Yeni, bağımsız, önceki raporlarda hiç görülmemiş TEST yalnız ayrı kaynak maruziyet onayı ve kilitli analiz tamamlandıktan sonra kullanılabilir.

## 6. Deneysel delil ve NO-GO kararları

- Gerçek geçmiş kaynaklar: SHA-256 uyumlu, yeniden işlenmiş **üç tarihsel çift**, daha önce görülmüş TRAIN.
- R25 yazılım: 30 regresyon testi, negatif ve sahte dış kilit senaryoları, altküme ve tarih sızıntısı denetimleri.
- Dış imzacı açık anahtarı: **yok**; gerçek bağımsız ön kayıt: **yok**.
- R19 2001–2030 yeni tohum çalıştırmaları: **yapılmadı**.
- Yeni 30 günlük AUDIT panosu: **yok**; örnek/test verileri hiçbir şekilde bilimsel ölçüm değildir.
- R23 gerçek OpenCEM sonlu-m güvenlik koşulları: **sağlandığı kanıtlanmadı**.
- Yayımlanabilecek yeni teyit edici üstünlük sonucu: **NO-GO**.

Bu sürüm tarihe yeni bir araştırma deneyi eklemek yerine mevcut projeye **kontrol edilebilir kanıt kökeni zinciri** ve eksik koşulların kesin listesi ekler. Eski R16, R19, R24 dosyalarına müdahale edilmez.
