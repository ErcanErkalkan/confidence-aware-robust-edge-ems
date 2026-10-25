# CRMT R27 — Brazil STAR sensör ve Pecan Street erişim denetimi

**Tarih:** 25 Ekim 2026  
**Sınıf:** Resmî kamuya açık kaynak metadatası + gerçek veri alımı için çalıştırılabilir kod; **ham ölçüm edinilmedi**.  
**Bilimsel statü:** `NO_GO_NEW_TEST`, `NO_GO_R19_CONFIRMATORY`, `NO_NEW_OPTIMIZER_RUNS`.

## 1. Kaynak kökeni ve ne doğrulandı?

R26'nın sekiz adaylık kaydından Brazil STAR ile Pecan Street seçildi. R26 katalog ve sonuç dosyalarının *değiştirilmemiş kopyaları* R27 `reference/` klasöründe. Bunlar eski kaynak hakkı onayını değiştirmez. 25 Ekim 2026 tarihinde aşağıdaki **yayıncı sayfaları** incelendi:

- [Brazil STAR Zenodo record V1.0](https://zenodo.org/records/3959739) (DOI 10.5281/zenodo.3959739).
- [Pecan Street access](https://www.pecanstreet.org/access/), [license tiers](https://www.pecanstreet.org/dataport/licenses/), [University sign-up](https://dataport.pecanstreet.org/), [license TOS](https://www.pecanstreet.org/pecan-street-inc-dataport-website-terms-of-service/).

**Önemli sınırlama:** Zenodo'daki 6.674.556 baytlık arşive bu ortamdan doğrudan erişim denendi, ancak ağ indirmesi başarısız oldu. **R27'de hiçbir gerçek Brazil STAR CSV satırı okunmadı, sıklığı ölçülmedi ve ham SHA-256 oluşturulmadı.** ZIP örnekleri sadece test sırasında üretilen sentetik güvenlik fixtürleridir.

## 2. Brazil STAR — Özgün veri sözlüğü (kaynak açıklaması)

Yer: Brezilya Amazonas, 2018–2019, dört ada tipi konut/saha STAR-A,B,C,D. Zenodo'da tek yayınlanmış dosya adı `Brazil_STAR_Microgrid_Monitoring.zip`, dosya büyüklüğü yaklaşık 6,7 MB; yayınlanan MD5 `b4f4bad22ba1d896937cfe555f41b25c`. MD5, dosya kontrolü için zayıf bir yayımlanmış işarettir; bağımsız saklayıcı kanıtı, lisans veya güvenli bir kriptografik imza değildir.

| Kaynak grubu | Resmen belgelenen alanlar | Tek başına ÇIKARILAMAYAN |
|---|---|---|
| Battery | timestamp, akım mA, Ah mAh, SOC %, şarj/deşarj sayıları, voltaj mV, güç W, şarj/deşarj enerji birimi 0.01 kWh | Bataryanın LFP kimyası, kontrol politikasının gerçek maliyeti, kesin yaşlanma |
| PV | timestamp, panel voltajı mV, güç W, enerji 0.01 kWh, çalışma modu 0–6 | Şebekeye ithalat/ihracat, kontrolcünün gerçek aç/kapa komutları |
| IAM | timestamp, aktif W ve reaktif güç, voltaj (birim belirsiz), IAM kimliği | Bütün ev yükünün eksiksiz kapsanması ve tek bir şebeke bağlantı sınırı |

### Dört CRMT hedefinin fiziksel eşlemesi

1. **`cap_violation_pct_total`:** Ölçülmüş grid ithalatı/ihracatı ve sözleşme limitinin tanımlanması gerekir. Resmî şemada bunlar yok; ada konutunda *grid cap ihlali* karşılaştırması **eşdeğer değil**.
2. **`lfp_cycle_loss_pct`:** SOC ve çevrim sayıları mevcut, fakat LFP hücre kimyası ve orijinal kontrollü batarya enerji denklemleri belgede doğrulanmıyor; orijinal bozunma vekili yeniden kalibre edilmeden eşdeğerlik kabul edilemez.
3. **`ramp95_kw_per_min`:** Akışın hangi sinyalden hesaplandığı, zaman çözünürlüğü ve saat dilimi ham kayıttan ölçülmeli. Basit interpolasyonla 2 dakikalık fiziksel olay uydurulamaz.
4. **`flip_per_day`:** PV durum kodu veya appliance switch hareketi, CRMT kontrolcüsünün emir değiştirme sayısıyla aynı şey değildir.

**Karar:** Brazil STAR, **ikincil sensör-şeması / off-grid OOD modelleme adayı**. Orijinal dört-hangi-amaç birincil TEST'i için uygunluğu **kanıtlanmadı**. Veri gerçek olsa bile önce orijinal ölçülen sistem ile simüle edilmiş yeni grid sınırı hedefi ayrılmalı.

**Lisans:** Kamuya açık Zenodo sayfasında `Rights / License` başlığı görünüyor fakat burada kesin lisans tanımı görüntülenmedi. Zenodo'nun genel varsayılan lisansı ilgili kaydın fiilî lisansı olarak varsayılmadı. AI ortamında işleme ve arşiv yeniden dağıtım izni ayrıca doğrulanmalı.

## 3. Pecan Street Dataport — Üniversite erişimi

- [Resmî erişim sayfası](https://www.pecanstreet.org/access/): ABD'deki veya başka ülkelerde eşdeğer seviyedeki dört yıllık yükseköğretim kurumlarının öğretim elemanı/öğrenci/çalışanlarına ücretsiz **ticari olmayan, eğitim amaçlı** erişim öngörülüyor.
- [Resmî lisans fiyat tablosu](https://www.pecanstreet.org/dataport/licenses/): **University Free** yalnız Austin 25, New York 25 ve California 25 ev olmak üzere **75 ev** ve ISO veri katmanını içeriyor. Ücretsiz lisansın kısıtlarında **fonlu araştırma yapılmaması** şartı yer alıyor. Ücretli katmanların tam proje koşulları resmî imzalı sözleşme olmadan burada onaylı sayılmaz.
- [Üniversite hesap formu](https://dataport.pecanstreet.org/): başvuru için üniversite e-posta adresi ve güncel kurum profili URL'si veya fotoğraflı kurum kimliği isteniyor. Portal açıklaması başvurunun üç iş günü içinde değerlendirileceğini bildiriyor; bu bir hizmet taahhüdü veya **onay** değildir.
- Dataport şartları lisansın sona ermesi üzerine veri kullanımının da sınırlandırılabileceğini belirtiyor. Kullanıcı yalnız bir hesap açtığı için genel yeniden dağıtım veya haricî AI işleme hakkı kazanmaz.

### Lisans karar matrisi

| Proje türü | Ön karar | Eksik kanıt |
|---|---|---|
| Bireysel, fonlanmamış üniversite araştırması | University Free hesabı için **aday** | Kurum uygunluğu ve sağlayıcı onayı |
| TÜBİTAK / Horizon / diğer fonlu araştırma | Ücretsiz katmanın kapsamı dışında olabilir; **lisans sorulmalı** | Yazılı izin ve fiyat/uygun katman |
| Bu ChatGPT oturumunda ham veri analizi | **İzin doğrulanmadı** | AI aracı/veri aktarımı ve dış işlem izni |
| CRMT'nin dört hedefiyle doğrudan fiziksel uygunluk | **Bilinmiyor** | Aynı sahada grid, PV, load, ESS SOC ve yerel zaman frekansı |
| R19 için 30 tohumlu bağımsız DISCOVERY/AUDIT | **NO-GO** | Dış kayıt, teknik kaynak ön kabulü, güvenli bölme ve yeni test erişimi |

*Not:* Ücret, şart ve veri alt kümesi değişebilir; başvuru anında imzalanan güncel sözleşme esas alınır. Kamu sayfasındaki 10.000 USD ve 15.000 USD ticari/araştırma katman fiyatları otomatik satın alma gerekçesi değildir.

## 4. Sunulan indirilebilir gerçek-ZIP denetleyici

`tools/brazil_zip_audit.py`: kullanıcı özgün dosyayı gerekli lisans/izin çerçevesinde kendi yetkili ortamında indirirse, yayıncı MD5 kontrolü, ham SHA-256, ZIP/traversal güvenlik, iç ZIP varlığı, sensör grubu ayrımı ve küçük CSV örneği sütun sayısı kontrolü yapar.

```bash
python tools/brazil_zip_audit.py /path/to/Brazil_STAR_Microgrid_Monitoring.zip --out brazil_star_raw_structure.json
python -m pytest tests -q
```

Burada JSON içindeki `is_independent_new_TEST=false` **her zaman** korunur. Analiz edilmiş dosyaların gerçek ölçüm anlamı ve geçmiş veri erişimi başka kaynaklarla denetlenmelidir. ZIP güvenliğini ve sahte onayı test etmek için testlerde küçük, sentetik örnek ZIP oluşturulur; ham Brazil STAR verisi taklit edilip sonuç gibi sunulmaz.

## 5. R27 kabul kontrolünün kapanış kararı

- Kaynak üreticisinin dosya türü ve sensör haritası: **yayıncı metadata düzeyinde değerlendirildi**.
- Brazil STAR gerçek orijinal CSV: **bu oturumda edinilemedi; incelenmedi**.
- Brazil STAR dosya lisansı ve AI aktarım izni: **belirsiz**.
- Pecan Street üniversite başvuru şartları: **resmî sayfadan doğrulandı; hesap açılmadı**.
- Pecan Street bireysel lisans: **alınmadı**.
- R26'daki sekiz adaydan kabul edilen yeni TEST: **0**.
- R19 B=10, C1/A1, 2001–2030 taslağı: **değişmedi; 30 yeni koşu çalıştırılmadı**.
- R25 bağımsız dış zamanlı ön kayıt: **yok; NO-GO**.

### Sonraki gerçek eylem

1. Pecan Street'e kullanılacak çalışma **fonlu mu, fonlanmamış mı** açıkça belirtilerek hesap ve AI işlem kapsamı sorulmalı. Kurum profili bağlantısı hizmet sağlayıcı başvurusunda kullanılabilir, özel kimlik bilgileri bu sohbete yüklenmemeli.
2. Brazil STAR kaydının fiilî lisansı ve veri aktarma izni kayda geçirilmeden ham ZIP işlenmemeli. İzin alınırsa ZIP kullanıcı denetiminde indirilmeli ve R27 koduyla incelenmeli.
3. Herhangi bir kaynağı birincil yeni TEST olarak kabul etmeden önce geriye dönük OpenCEM/OPSD maruziyeti, kaynak ayrıklığı, grid/battery fiziksel eşlemesi ve bağımsız dış ön kayıt doğrulanmalı.
