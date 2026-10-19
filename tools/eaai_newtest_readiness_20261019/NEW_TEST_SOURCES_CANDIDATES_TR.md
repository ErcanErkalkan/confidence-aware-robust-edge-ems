# Bağımsız TEST veri kaynakları: yalnızca uygunluk araştırması (19 Ekim 2026)

**Kritik:** Bunlar `READY_FOR_TEST` listesi değildir. Kaynaklar ve izinler doğrulanmadan, hedef dört kayıp / 2 dakikalık yeniden oynatma adaptörü sağlanmadan deney çalıştırılamaz.

| Aday | Kamu bağlantısı | Ölçüm/erişim | Bilimsel engel ve önerilen kullanım |
|---|---|---|---|
| Brazil STAR (Coventry / Amazonas) | https://zenodo.org/records/3959739 | 2018–2019; 4 farklı hanede batarya, PV ve appliance monitor; ZIP 6.7 MB, açık dosya | Ada tipi konut mikroşebekeleri; **grid import/export ve mevcut kap-ihlali eşdeğerliği doğrulanmamış**. Önce sensör, örnekleme ve lisans denetimi. Uygun olmazsa yalnız ikincil OOD/alt hedef |
| SOFIE / TU Ilmenau (v6) | https://zenodo.org/records/21699601 | 2025-12–2026-06; 38.4 kWh batarya, solar, EV şarj yükü; birden çok GB | Ada işletimi, EV şarj odaklı; grid ithalat/ihracat sınırı ve mevcut kontrolcünün fiziksel arayüzü eşleşmeyebilir. Büyük veri; kısmi meta denetimi uygun, test için önce uyarlayıcı lazım |
| Polytechnic of Porto daily EMS | https://zenodo.org/records/15394961 | Yıllık saatlik PV/yük/fiyat; gerçek batarya profilleri 15 dk | 2 dk zaman çözünürlüğü ve dört mevcut fiziksel hedef için uyumluluk yetersiz olabilir. Birincil test değil, ayrı modelleme duyarlılığı adayı |
| MCUT campus islanded ESS (restricted) | https://zenodo.org/records/21212713 | 2026 bir günlük 1 dk PV/ESS telemetry; dosyalar erişime kısıtlı | İzin ve access önce; tek gün ve ada işletimi nedeniyle birincil 118-blok benzeri saha karşılaştırması için yetersiz olabilir |

Diğer kaynak: NREL PVDAQ (https://github.com/openEDI/documentation/blob/main/pvdaq.md) çok çeşitli PV sahalarından ölçümler sağlar; **BESS + grid telemetry bir arada bulunması garanti değildir**. Kaynak/profil eşleştirmesi olmadan tam dört-hedef TEST sayılmaz.

**Önerilen karar sırası:** (i) gözlemlenmiş eski sitelerle ayrık site/veri periyodu, (ii) gerçek tam akıştan 2 dakikalık binlere yeniden örnekleme için sensör yeterliliği, (iii) grid import/export + battery SOC + PV + load ve kontrol edilebilir kaynak varlığı, (iv) izin/atıf/lisans, (v) geçmiş TRAIN/VAL/old TEST/OPSD pencereleriyle kanıtlanmış ayrıklık. Bu maddelerin hiçbirinin otomatik kabul edildiği varsayılmaz.

**Mevcut durum:** `NO_NEW_TEST_DATA_SELECTED`; eski 78 internal TEST ve geçmiş OPSD yeni kör test değildir.
