# CRMT R28 — Kamuya açık metadata ile kaynak kabul edilebilirliği ve kurumsal lisans incelemesi

**25 Ekim 2026 · Kapsam: kaynak dokümantasyonu/planlama.** Bu rapor ne katılımcı zaman serisi indirdiğini ne de yeni AUDIT/TEST çalıştırıldığını iddia eder.

## 1. Gerçekten yeni doğrulanabilen şey

Pecan Street'in herkese açık `https://dataport.pecanstreet.org/metatable` sayfasında `dataid`, `pv`, `grid`, `solar`, `egauge_1min_min_time`, `egauge_1min_max_time`, `egauge_1min_data_availability` ve 1-saniyelik kapsam metadata alanları görülmektedir. Açık tablodaki örnek satırlarda 1 dakikalık pencere ve grid/solar işaretleri aynı kayıt başına görülebilmektedir. Bu, R27'deki sadece sağlayıcının genel tanıtımından daha ileri bir **metadata şeması kanıtıdır**.

Yine de bu tabloda aynı evde **mevcut ve temiz ham grid+PV akışlarının eşzamanlı olduğu**, batarya SOC'si, LFP kimyası, inverter kontrol komutları veya sözleşmesel import sınırı kanıtlanmaz. Tablodaki uzun başlangıç/bitiş penceresi, 30 eksiksiz ortak gün demek değildir. `grid` devre etiketi otomatik olarak sözleşmesel limit değildir. Erişim onayı alınmadı, müşteri ham zaman serisi görülmedi.

## 2. Dört CRMT hedefiyle teknik eşleştirme

| Orijinal hedef | Gereken hesap/yorum | Açık metadata ile durum | Dürüst alternatif |
|---|---|---|---|
| `cap_violation_pct_total` | Denetleyicinin varsayılan şebeke limitini aşması; grid alış gücü/limit | `grid` işareti var, **sözleşmesel limit yok** | Yalnız önceden tanımlı *simüle cap* ile model-bazlı sonuç; gerçek sözleşme ihlali değil |
| `lfp_cycle_loss_pct` | LFP batarya çevrim/kayıp modeli | Batarya SOC/kimyası doğrulanmadı | Model-tabanlı sentetik batarya kaybı; saha LFP ölçümü değil |
| `ramp95_kw_per_min` | Uygun çözünürlüklü zamana bağlı grid ramp ölçümü | 1-dakika **metadata penceresi** mevcut; gerçek ham örnekler görülmedi | Yalnız izinli gerçek akış ve tam senkronizasyon sonrası keşifsel ölçüm |
| `flip_per_day` | Denetleyicinin kontrol eylemi flip olayları | Açık metadata kontrol komutu kaydetmiyor | Simüle kontrolcü flip'i olabilir; sahada gözlenen anahtarlama diye sunulamaz |

## 3. Pecan Street lisans ve fiyatlandırma riski

`https://www.pecanstreet.org/dataport/licenses/` üniversite ücretsiz paketinde 75 ev kapsamı sunuyor ve fonlu araştırmaya izin vermediğini belirtiyor. Aynı tabloda $10.000 fiyatlı **University-Funded Faculty Research** başlıklı sütunun kısıtlamasında yine `No funded research` yazıyor. Bu yazılı çelişki resmî açıklama olmadan yorumlanmamalıdır. Üçüncü taraf fonlu proje seçeneği başka bir fiyatlandırmaya yönlendiriliyor. Ayrıca Dataport lisansı süre sınırlı olabilir; kullanım ve üçüncü taraf işleyici/AI paylaşımı otomatik olarak izinli değildir. Kurumsal üyelik başvurusu yapılmadı.

## 4. Brazil STAR lisans ve fiziksel uyumsuzluk

`https://zenodo.org/records/3959739` sayfası 6,7 MB özgün ZIP için MD5 ve Battery/PV/IAM ölçümlerini gösteriyor; sayfa metin çıkarımındaki Rights/License başlığında spesifik lisans yok. Zenodo'nun genel CC BY varsayılanı bu kaydın kanıtı değildir. Resmî şema ada tipi mikroşebekeler içindir; grid alış/satış sayaçları ve kontrat limiti belgelenmemiştir. Yasal kullanım izni ve özgün veri örneklemi çözümlenmeden ham ZIP'e ilişkin ileri düzey sonuç verilmez.

## 5. Uygulanan kod

`tools/metadata_gate.py` sağlayıcının kamuya açık metadata CSV'si izinli olarak yerel şekilde edinildiğinde `grid`+`solar`+`pv`+native 1-dakika tarih/kapsam işaretlerini birlikte süzer, bozuk zaman damgalarını, yinelenen site kimliklerini ve sahte SOC alanlarını reddeder. **Metadata-suitable** hiçbir site için `approved_r19_sources` veya `new_unseen_TEST_eligible` statüsünü açmaz. Aracın testleri gerçek Pecan müşteri verilerini değil sentetik metadata satırlarını kullanır.

## 6. Bilimsel karar ve sıradaki tek uygulanabilir dış eylem

Pecan Street `licensing@pecanstreet.org` adresine hazırlanmış e-posta, sağlayıcıdan fonlu araştırma lisansını ve gerçek aynı-site PV+grid+SOC kapsamasını sorar. Zenodo araştırmacıları için ayrı, henüz adresi doğrulanmamış taslak vardır. Kullanıcı onayı/veri sorumlusu yanıtı olmadan yeni veri yüklenmez, dış ön kayıt yapılmaz, R19 tohumları başlatılmaz. Olası fiyat ve veri şemasının açıklığa kavuşmasından sonra lisanslı yerel veri incelemesi ve bağımsız ön kayıt için insan incelemesi gerekir.

### Kaynaklar

- https://dataport.pecanstreet.org/metatable
- https://www.pecanstreet.org/dataport/licenses/
- https://www.pecanstreet.org/access/
- https://www.pecanstreet.org/pecan-street-inc-dataport-website-terms-of-service/
- https://dataport.pecanstreet.org/
- https://zenodo.org/records/3959739
- https://support.zenodo.org/help/en-gb/2-content/21-can-i-get-permission-to-use-a-specific-record
- https://help.zenodo.org/docs/deposit/describe-records/licenses/
