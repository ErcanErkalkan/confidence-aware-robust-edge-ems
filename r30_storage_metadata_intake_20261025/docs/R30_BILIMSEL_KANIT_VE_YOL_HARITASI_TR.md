# CRMT R30 — Pecan Street batarya kohortu ve asli kaynak kabulünün sınırları

**Tarih:** 25 Ekim 2026  
**Kapsam:** R19 C1/A1, 256 kontrolcü, B=K=10, dört orijinal fiziksel hedef değişmedi. R30 yalnız dış veri kaynağı uygunluğunu araştırır; optimizer veya bağımsız TEST değildir.

## Yönetici özeti

- Pecan Street'in halka açık `static/metadata.csv` kaynağına üçüncü taraf metin çıkarımıyla erişildi. Önceki R29'un 2.072 adet 130 alanlı `dataid` kaydı ve 385 PV+grid+solar/1-dk metadata adayı sonucu korundu. Sağlayıcının özgün CSV dosya baytları indirilmedi; resmi kaynak SHA-256 doğrulanamadı.
- 385 metadata adayında `battery1=yes` **6**, `energy_storage_system=yes` **1** kayıt; iki kümenin kesişimi **0**, birleşimi **7**. Böylece depolama bayrağı bulunmayan **378** aday var. `battery1` kümesinde 5/6 kayıt, `energy_storage_system` kümesinde 0/1 kayıt en az %90 bildirilmiş 1-dk kullanılabilirliğe sahip; birleşimde **5/7**. En az %95 eşiği için birleşimde **4/7**.
- Yedi depolama işaretli kaydın zaman aralığı en az 30 gün görünür; bu *kesintisiz*, ölçülmüş ve şebeke/PV/BESS için *eşzamanlı* 30 gün kanıtı **değildir**.
- 2019 tarihli Pecan Street sözlüğü `dataid` değerini fiziksel bina değil *konut-sakin çifti* olarak tanımlar. `grid = use - gen` fiziksel ölçümü, sözleşmesel şebeke güç sınırı/kap-ihlali hedefi ile aynı veri değildir. Aynı sözlükte daha yeni `energy_storage_system` ve `battery1` bayraklarının fiziksel veya SOC semantiği belgelendiği doğrulanmadı. Resmi sözlük: https://www.pecanstreet.org/wp-content/uploads/2019/04/Dataport-metadata-dictionary.pdf
- **Pecan Street lisansı hâlâ yazılı onay gerektiriyor**: https://www.pecanstreet.org/dataport/licenses/ sayfasında ücretli University-Funded Faculty Research adlandırmasıyla `No funded research` kısıtı aynı sütunda görülüyor. Yazılı açıklama ve AI işlem izni olmadan lisanslı veri alınmadı.
- İlgili soruları içeren mevcut bağlı Gmail **gönderilmemiş taslağı güncellendi; gönderilmedi**. Kişisel Gmail kimlikleri veya katılımcı `dataid` değerleri yayınlanmadı.
- Brazil STAR kayıt-özel lisans id'si daha önceki API-metin çıktısında `cc-by-4.0` olarak gözlendi; yeni ham ZIP indirme yine başarısız oldu. Dolayısıyla orijinal saat çözünürlüğü, LFP kimyası, şebeke kapı ve dört CRMT hedefiyle eşdeğerlik doğrulanmadı.

## Kaynak hiyerarşisi

1. **Resmî Pecan veri sözlüğü (PDF) ve fiyat sözleşmesi**: `dataid`/`grid` semantiğini ve lisans belirsizliğini destekler.
2. **Pecan kamu metadata CSV'sinin üçüncü taraf metin çıkarımı**: 385/7 gibi *betimleyici* sayımları destekler, fakat `original_csv_sha256=null`. Orijinal baytlar, kaynak imza/tarih bilgisi ve yeniden üretilebilir tam dosya mevcut değil.
3. **Herhangi bir lisanslı gerçek zaman serisi**: bu aşamada yoktur. Kullanılan test CSV'leri sentetik, gerçek katılımcı verisi değildir.
4. **Zenodo 3959739 kayıt sayfası ve önceki kayıt-özel API-metin çıkarımı**: erişim, belirtilen genel sensör kümesi ve CC BY 4.0 kaydını destekler; haklara uygunluk ham verinin uygunluğunu kanıtlamaz.

## R19 dört amaç için fiziksel eşleme matrisi

| Amaç | İstenen kaynak | R30 kamu verisindeki kanıt |
|---|---|---|
| `cap_violation_pct_total` | Sözleşmesel import limiti, gerçek/yeniden oynatılmış grid güç serisi | `grid` metadata var; sözleşme limiti **yok** |
| `lfp_cycle_loss_pct` | LFP BESS kimyası, SOC/güç, tanımlı yıpranma modeli | Depolama metadata bayrakları var; **SOC, kimya ve kayıp modeli yok** |
| `ramp95_kw_per_min` | Yerel orijinal 2-dk veya daha iyi güç ve simülasyon kontrol eylemleri | 1-dk erişilebilirlik metadatası var; ortak gerçek zaman serisi **yok** |
| `flip_per_day` | Gerçek/simüle edilmiş inverter kontrolcü aç-kapa eylemi | `solar` veya BESS bayrağı **kontrol eylemi değildir** |

Dolayısıyla **4/4 fiziksel hedef için kanıt yetersiz**, 385/7 metadata adayından hiçbiri otomatik kabul edilemez. F0 ve F1 karşılaştırmasının R19 estimandı değiştirilmedi. R23 şartlı istatistiksel güvence bu veri üzerinde sağlanmış değildir.

## Yeni çalışan kod

`tools/r30_metadata_gate.py` yalnız yerel **kamu metadata** CSV'leri için iki mod sunar: `original_csv` ve açıkça belirtilmiş üçüncü taraf `normalized_extractor_text`. Satır/başlık sayısı, `dataid` tekrarları, tarih zaman dilimi, erişilebilirlik yüzdesi, iki depolama bayrağı kesişimi ve gerçek fiziksel hedeflerin yanlış onaylanması test edilir. Kullanıcıdan verilen metadata bayrağını gerçek BESS SOC olarak kabul etmez; kişisel kayıt kimliklerini sonuç dosyasına çıkarmaz.

Kullanım örneği (yalnız doğrulanmış kamu metadata dosyası edinildikten sonra):

```sh
python tools/r30_metadata_gate.py /path/to/public_metadata.csv --mode original_csv --out /tmp/r30_screen.json
pytest -q tests
python tools/verify_release.py
```

## Öncelikli bağımsız iş akışı

1. Sağlayıcıdan yazılı **üniversite lisansı**, araştırma fon türü ve üçüncü taraf AI/cloud işleme izni alın.
2. Yalnız yayımlanabilir anonim cohort uygunluk sayısı isteyin; mümkünse **aynı cihaz/saha ve aynı zaman damgası** üzerinde PV, iki yönlü şebeke, BESS güç, SOC ve şebeke kontrat limiti bulunduğunu doğrulayın.
3. Kaynak tarafından imzalı/bağımsız zamanlı örnek veri envanteri ve yetkili hak belgesi alın; eski OpenCEM/OPSD maruziyetini bağımsız denetleyin.
4. R19'un kilitsiz internal hipotezine bağımsız ön kayıt, güç analizi ve veri ayrımını onaylatın; ancak sonra *yeni* optimizer/AUDIT çalışmasını ayrı versiyonda başlatın.
5. Yeni, gerçekten kör bağımsız TEST hakkı oluşmadan ana bilimsel üstünlük iddiası kurmayın.

**Karar:** `R30_PUBLIC_METADATA_FEASIBILITY_DONE / R19_CONFIRMATORY_NO_GO / INDEPENDENT_TEST_NO_GO`. Orijinal tarihsel kaynaklar değiştirilmedi; yeni test sonucu, üretim güvenliği veya EAAI uyumu ileri sürülmedi.
