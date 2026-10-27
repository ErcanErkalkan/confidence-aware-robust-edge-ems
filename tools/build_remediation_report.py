"""Assemble evidence-backed audit documents; no task is closed by file existence."""
from __future__ import annotations
from collections import Counter
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
WORK=Path(__file__).resolve().parents[1];ROOT=WORK.parents[1]
sys.path.insert(0,str(WORK/'src'))
from crmt_edge_ems.contracts import file_hash,canonical
DOC=ROOT/'docs/remediation';REPORT=WORK/'reports';PREFIX='03_CODE_AND_CONTROLLER/04_REMEDIATION_WORKTREE_20261027/'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def md(name,text): (DOC/name).write_text(text.strip()+'\n',encoding='utf-8')
def csvwrite(path,rows):
    with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def testcounts(path):
    root=ET.parse(path).getroot();suites=list(root) if root.tag=='testsuites' else [root]
    d={k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
    d['passed']=d['tests']-d['failures']-d['errors']-d['skipped'];return d

def main():
    DOC.mkdir(parents=True,exist_ok=True)
    history=read(REPORT/'remediation/HISTORICAL_160_RECHECK.json');pairs=read(REPORT/'remediation/HISTORICAL_PAIR_RECHECK.json')
    frozen=read(REPORT/'remediation/FROZEN_MANIFEST_RECHECK.json');packages=read(REPORT/'remediation/PACKAGE_MANIFEST_RECHECK.json')
    tests=read(REPORT/'remediation/package_tests/PACKAGE_TEST_RESULTS.json')
    current=testcounts(REPORT/'test_results/final_current_environment.xml');clean=testcounts(REPORT/'test_results/final_clean_environment.xml')
    calibration=read(REPORT/'calibration/stress_v1/summary.json');calstatus=read(REPORT/'calibration/stress_v1/status.json')
    power=read(REPORT/'statistical_validation/status.json');membership=read(REPORT/'remediation/HISTORICAL_MEMBERSHIP_RECHECK.json')
    preservation=read(REPORT/'remediation/INPUT_PRESERVATION_CHECK.json')
    build=read(ROOT/'06_MANUSCRIPT_AND_PUBLICATION/03_NEXT_REVISION/v13/V13_BUILD_CHECK.json')
    source=read(WORK/'reproducibility/current_source_manifest.json')
    records=list(csv.DictReader((ROOT/'08_OPEN_TASKS/CRMT_YAPILACAKLAR_20261027.csv').open(encoding='utf-8-sig',newline='')))
    snapshot=ROOT/'07_REPRODUCIBILITY/06_REMEDIATION_20261027/TASK_REGISTER_ORIGINAL.csv'
    if not snapshot.exists():shutil.copyfile(ROOT/'08_OPEN_TASKS/CRMT_YAPILACAKLAR_20261027.csv',snapshot)
    mapping={
    'A01':('PARTIAL','Kaynak manifesti ve eski 63 kayıt yeniden kontrol edildi; 23 içerik farkının 15 eski blobu bulundu, 8 nedeni çözülemedi.','provenance.py; tools/remediation_verify.py','test_provenance_integrity.py','8 eski manifest blobu, tam üretim entegrasyonu ve gelecek yürütme kilidi açık.'),
    'A02':('VERIFIED_COMPLETE','Yerel 14 ZIP / 261 manifest kaydı ve CRC yeniden doğrulandı; uzak HEAD okundu.','reports/remediation/PACKAGE_MANIFEST_RECHECK.json','package_tests','Kapanış yalnız erişilebilir paket baytları kapsamındadır; sağlayıcı kökeni için bağımsız attestation değildir.'),
    'A03':('VERIFIED_COMPLETE','Tek yeni durum indeksi, kanıt yolları ve kararlar oluşturuldu.','docs/remediation/CRMT_REMEDIATION_FINAL_REPORT.md','final test XML + preservation receipt','Yeni kanıtlar geldikçe sürümlü bakım gerekir.'),
    'A04':('PARTIAL','8 Google Docs okunabilir metni ve sağlayıcı revision ID/tarih metadata kaydı edinildi.','07_REPRODUCIBILITY/06_REMEDIATION_20261027/google_docs','connector readback','Metin okuması ve revision metadata ayrı çağrılardır; değişmez özgün native revision exportu yapılmadı.'),
    'A05':('VERIFIED_COMPLETE','160/160 özgün kaynak artefaktı özgün katalog SHA değerleriyle yeniden eşleşti.','reports/remediation/HISTORICAL_160_RECHECK.json','160 direct file rehashes','Yürütme kökeni A07 kapsamındadır.'),
    'A06':('VERIFIED_COMPLETE','20/20 çiftte olay ve dört bilimsel amaç eşitliği yeniden doğrulandı; strict 19 geçiş.','reports/remediation/HISTORICAL_PAIR_RECHECK.json','20 audit_arm + audit_pair calls','Bu kapsam yeni deney veya 20 bağımsız yürütme kimliği değildir; A07 açık.'),
    'A07':('BLOCKED_EXTERNAL','UNRECORDED_LOCAL_SHA olduğu gibi korunur; exception kaydı makinece okunabilir.','provenance.py','test_provenance_integrity.py','Özgün yürütmeden değişmez log veya bağımsız saklanmış receipt gerekli; yeni HEAD yeterli değil.'),
    'A08':('VERIFIED_COMPLETE','Mevcut R9 paketleme çözümü yeni çalıştırmada 34/34 geçti.','reports/remediation/package_tests/R9_LOCAL_PACKAGE.xml','34 historical package tests','Yalnız paketleme ve regresyon kapsamı; yeni R9 TEST yok.'),
    'A09':('IMPLEMENTED_NOT_INDEPENDENTLY_VALIDATED','Yeni strict_risk sonlu olmayan ve eksik desteği reddediyor; legacy risk değiştirilmedi.','contracts.py; data_adapters/validation','test_r19_primary_contract.py; test_data_lineage.py','Tüm üretim yollarına entegrasyon ve bilimsel kuyruk-destek eşiği için bağımsız protokol incelemesi açık.'),
    'A10':('BLOCKED_SCIENTIFIC','9 senaryo x 5 yöntem x 80 tekrar = 3600 sentetik kayıt; tüm eleme yöntemleri kapsama ölçütünü en az bir senaryoda kaçırdı.','calibration; experiments/calibration/run_stress.py','test_archive_calibration.py + reports/calibration/stress_v1','Geçerli bağımlılık varsayımı ve eleme faydasını koruyan kalibrasyon bulunmadı.'),
    'A11':('VERIFIED_COMPLETE','Arşiv-geneli %95 garantisi çıkarıldı; family undercoverage, false-pair ve false-removal ayrıldı.','docs/remediation/02_CONFIDENCE_CALIBRATION.md; v13 sources','calibration metrics + manuscript compile','Yeni garanti için yeni yöntem, matematiksel koşullar ve bağımsız doğrulama gerekir.'),
    'A12':('PARTIAL','Sabit R19 sözleşmesi ve strict seçim uygulandı; locked=false.','r19_primary.py; config/r19_primary_contract.json','test_r19_primary_contract.py','Etki/güç/split planı, sayısal tolerans politikası, bağımsız ön kayıt ve gerçek kaynak onayı eksik.'),
    'A13':('VERIFIED_COMPLETE','B10 çıktı sınırı; doğal arşivden seçim ve BLOCKED_CAPACITY, backfill yok.','r19_primary.py','test_r19_primary_contract.py','Native RAM limiti veya bu politikanın dış bilimsel onayı iddia edilmiyor.'),
    'A14':('IMPLEMENTED_NOT_INDEPENDENTLY_VALIDATED','DISCOVERY-only all256 minmax + Linf/L1/lexical sıralama test edildi.','r19_primary.py','test_r19_primary_contract.py','Operasyonel karar kuralının dış kilidi ve strict-v1 exact Pareto / legacy 1e-12 politikası incelemesi gerekli.'),
    'A15':('PARTIAL','Faktör sözlüğü kod/raporda açık: C tail0/.5; F point/legacy confidence; A round-robin/adaptive.','ablation.py; experiments/ablations/run_engineering.py','test_adaptive_ablation.py','Gelecek gerçek yürütme ile bütün makale çıktılarının otomatik sözlük kilidi tamamlanmadı.'),
    'A16':('PARTIAL','OS peak RSS, CPU/wall, başarısızlık dahil olay/bütçe ve yeni bootstrap faz ölçümü eklendi.','profiling; experiments/ablations/run_engineering.py','test_cost_accounting.py','Legacy study iç bootstrap/archive fazları ayrı ölçülmedi; tam256 maliyet ve enerji ölçümü yok.'),
    'A17':('PARTIAL','Ham dosya hash/özgün satır/bin/ayrı inverter/simülasyon/amaç/risk/seçim zinciri üç kısa parçada yürütüldü.','data_adapters/validation; experiments/runner/historical_engineering_demo.py','test_data_lineage.py; reports/historical_engineering/partial_trace_v2','Tam gün/tüm veri dönüşüm kökeni ve duplicate politikası kaynak bazında bağımsız doğrulanmadı.'),
    'A18':('PARTIAL','Gün/grup çakışması, embargo, exposure ve AUDIT desteği retleri çalışıyor.','data_adapters/validation; gates','test_temporal_leakage.py; test_experiment_gates.py','Yetkili gerçek kaynak/maruziyet envanteri ve onaylı split planı yok.'),
    'A19':('PARTIAL','Eşli Gaussian t güç duyarlılığı, bounded-mean CI ve koşullu sign-flip doğrulaması eklendi.','statistical_validation; experiments/statistical_validation','test_statistical_inference.py','Bağımsız birim, etki/SD belirsizliği ve n planı dışarıdan onaylanmalı; 30 seed yeterlilik kanıtı değil.'),
    'A20':('IMPLEMENTED_NOT_INDEPENDENTLY_VALIDATED','SOC geçişi, güç/grid/ramp/switch/telemetri veto; tüm adayların reddi açık blok durumudur.','safety','test_safety_veto.py','Fiziksel limit onayı ve hung controller için process-level preemption yok; HIL/saha yok.'),
    'A21':('BLOCKED_EXTERNAL','İmza/zaman/binding negatif kontrolleri R25 ilkesiyle birleştirildi; yerel geçerli imza bile kapı açmıyor.','gates; config/experiment_gates.json','test_experiment_gates.py','Doğrulanmış bağımsız otorite sicili, veri hakları/maruziyet kanıtı ve gerçek ön kayıt gerekli.'),
    'A22':('PARTIAL','Mevcut ölçüm dosyasından 3 kısa parça için gerçek ingest→simulator→metric→risk→singleton seçim kuru yürütümü.','reports/historical_engineering/partial_trace_v2','actual three simulator events; safety integration test','Tam gün ve çok adaylı gerçek veri entegrasyonu açık; ilk v1 şema hatası ayrı başarısız kayıt olarak korunur.'),
    'A23':('BLOCKED_EXTERNAL','Yeni onaylı optimizer/AUDIT başlatılmadı; scientific CLI fail-closed.','experiment_runner.py; experiments/runner/run.py','test_experiment_runner.py; test_experiment_gates.py','G0–G4 geçmeden başlatma; tam gerçek yürütme backend entegrasyonu ayrıca tamamlanmalı.'),
    'A24':('BLOCKED_EXTERNAL','Kaynak kabul şeması dört amaç için kanıt ve dosya hash kontrolü istiyor.','data_adapters/external_source_gate.py','test_external_source_gate.py','Sağlayıcı sensör, SOC/kimya/güç/grid sözleşmesi/eylem ve süre kanıtları eksik.'),
    'A25':('BLOCKED_EXTERNAL','R26–R30 metadata kapsamı korundu; kısıtlı ham veri indirilmedi, lisans kabul edilmedi.','docs/remediation/10_EXTERNAL_DATA_READINESS.md','R26–R30 package regression tests','Yetkili özgün ölçüm baytları ve AI/cloud işlem izni gerekli; yazışma gönderimi için ayrıca açık yetki gerekir.'),
    'A26':('BLOCKED_EXTERNAL','Bağımsız TEST NO_GO; tek CLI bayrağı ile açılamıyor.','gates; experiments/runner/run.py','test_experiment_gates.py; test_experiment_runner.py','Yeni uygun maruz kalmamış veri, ayrı operasyonel TEST protokolü, lisans, safety ve bağımsız kilit gerekli.'),
    'A27':('PARTIAL','v12 kaynak ZIPinden ayrı v13 taslağı, kaynak diffleri ve 34 sayfalık derleme üretildi.','06_MANUSCRIPT_AND_PUBLICATION/03_NEXT_REVISION/v13','V13_BUILD_CHECK.json; rendered PDF review','Yazar incelemesi, bütün nicel cümlelerin yeniden denetimi ve güncel kaynak doğrulaması açık; gönderime hazır değil.'),
    'A28':('PARTIAL','C01–C15 matrisi v13 düzeltmelerine bağlandı; TRAIN/VALIDATION etiketi ve maliyet sınırı düzeltildi.','docs/remediation/12_MANUSCRIPT_CLAIM_AUDIT.md; v13','V13_REVISION_RECEIPT.json; no undefined citations/overfull boxes','Tüm tablo/şekil çıkarımlarının bağımsız bilimsel incelemesi ve cover letter açık.'),
    'A29':('PARTIAL','Temiz venv kuruldu; 297 test geçti; tam transitif sürüm kilidi alındı; Windows/Linux CI tanımı eklendi.','reproducibility/requirements-remediation-full-lock.txt; .github/workflows/remediation.yml','reports/test_results/final_clean_environment.xml','Linux ve Python3.11/3.12 CI henüz yürütülmedi; gelecek fiziksel donanım kilidi açık.'),
    'A30':('PARTIAL','Başlangıç hash envanteri ve byte-identical duplicate grupları üretildi; hiçbir özgün kopya silinmedi.','07_REPRODUCIBILITY/06_REMEDIATION_20261027/BYTE_IDENTICAL_DUPLICATES.json','INPUT_PRESERVATION_CHECK.json','Aynı hash aynı rol demek değildir; anlamsal obsolete/arşiv sınıflaması tamamlanmadı.'),
    'A31':('PARTIAL','Tek yeni indeks bütün çıktı ve kararlara bağlantı veriyor.','CRMT_REMEDIATION_INDEX.md','report artifact index','Bakım sorumlusu ve periyodu kullanıcı/ekip tarafından atanmalı.'),
    'A32':('BLOCKED_SCIENTIFIC','Fiziksel ömür, saha, HIL ve hard real-time iddiaları verilmedi.','safety; v13 current evidence section','scenario-only software tests','Bu iddialar hedeflenecekse gerçek donanım, saha ve elektrokimyasal doğrulama protokolü ve ölçümleri gerekir.'),
    }
    matrix=[]
    for original in records:
        task=original['id'];status,evidence,files,test,blocker=mapping[task]
        matrix.append({'task_id':task,'original_problem':original['is'],'current_evidence':evidence,
            'implementation_change':evidence,'files_modified':files,'tests_added':test if test.startswith('test_') else 'None; existing checks rerun or connector/compile evidence',
            'tests_executed':test,'remaining_blocker':blocker,'verification_status':status,
            'scientific_status':'BLOCKED_EXTERNAL' if task in {'A07','A21','A23','A24','A25','A26'} else 'BLOCKED_SCIENTIFIC' if task in {'A10','A32'} else 'PARTIAL',
            'next_required_action':blocker})
    if {r['task_id'] for r in matrix}!={f'A{i:02d}' for i in range(1,33)}:raise RuntimeError('A01–A32 register mismatch')
    csvwrite(DOC/'A01_A32_REMEDIATION_MATRIX.csv',matrix)
    counts=Counter(r['verification_status'] for r in matrix)
    common=f'\n\nKod yolu: `{PREFIX}src/`. Test kanıtı: `{PREFIX}reports/test_results/final_current_environment.xml` ve `final_clean_environment.xml` (her birinde {current["passed"]} geçti). Bu iki yürütüm bağımsız bilimsel örneklem değildir.\n'
    md('01_SOURCE_PROVENANCE.md',f'''# Kaynak ve köken denetimi

Durum: PARTIAL. Yerel dal `remediation/az-20261027`; temel uzak commit `353b5710da298c6d51fb96452294ff117a31603e`. Kanonik kök Git deposu olmadığı için ayrı bir checkout kullanıldı. Clone sırasında README için Git durumunda içerik farkı olmayan bir stat/line-ending bildirimi oluştu; README değiştirilmedi veya commit kapsamına alınmadı.

Yeni doğrudan kontroller: **{history['passed']}/160** kaynak hash eşleşmesi; **{pairs['scientific_pairs']}/20** aynı controller–block olayları ve dört bilimsel amaç; **{pairs['strict_pass']}** strict geçiş. `seed1001/C1_F1_A1 = UNRECORDED_LOCAL_SHA` açık kalır. Diğer kayıtların SHA beyanları da bağımsız yürütme attestation'ı değildir.

63 eski manifest kaydı: 6 EXACT, 34 NEWLINE_NORMALIZED, 23 CONTENT_DIFFERENCE. Bunların 15'i için Git geçmişinde eski manifest hash'ine uyan blob bulundu; unified diffler `reports/remediation/source_diffs/` altında. 8 eski blob kontrol edilen Git geçmişinde bulunamadı: evaluator, parameter_space, replay, risk, site_model, study, OpenCEM adapter ve Windows ingest betiği. Bu sekiz farkın nedeni çözülmüş sayılmıyor. Örnek gerçek değişiklik: dominance bootstrap döngüsü vektörleştirilmiş; normalize edilmiş Python AST değişiklikleri de sürüm farkıdır, yalnız CRLF dönüşümü değildir. Özgün manifest değiştirilmedi.

`reproducibility/current_source_manifest.json` yeni kaynak byte kimliğini, çevreyi ve commit bağlamını verir; tarihsel yürütme kimliği yerine geçmez. `provenance_validation.json` BYTE_IDENTITY_ONLY kapsamındadır. Başlangıçtaki **{preservation['checked']} okunabilir dosya** son kontrolde değişmeden duruyor; 8 .gdoc yerelde byte olarak okunamadı, bağlayıcıdan metin snapshotları ayrıca edinildi.

Makine kanıtları: HISTORICAL_160_RECHECK, HISTORICAL_PAIR_RECHECK, FROZEN_MANIFEST_RECHECK, PACKAGE_MANIFEST_RECHECK ve INPUT_PRESERVATION_CHECK JSON dosyaları `{PREFIX}reports/remediation/` altında. 14 ZIP / 261 manifest girdisi ve CRC kontrolü geçti; bu yayıncı özgünlüğünün bağımsız teyidi değildir.
'''+common)
    calib_table='| Senaryo | Yöntem | Family undercoverage | False pair | False removal | Overflow |\n|---|---|---:|---:|---:|---:|\n'
    for r in calibration:
        if r['n_measured'] and r['method']!='abstain_v1':
            calib_table+=f"| {r['scenario']} | {r['method']} | {r['family_undercoverage_rate']:.4f} | {r['false_pair_declaration_rate']:.4f} | {r['false_removal_rate']:.4f} | {r['archive_overflow_rate']:.4f} |\n"
    md('02_CONFIDENCE_CALIBRATION.md','''# Confidence kalibrasyonu

Durum: BLOCKED_SCIENTIFIC. Yeni ayrı deney `CAL-STRESS-v1`: 9 senaryo × 5 yöntem × 80 tekrar = 3600 kayıt. Her ölçülebilir koşulda 399 bootstrap resample; sentetik normal kayıpların popülasyon risk farkları analitik olarak bilinir. Bu kayıplar fiziksel EMS ölçümü değildir. Özgün F1 fonksiyonu değiştirilmeden karşılaştırıldı; yeni max-T IID, circular block (L=8), Bonferroni ve abstention ayrı kimlikler taşır.

Konfigürasyon sonuçlardan önce yazıldı; **bağımsız ön kayıt yoktur**. Taslak kabul ölçütü: her geçerli senaryoda family-undercoverage oranının tek taraflı %95 Wilson üst sınırı ≤0.05. Eleme yapan hiçbir yöntem tüm senaryolarda geçmedi. Hiçbir adayı elemeyen abstention ölçütü sağladı; bu, faydalı eleme veya kapasite çözümü değildir. 12 adaylı flat-front örneğinde B10 overflow sürer.

Family undercoverage bütün sıralı aday çiftleri ve dört amaç için eşzamanlı sınır ihlalidir. False pair yanlış dominance bildirimidir. False removal gerçek Pareto adayının elenmesidir. Ayrı hesaplandılar; sayılar birbirinin yerine kullanılamaz. Eksik/unequal destek ve kronoloji boşluğu senaryoları strict wrapper tarafından her yöntemde reddedildi; bu tekrarlar oran paydasına sokulmadı.

AR(1)=0.95 sonlu-m bağımlılık varsayımını sağlamaz. L=8 yalnız önceden belirlenen stres ayarıdır; gerçek veride doğrulanmış seçim değildir. Bonferroni'nin çok küçük kuyruk olasılıkları 399 resample ile yeterince çözümlenmez; resolution bayrağı çıktıda var. Nominal arşiv garantisi kurulmadı. R22/R23'ün koşullu prototipleri bu sonuçlarla saha güvencesine dönüşmez.

'''+calib_table+f'\nHam/özet JSON ve CSV, config hash, runtime ve process peak RSS: `{PREFIX}reports/calibration/stress_v1/`. Kod `calibration/__init__.py`; test `test_archive_calibration.py`.\n'+common)
    md('03_R19_PRIMARY_PROTOCOL.md','''# R19 birincil sözleşmesi

Durum: PARTIAL. C1/A1, B=K10, 256 aday, 12.600 ortak DISCOVERY olayı, backfill=false, ΔMiss=F1−F0 korunur. Negatif fark F1 lehinedir. Dört amaç ve mean+0.5 ceil-top-10%-tail risk değişmedi. Tüm aday riskleri yalnız DISCOVERY verisinden hesaplanır; min–max referansı tüm256 adaya aittir; Linf, L1 ve lexical ID sıralaması uygulanır. Doğal arşiv üyeliği zorunludur; 10'dan az doğal aday varsa BLOCKED_CAPACITY.

AUDIT skoru tüm256 için aynı en az8 blok desteği ve DISCOVERY ile blok ayrımı ister. Teknik8-blok alt eşiği planlanan60-blok panelin yeterliliği değildir. Gün/grup/embargo kontrolü ayrıca `validate_partitions` ile uygulanır. Seed agregasyonu planlanan seedlerden eksik/tekrarlı/başarısız koşuları reddeder.

Strict-v1 Pareto karşılaştırması exact'tir; eski R19/legacy 1e-12 toleransı değiştirilmedi. Bu sayısal politika farkı açıkça sürümlenmiştir ve gerçek prospektif koşudan önce onaylanmalıdır. Eski protokol dosyası aynen kalır. `locked=false`. Eski TRAIN yeniden bölmesi ve yeni-kaynak R25 yolu aynı bilimsel kapsam diye sunulmaz.

30 seed ×12600 =378000 DISCOVERY; 30×256×60=460800 AUDIT; paylaşılan F0/F1 simülasyon çıktıları yeniden kullanılırsa toplam838800 benzersiz planlama olayı. **Bu sayıda olay yürütülmedi.** Kuru runner yalnız yapay kayıp girdileri ve aynı verilen arşivlerle seçim matematiğini test eder; özgün F1 archive-build veya EMS optimizer deneyi değildir.
'''+common)
    md('04_ADAPTIVE_ABLATION.md','''# Adaptive katkı ve faktöriyel tanılama

Durum: PARTIAL; bağımsız adaptive üstünlüğü UNSUPPORTED. Tarihsel CSV'de CRMT ve NO_ADAPTIVE dört held-out amaç vektörü **30/30 seedde tam eşit** olarak yeniden hesaplandı. Önceki rapor 30/30 seçilmiş kontrolcü kimliği eşitliği bildirir; bu çalışmada 30 seçilmiş parametre artefaktının tamamı yeniden açılmadı. Sonuç eşitliği yeni bir kimlik denetimi gibi sunulmuyor.

Kaynak incelemesi: aynı Sobol havuzu, farklı adaptive/round-robin tahsisi, risk vektörleriyle doğal arşiv ve daha sonraki ortak-normalizasyon minimax seçimi farklı aşamalardır. Aynı final seçime yakınsamaları mümkün; tek bir mekanizmayı nedensel neden diye atamak için mevcut özetler yetersizdir. Gerçek allocation ledgerleri ve seçilmiş parametreler üzerine tam30-seed karşı-olgusal analiz açık.

Yeni framework beş faktörü ayırır: confidence, adaptive, risk, output capacity, selection strategy. Küçük sentetik **gerçek EMS simülatör** regresyonu 8 optimizer ayarını, 32 faktöriyel satırı, her temel ayarda40 olayı (toplam320 gerçek simülatör controller–block olayı) yürüttü. Kapasite ve seçim stratejisi aynı optimizer çıktılarında tekrar skorlanır; bunlar ek simülatör çalışması diye sayılmaz. Tek optimizer seed ve10-dakikalık sentetik bloklar bilimsel fayda deneyi değildir.

Eşleştirme veri partition hash'i, aday havuzu hash'i, optimizer/simülasyon seedleri ve TRAIN bütçesiyle doğrulanır. Çıktıda allocation dağılımı, archive intersection/Jaccard, seçilen parametre hash eşitliği ve CPU/wall/RSS vardır. Pareto retention için tam gerçek held-out referans ve seed düzeyi belirsizlik analizi yapılmadı. Legacy study iç bootstrap/archive faz zamanı ayrı ölçülmedi; null olarak bırakıldı.
'''+common)
    md('05_COMPUTATIONAL_FAIRNESS.md','''# Hesaplama maliyeti ve adalet

Durum: PARTIAL. Yeni `CostTracker` split bazında TRAIN/AUDIT/VALIDATION/TEST olaylarını, atomik bütçe rezervasyonunu, başarısız ama ücretlenen olayları, incomplete olayları, aday maliyetini ve çakışmasız CPU/wall faz sürelerini tutar. Tekrarlı simülasyon olayını reddeder; önbellek yeniden kullanımı ayrıca açıkça belirtilmelidir. Ölçüm sırasında hata oluşsa bile süre kaydı tutulur.

Windows GetProcessMemoryInfo PeakWorkingSetSize ve POSIX ru_maxrss ayrı backendlerdir. Birim byte; kapsam process lifetime high-water mark'tır. Faza özgü RAM farkı değildir. Windows backend bu ortamda yürütüldü; Linux uygulaması için CI tanımı eklendi, Linux yürütülmedi. Enerji tahmini null; doğrulanmış ölçüm/model olmadan sayı uydurulmadı.

Eşit TRAIN simülatör sayısı, eşit shortlist kapasitesi, gerçek toplam CPU/wall/RSS ve kontrollü toplam-compute karşılaştırmaları ayrı koşullardır. Native arşiv B10 ile sınırlanmaz. Büyük archive daha fazla validation işi doğurur. Orijinal R20 Windows resource import hatası saklandı; ayrı Windows türevinde29 test geçti. Tarihsel CPU değerleri yeni ölçüm diye sunulmadı.

Yeni sentetik kalibrasyonda her tekrarın runtime/CPU/process RSS değeri ölçüldü. Küçük faktöriyel EMS regresyonunda end-to-end süre ve olaylar ölçüldü; legacy archive/bootstrap faz ayrımı ölçülmedi. Tam256 adaylı gerçek benchmark veya eşit toplam maliyet sonucu yok. Optional equal-compute optimizer tasarımı uygulanmadı; eşit süre elde etmek için algoritmalar değiştirilmedi.
'''+common)
    md('06_DATA_INTEGRITY.md','''# Veri semantiği, lineage ve sızıntı

Durum: PARTIAL. Yeni strict adapter ölçüm dosyası hash'i, özgün1-bazlı satır kimliği, UTC normalizasyonu, kaynak timezone'u, temporal bin, ayrı inverter-day ID, load/PV ve base=load−PV değerlerini bağlar. Ölçülen downstream gridpower baseline olarak kullanılmaz. Eksik/nonfinite/negatif sinyaller ve duplicate gözlemler reddedilir. Tarihsel duplicate-collapse politikası değiştirilmedi; yeni adapter default'u farklı ve açıkça sürümlüdür.

Asia/Shanghai yerel günleri korunur; başka timezone'larda DST gün uzunluğu date-range üzerinden hesaplanır. Kadans ve bin desteği doğrulanır. pandas3 datetime birimi varsayımı test sırasında bulundu, `as_unit('ns')` dönüşümüyle giderildi; kadans beklenen değerleri gevşetilmedi.

Gerçek, daha önce görülmüş 2025-08-b.csv dosyasından ilk10000 satır için açık mühendislik subset politikası uygulandı: inv1, complete/nonnegative, ilk duplicate temsilcisi. Seçilen/dışlanan özgün satırlar configte kaydedildi. Yalnız3×8-bin bitişik parça simüle edildi; tam bağımsız gün diye adlandırılmadı. Ham satır→lineage→simülasyon hash→dört amaç→risk→singleton archive/selection zinciri `reports/historical_engineering/partial_trace_v2/` altında. Varsayılan SiteConfig fiziksel gerçek diye sunulmuyor.

İlk demo v1, safety wrapper'ın metrik şemasında grid-cap sütunları eksik olduğu için başarısız oldu. Hata saklandı; wrapper düzeltildi ve v2 ayrı dizinde çalıştırıldı. Yeni negatif testler duplicate/same-day/group overlap/embargo/exposed external TEST/NaN desteğini reddediyor. Bu yapısal kontroller yetkili gerçek maruziyet attestation'ının yerine geçmez. Tüm19 ham parçanın uçtan uca bilimsel lineage doğrulaması tamamlanmadı.
'''+common)
    md('07_POWER_AND_INFERENCE.md',f'''# Güç ve çıkarım

Durum: PARTIAL; onaylı örneklem planı yok. Birincil birim sabit veri kümesine koşullu optimizer seed farkıdır; zaman blokları seed sayısı yerine kullanılamaz. Paylaşılan veri üzerinde30 optimizer seed yeni30 bağımsız site değildir. ΔMiss bounded [-1,1].

Kod mean-null için eşli-fark t testi ve t-CI duyarlılığı sunar: iid Gaussian farklarda exact, diğer dağılımlarda ancak uygun asimptotik koşullarda yorumlanır. Independent bounded farklar için konservatif Hoeffding mean-CI ayrıca verilir. Sign-flip varsayımı açıkça belirtilmeden p-değeri üretilmez; bağımsız simetrik farklar veya geçerli paired randomization gerekir. Sıfır ortalama tek başına yeterli değildir. Monte Carlo p hesabında +1 düzeltmesi ve MCSE vardır; küçük n için tüm2^n işaret kombinasyonları kullanılır.

Gaussian model duyarlılığında n=30 ve |ΔMiss|=.05 için güç: SD=.05 →{power['n30_effect05_power']['0.05']:.4f}; SD=.10 →{power['n30_effect05_power']['0.1']:.4f}; SD=.20 →{power['n30_effect05_power']['0.2']:.4f}. Bu değerler gerçek paired SD tahmini,80% güç garantisi veya onaylı n değildir. Etki eşiği, SD belirsizliği, site/zaman bağımlılığı, multiplicity ve failed-run politikası önceden incelenmeli. Yeni confirmatory sonuçlar görülerek n değiştirilemez.2001–2030 yalnız taslak seed listesidir.

54 satırlı duyarlılık CSV ve güç eğrisi `reports/statistical_validation/` altında. Bu bir model planlama artefaktıdır; operasyonel sonuç değildir. Teknik referanslar: [SciPy paired permutation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.permutation_test.html), [one-sample t](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_1samp.html), [bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html). Bibliyografik atıf gibi bu kaynaklara yeni bilimsel garanti atfedilmez.
'''+common)
    md('08_PHYSICAL_SAFETY.md','''# Fiziksel güvenlik veto arayüzü

Durum: IMPLEMENTED_NOT_INDEPENDENTLY_VALIDATED. `SafetyLimits` finite geçerli SOC, enerji, verim, timestep, charge/discharge, import/export, command-ramp, switches ve step-süre sınırlarını ister. `simulate_checked` kabul edilen SOC geçişinden önce veto uygular; enerji geçişi clipping ile gizlenmez. Geçersiz command/telemetri, controller exception, uygunsuz zaman desteği, timeout ve constraint ihlalleri denetlenebilir failure code üretir. Tam reddedilmiş aday popülasyonu BLOCKED_ALL_CANDIDATES_REJECTED verir.

Bu arayüz causal ControllerBase step imzasını destekler; MPC/cloud-dependent arayüzleri eşdeğer olduğu varsayılıp sessizce çalıştırılmaz. Post-step timeout geri dönmüş yavaş çağrıyı algılar; hung process'i durduramaz. Process-level preemption, retry/timeout koordinasyonu ve bütün üretim optimizer yollarına veto entegrasyonu açık. Geçersiz seedleri seçerek çıkarmak yasaktır; R19 seed agregasyonu tam planlanan seed setini ister.

Tüm limitlerin basis'i SCENARIO_ASSUMPTIONS_NOT_CERTIFIED. Site-specific verified parametre ve yetkili fiziksel limit kanıtı yoksa saha güvenliği iddia edilmez. Mevcut kontrolcü ile küçük gerçek simülatör entegrasyonu test edildi; HIL, field deployment, hard real-time ve elektrokimyasal ömür sertifikası yok.
'''+common)
    md('09_PREREGISTRATION_AND_GATES.md','''# Ön kayıt ve bilimsel kapılar

Durum: BLOCKED_EXTERNAL. G0–G7 JSON her kapı için status, required_evidence, verification_method, evidence_hash, blocking_reason, reviewer_or_authority ve last_checked taşır. Kaynak byte doğrulaması bağımsız yürütme yetkisi değildir. Güncel CONFIRMATORY_STATUS=NO_GO ve locked=false.

R25'in temel ayrımı korunur: geçerli Ed25519 imzası yalnız anahtar sahipliğini gösterir; kurum yetkisi, bağımsızlık, ön kayıt veya veri körlüğünü göstermez. Yeni verifier binding, geçerli zaman aralığı ve imzayı denetler. Sahte, expired, future, mismatched ve internal substitute örnekler reddedilir. Test sırasında bellekte oluşturulan geçerli yerel imza bile scientific gate'i açamaz; sertifika/anahtar dosyası diye kaydedilmedi.

**Olumlu bağımsız yetkilendirme backend'i bu sürümde kurulu değildir.** Bu bilinçli ve açık bir eksiktir; tüm gerçek scientific komutlar fail-closed kalır. Gerçek otorite registry'si, provider/exposure belgeleri, değişmez ön kayıt ve bağımsız reviewer doğrulaması haricî güven zinciriyle kurulmadan hiçbir boolean/URL/config değişikliği deneyi yetkilendirmez. Gate motoru dış gerçekliği yerel olarak kanıtladığını iddia etmez.
'''+common)
    md('10_EXTERNAL_DATA_READINESS.md','''# Dış veri kabul hazırlığı

Durum: BLOCKED_EXTERNAL. R26–R30 sonuçları tarihsel metadata taramasıdır; güncel lisanslı ölçüm erişimi veya yeni kabul edilmiş veri yoktur. Pecan Street için saklama/batarya bayrağı SOC, LFP kimyası, action serisi veya grid contract limiti değildir. Brazil STAR sağlayıcı özgün ölçüm ZIP'i ve yeterli hak kanıtı bu çalışmada edinilmedi. Kısıtlı veri indirilmedi, lisans kabul edilmedi, e-posta gönderilmedi.

Yeni validator source identity, official download, license, AI/cloud izinleri, resolution, PV/load/grid, battery presence/SOC/chemistry/power, grid contract, action observability, continuous coverage ve exposure alanlarını ister. Her dört amaç somut ölçümlere veya önceden bildirilmiş model varsayımlarına bağlanır. Typed64-karakter hash tek başına incelenmiş kanıt sayılmaz: explicit evidence_root altındaki content-addressed dosya byte hash'i eşleşmelidir.

ACCEPTED sınıflaması yalnız belge/byte tamlığı taramasıdır; sağlayıcı özgünlüğü ve bilimsel yetki kabulü değildir; independent_test_ready her durumda false. Gerçek yetki ayrı bilimsel kapılardadır. Mevcut adaylar için hak/ölçüm/maruziyet belgeleri yokken INSUFFICIENT_EVIDENCE/LICENCE veya DOWNLOAD blokları korunur.

İstenen dış kanıtlar: sağlayıcı kimliği ve değişmez kaynak URL; orijinal dosya/hash; kullanım ve AI/cloud lisansı; sensör/birim/kadans/timezone envanteri; eşzamanlı PV-load-grid-battery/SOC/power/kimya; grid sözleşmesi veya önceden gerekçelenmiş model; control action/mode serisi; kesintisiz coverage; önceden maruziyet ve kör açılış kayıtları; bağımsız kaynak/safety reviewer onayı. Dört hedefe uygunluğu belge olmadan metadata ile doldurmak yasaktır.
'''+common)
    md('11_EXPERIMENT_EXECUTION.md','''# Deney runner'ı ve tekrar üretim

Durum: PARTIAL. CLI prepare, verify, dry-run, gate-check ve tüm istenen scientific komut adlarını tanır. prepare/verify mevcut kaynak manifestini hash ile kontrol eder. dry-run sadece açık etiketli yapay risk gözlemleriyle çalışan mühendislik pipeline'ıdır; orijinal F1 veya EMS simulator yürüttüğünü iddia etmez. Gerçek discovery/archive-build/shortlist-select/audit/analyze/independent-test/report kapı eksikliği nedeniyle çıkış kodu2 ile durur. Tam gerçek-deney backend'i bu sürümde entegre edilmedi.

Checkpointler config/seed/source-binding, stage input hash ve output hash'e bağlanır. Resume aynı stage girdilerini ve artefakt baytlarını doğrular; hash değiştirilmiş veya eksik çıktı complete sayılamaz. Eksik aşama ve failure kaydı açık kalır. Concurrent lock çakışması reddedilir; crash sonrası stale lock kullanıcı incelemesi olmadan silinmez. Orphan saf sentetik dönüşüm çıktısı ancak aynı girdilerle tam yeniden hesaplama ve byte eşitliği sonrası kullanılabilir. Bu davranış gerçek simulator run retry politikası değildir.

Gerçek kayıtlı yürütümler: sentetik istatistik kalibrasyonu3600 kayıt; küçük faktöriyel EMS320 simülatör olayı; historical exposed partial-trace demo3 simülatör olayı. Hiçbiri yeni onaylı R19 DISCOVERY/AUDIT veya independent TEST değildir. 838800 olay yalnız planlama toplamıdır.

Çalıştırma dizini `03_CODE_AND_CONTROLLER/04_REMEDIATION_WORKTREE_20261027`. Güvenli tekrar komutları final raporda; nonempty deney çıktı dizinleri korunur, yeni tekrar için yeni isim seçilir. Kaynak manifesti üretim kilidi değildir; önce yeni commit/ortam/protokolün onaylı yürütme kaydı gerekir.
'''+common)
    claimrows=list(csv.DictReader((ROOT/'06_MANUSCRIPT_AND_PUBLICATION/03_REVISIONS_20261027/CLAIM_EVIDENCE_CURRENT.csv').open(encoding='utf-8-sig',newline='')))
    claimtable='| İddia | v13 izin verilen kapsam | Hâlâ açık |\n|---|---|---|\n'
    for r in claimrows:claimtable+=f"| {r['id']} | {r['izin_verilen_ifade'].replace('|','/')} | {r['kapsam'].replace('|','/')} |\n"
    md('12_MANUSCRIPT_CLAIM_AUDIT.md',f'''# v13 yayın iddiası denetimi

Durum: PARTIAL. v12 PDF/ZIP aynen korundu. Ayrı v13 orijinal LaTeX kaynağından üretildi; abstract, introduction/related-work ifadeleri, methodology confidence tanımı, results kalite etiketi, discussion, limitations, reproducibility ve conclusion değiştirildi. Yanlış etiket taşıyan optimizer-quality grafikler özgün CSV sayılarıyla yeniden çizildi; iki eski vektör şeması v13'te açık evidence-layer metin şemasıyla değiştirildi. Sayısal tarihsel tablolar korunur; yeni operasyonel sonuç yazılmadı.

C07 ölçüm adı: **Validation-evaluated approximation-set quality of TRAIN-generated fronts.** Eşit TRAIN bütçesi eşit toplam maliyet diye sunulmuyor. C03 için30/30 objective eşitliği yeni CSV kontrolü, selected-controller kimlik eşitliği ise önceki rapor kapsamı olarak ayrıldı. C11 evrensel subset çıkarıldı; C12 archive95% garantisi kaldırıldı. R22/R23 koşullu, R19 taslak, R26–R30 metadata olarak sınırlandı. LFP proxy ve HIL/field/hard-real-time sınırlamaları açık.

MiKTeX pdflatex + BibTeX ile **{build['pages']} sayfa** derlendi; final logda undefined citation/reference veya overfull kutu yok. Önceki tüm35 sayfa contact sheetlerde, başlık düzeni düzeltmesinden sonra final başlık ayrıca gözden geçirildi. Bu, bilimsel hakem/yazar onayı değildir. Orijinal bibliography korunmuş, her referansın yayıncı metadatası bu çalışmada bağımsız yeniden doğrulanmamıştır. Yazar beyanı/onayı uydurulmadı; taslak açıkça author-review-pending'dir. Cover letter ve bağımsız tam nicel iddia doğrulaması açık.

{claimtable}

Kaynak/diff/build fişleri: `06_MANUSCRIPT_AND_PUBLICATION/03_NEXT_REVISION/v13/`. Doğrulanmış yeni operational TEST veya preregistration yokken MANUSCRIPT_V13_READY=PARTIAL; submission-ready değil.
''')
    state={'SOFTWARE_READY':'PARTIAL','REPRODUCIBILITY_READY':'PARTIAL','R19_PROSPECTIVE_READY':'NO','INDEPENDENT_TEST_READY':'NO','MANUSCRIPT_V13_READY':'PARTIAL','Q1_SCIENTIFIC_CLAIMS_SUPPORTED':'PARTIAL'}
    acceptance=[
        ('1','Current source identity','PARTIAL','Current byte manifest, base commit and environment captured; historical drift8 and future execution lock remain.'),
        ('2','160 source artifacts','VERIFIED_COMPLETE','160/160 new direct rehashes match historical catalog.'),
        ('3','Execution SHA exception','BLOCKED_EXTERNAL','UNRECORDED_LOCAL_SHA explicitly retained, no later HEAD substitution.'),
        ('4','Tests','PARTIAL','297 current +297 clean passed;419 package tests passed; originalR20 collection error; Linux CI not run.'),
        ('5','Lineage','PARTIAL','Three short historical trace pieces have full hash chain; all-source/day certification absent.'),
        ('6','Paired F0/F1','VERIFIED_COMPLETE','20/20 historical scientific event/objective pairs newly checked.'),
        ('7','B10 semantics','VERIFIED_COMPLETE','Output shortlist only, natural membership, no backfill; capacity blocks tested.'),
        ('8','Deterministic selection','VERIFIED_COMPLETE','DISCOVERY minmax/Linf/L1/lexical ties and reproducible synthetic resume tested.'),
        ('9','Archive confidence calibration','BLOCKED_SCIENTIFIC','No elimination method passes all required synthetic scenarios.'),
        ('10','False removal vs undercoverage','VERIFIED_COMPLETE','Separate ground-truth metrics,3600 records with blocked-support denominators explicit.'),
        ('11','Adaptive contribution','BLOCKED_SCIENTIFIC','Historical held-out30/30 outcome equality; small pilot is not independent benefit evidence.'),
        ('12','Full cost fairness','PARTIAL','Instrumentation and small measured examples; legacy internal phases/full256 cost absent.'),
        ('13','Inference justified','PARTIAL','Assumptions explicit and alternatives implemented; actual confirmatory assumptions unapproved.'),
        ('14','Power defensible','PARTIAL','Model curves/tables generated;30-seed power depends on unknown paired SD and external plan approval.'),
        ('15','Safety enforced','PARTIAL','New opt-in veto tested; not all legacy pipelines integrated, no physical authority or hung-process supervisor.'),
        ('16','Leakage prevented','PARTIAL','Structural negative checks; real exposure cannot be established from a local flag.'),
        ('17','New external source accepted','BLOCKED_EXTERNAL','No eligible authorized new measurement dataset admitted.'),
        ('18','Externally preregistered','BLOCKED_EXTERNAL','No genuine independent registry/receipt installed.'),
        ('19','New confirmatory AUDIT','NOT_STARTED','No authorized new experiment run.'),
        ('20','Independent operational TEST','BLOCKED_EXTERNAL','NO_GO, eligible new data/protocol/authority absent.'),
        ('21','Manuscript supported claims','PARTIAL','Separate v13 corrected and compiled; full author/scientific/reference review pending.'),
        ('22','A01–A32','PARTIAL','All32 mapped; no global success percentage used.')]
    csvwrite(DOC/'ACCEPTANCE_22_QUESTIONS.csv',[{'question':q,'subject':s,'status':t,'evidence':e} for q,s,t,e in acceptance])
    audittable='| No | Konu | Durum | Kanıt / sınır |\n|---:|---|---|---|\n'+''.join(f'| {q} | {s} | {t} | {e} |\n' for q,s,t,e in acceptance)
    md('A_Z_FINAL_AUDIT.md','# A–Z kabul denetimi\n\nMühendislik, bilimsel geçerlilik ve dış yetki tek başarı yüzdesine dönüştürülmedi.\n\n'+audittable+'\n\n'+json.dumps(state,indent=2))
    tasktable='| Görev | Durum | Kalan gereksinim |\n|---|---|---|\n'+''.join(f"| {r['task_id']} | {r['verification_status']} | {r['remaining_blocker']} |\n" for r in matrix)
    commands=r'''```powershell
Set-Location '03_CODE_AND_CONTROLLER/04_REMEDIATION_WORKTREE_20261027'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r reproducibility/requirements-remediation-full-lock.txt
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --override-ini addopts= -q tests --junitxml=reports/test_results/recheck.xml
.\.venv\Scripts\python.exe experiments/runner/run.py verify
.\.venv\Scripts\python.exe experiments/runner/run.py gate-check
.\.venv\Scripts\python.exe experiments/runner/run.py dry-run --out reports/runner/recheck_NEW
.\.venv\Scripts\python.exe tools/remediation_verify.py audit
.\.venv\Scripts\python.exe tools/remediation_verify.py tests
.\.venv\Scripts\python.exe experiments/calibration/run_stress.py --out reports/calibration/recheck_NEW --repetitions 80 --n-boot 399
.\.venv\Scripts\python.exe experiments/ablations/run_engineering.py --out reports/ablations/recheck_NEW
.\.venv\Scripts\python.exe experiments/statistical_validation/power_plan.py
```

`_NEW` dizinleri boş/henüz oluşturulmamış olmalıdır. Kaynak manifesti değiştirilmişse verify durur; bilinmeyen farkı gizlemek için manifesti yeniden üretmeyin. Bilerek yeni sürüm hazırlanıyorsa `tools/remediation_verify.py manifest` yeni manifest üretir; bu bağımsız yürütme veya dış onay değildir. Paket testi Windows'ta özgün R20'nin bilinen resource import hatasını da raporlar. Bu süreç `git push`, merge, veri lisansı kabulü veya yayın yapmaz.
'''
    package_pass=sum((r['tests']-r['failures']-r['errors']-r['skipped']) for r in tests if r['tests'] is not None)
    md('CRMT_REMEDIATION_FINAL_REPORT.md',f'''# CRMT mühendislik ve bilimsel iyileştirme raporu — 27 Ekim 2026

**Karar: KISMİ.** Çalışan, test edilmiş yeni mühendislik altyapısı ve ayrı v13 iç taslağı üretildi. Arşiv-geneli güven kalibrasyonu bilimsel olarak kapanmadı; yeni dış veri, bağımsız ön kayıt, onaylı R19/AUDIT ve bağımsız TEST yok. Tam A–Z tamamlandı iddiası yapılmıyor. Yerel dal `remediation/az-20261027`; kaynak commit'i `{source['git_head']}`; byte-manifest içerik hash'i `{source['content_sha256']}`. Uzak push/merge/yayın yapılmadı. Özgün kaynak/veri/manifest/v12 ve başlangıçtaki {preservation['checked']} okunabilir dosya korunmuştur.

## Doğrudan doğrulanmış sonuçlar

- {history['passed']}/160 tarihsel artefakt hash'i;20/20 eşli bilimsel ledger/amaç;19 strict geçiş;1 özgün SHA istisnası.
- 14 ZIP /261 manifest kaydı /CRC yeniden doğrulandı. F0⊆F1 yalnız18/20 çiftte.
- Mevcut GitHub kaynak başlangıcında197 test geçti. Değişiklik sonrası{current['passed']} test; temiz venv'de{clean['passed']} test geçti.100 yeni test var. Bunlar ayrı yürütümler; tek bağımsız örneklem sayısı gibi toplanmaz.
- Ayrı tarihsel paket tekrarında{package_pass} test geçti; özgün R20 Windows'ta1 toplama hatası verdi. Yeni100 testin ilk turunda4 hata bulundu (datetime birimi); düzeltildi. Sonradan gerçek-trace entegrasyonunda metrik şeması eksikliği bulundu, v1 başarısız kaydı korundu ve v2 ayrı çalıştı.
- Yeni sentetik kalibrasyon3600 kayıt; küçük faktöriyel EMS320 simülatör olayı; exposed historical partial trace3 olay. Hiçbiri yeni onaylı R19 veya independent TEST değildir.
- V13 orijinal kaynaktan ayrı hazırlandı,34 sayfa derlendi; author review pending.

## Önemli kod değişiklikleri

`contracts.py`: finite bilimsel girdiler ve risk; `provenance.py`: güvenli manifest yolları ve hash, korunmuş SHA istisnası; `r19_primary.py`: paired DISCOVERY, all256-normalization, Linf/L1/ID ve doğal B10/no-backfill; `calibration/`: ayrı yöntem kimlikleri ve bilinen-gerçeklik metrikleri; `profiling/`: atomik bütçe ve OS RSS; `safety/`: clipping öncesi geçiş vetosu; `statistical_validation/`: koşullu çıkarım/güç; `data_adapters/validation/`: satır/bin/inverter lineage ve embargo; `external_source_gate.py`: dört-amaç evidence screening; `gates/`: R25 ilkesiyle fail-closed; `experiment_runner.py`: hash-bound sentetik checkpoint/resume. Legacy F0/F1 modülleri değiştirilmedi.

Kaynak/test değişikliklerinin tam listesi `SOURCE_CHANGESET.csv`; üretilen kanıt dosyaları ve hashleri `DELIVERABLE_FILE_INDEX.csv` içindedir. Kaynak checkout'ın değişmemiş upstream dosyaları yeni bir araştırma uygulaması gibi sunulmaz. Tam okunabilir baseline envanteri, import dependency graph ve duplicate hash grupları `07_REPRODUCIBILITY/06_REMEDIATION_20261027/` altında.

## İstatistiksel ve yöntemsel sonuç

Eleme yapan legacy F1, max-T IID, blok max-T ve bootstrap Bonferroni bütün geçerli senaryolarda taslak kapsama ölçütünü sağlayamadı. StrongAR1 near senaryosunda false-removal oranı max-T IID .1375, blok max-T .0125; family undercoverage ikisinde de1.0. IID clear senaryosunda family undercoverage legacy .80, max-T IID .15, blok max-T .475. Bu yeni sentetik fixture sonuçları eski R21 sayılarıyla aynı deney gibi birleştirilmez. Abstention eleme yapmadan kapsama ölçütünü sağladı; kapasiteyi çözmüyor.

Tarihsel CRMT/NO_ADAPTIVE objective vektörleri30/30 eşitliği tekrar doğrulandı.30/30 seçilmiş parametre kimliği bu tur yeniden üretilemedi; önceki rapor olarak etiketli. Küçük faktöriyel tanılama bağımsız adaptive fayda göstermez. n30, effect .05 için Gaussian güç SD=.1'de{power['n30_effect05_power']['0.1']:.3f}, SD=.2'de{power['n30_effect05_power']['0.2']:.3f}; yeterlilik onayı değildir. Sign-flip arbitrary mean-null için exact diye sunulmaz.

## Yeniden üretilemeyen veya açık kalan kapsam

8 eski frozen-manifest blobu; özgün eksik execution SHA; tam30-seed seçilmiş-parametre kimlikleri ve bütün operasyonel istatistiklerin bağımsız tekrarı; tüm ham veride/daylerde lineage; gerçek saha bağımlılık/fiziksel sınır varsayımları; tam256 total-compute benchmark; legacy iç bootstrap faz maliyeti; Linux/Python3.11/3.12 CI; process-level hung-controller supervision; olumlu bağımsız-authority backend'i; gerçek onaylı deney backend entegrasyonu. Sekiz Google Docs metni ve revision metadata okundu; native immutable revision export yapılmadı.

## Dış bilimsel engeller

Özgün SHA için immutable yürütme kanıtı; sağlayıcı orijinal measurement baytları ve AI/cloud hakkı; SOC/kimya/command/grid-contract fiziksel uygunluk kanıtı; yetkili exposure envanteri ve split/embargo incelemesi; etki/SD/güç/missing-run/multiplicity planı; bağımsız ön kayıt ve doğrulanmış otorite; yeni bağımsız operasyonel TEST protokolü; yazar/hakem ve release onayı. Yerel anahtar, URL, boolean, synthetic veri veya sonraki HEAD bunların yerine geçmez.

## Makale kapsamı

C07 etiketi VALIDATION üzerinde ölçülen TRAIN-generated front kalitesi olarak düzeltildi. Confidence/adaptive bağımsız üstünlüğü, arşiv95% garantisi, universalOOD, physical lifetime, HIL/field/hard-real-time iddiaları verilmedi. C08–C10 provenance istisnasını açıkça taşır. C11 yalnız18/20 subset. C13 koşullu prototip; C14 taslak; C15 metadata. Özgün bibliography korunur; atıflar burada yeni bağımsız bibliyografik incelemeden geçmiş sayılmaz. V13 gönderime hazır değildir.

## A01–A32

{tasktable}

Makine matrisi özgün problem, kanıt, değişiklik, dosya, test, kalan engel, verification/scientific status ve sonraki eylemi ayrı sütunlarda içerir. Durum dağılımı: {dict(counts)}. Bu dağılım bilimsel başarı yüzdesi değildir.

## Tekrar üretim komutları

{commands}

## Açık karar

```text
SOFTWARE_READY = PARTIAL
REPRODUCIBILITY_READY = PARTIAL
R19_PROSPECTIVE_READY = NO
INDEPENDENT_TEST_READY = NO
MANUSCRIPT_V13_READY = PARTIAL
Q1_SCIENTIFIC_CLAIMS_SUPPORTED = PARTIAL
```
''')
    # Machine-readable summary and single discoverable index.
    (DOC/'FINAL_STATUS.json').write_bytes(canonical({**state,'historical_artifacts':history['passed'],'paired_scientific_checks':pairs['scientific_pairs'],
        'strict_preflight_pass':pairs['strict_pass'],'current_tests':current,'clean_tests':clean,'package_successful_tests':package_pass,
        'package_collection_errors':sum(r['errors'] or 0 for r in tests),'new_synthetic_calibration_records':calstatus['output_rows'],
        'original_readable_inputs_preserved':preservation['all_preserved'],'task_status_counts':dict(counts)}))
    index='''# CRMT remediation — tek çıktı indeksi

27 Ekim2026. Yeni yerel mühendislik çalışması; bilimsel/dış yetki kapıları kapanmadı.

- [Nihai Türkçe rapor](docs/remediation/CRMT_REMEDIATION_FINAL_REPORT.md)
- [A01–A32 matrisi](docs/remediation/A01_A32_REMEDIATION_MATRIX.csv)
- [22 kabul sorusunun denetimi](docs/remediation/A_Z_FINAL_AUDIT.md)
- [Makine kararları](docs/remediation/FINAL_STATUS.json)
- [Dosya/kanıt indeksi](docs/remediation/DELIVERABLE_FILE_INDEX.csv)
- [Kaynak değişiklikleri](docs/remediation/SOURCE_CHANGESET.csv)
- [Yeni çalışma kopyası](03_CODE_AND_CONTROLLER/04_REMEDIATION_WORKTREE_20261027/)
- [V13 iç çalışma taslağı](06_MANUSCRIPT_AND_PUBLICATION/03_NEXT_REVISION/v13/)

Alt denetimler `docs/remediation/00_BASELINE_AUDIT.md`–`12_MANUSCRIPT_CLAIM_AUDIT.md` altında. Özgün27 Ekim durum kayıtları ve görev listesi değiştirilmedi. Bu yeni indeks önceki raporları tarihsel bağlamlarıyla koruyarak yeni kanıtı ekler. Remote push/merge/submission yapılmadı.
'''
    (ROOT/'CRMT_REMEDIATION_INDEX.md').write_text(index,encoding='utf-8')
    # Paths below are canonical-project-relative. This receipt does not imply
    # source existence alone means scientific completion.
    sourcechanges=[]
    original_commit='353b5710da298c6d51fb96452294ff117a31603e'
    tracked=subprocess.run(['git','ls-tree','-r','--name-only',original_commit],cwd=WORK,capture_output=True,text=True,check=True).stdout.splitlines()
    tracked=set(tracked)
    for folder in ('src','tests','tools','config','experiments','.github','docs/remediation'):
        for p in (WORK/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:
                rel=p.relative_to(WORK).as_posix()
                if rel not in tracked: sourcechanges.append({'path':PREFIX+rel,'change':'ADDED','sha256':file_hash(p)})
    sourcechanges.append({'path':PREFIX+'pyproject.toml','change':'MODIFIED','sha256':file_hash(WORK/'pyproject.toml')})
    csvwrite(DOC/'SOURCE_CHANGESET.csv',sorted(sourcechanges,key=lambda r:r['path']))
    outputfiles=[]
    for area in (DOC,REPORT,ROOT/'07_REPRODUCIBILITY/06_REMEDIATION_20261027',ROOT/'06_MANUSCRIPT_AND_PUBLICATION/03_NEXT_REVISION/v13',WORK/'reproducibility'):
        for p in area.rglob('*'):
            if not p.is_file() or p.name=='DELIVERABLE_FILE_INDEX.csv' or '__pycache__' in p.parts:continue
            if p.is_relative_to(WORK/'reproducibility') and p.name not in {'current_source_manifest.json','provenance_validation.json','requirements-remediation-lock.txt','requirements-remediation-full-lock.txt'}:continue
            outputfiles.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':file_hash(p)})
    for p in (ROOT/'CRMT_REMEDIATION_INDEX.md',):outputfiles.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':file_hash(p)})
    csvwrite(DOC/'DELIVERABLE_FILE_INDEX.csv',sorted(outputfiles,key=lambda r:r['path']))
    print(json.dumps({'task_rows':len(matrix),'task_status_counts':dict(counts),'source_changes':len(sourcechanges),'indexed_files':len(outputfiles),'decisions':state},ensure_ascii=False))

if __name__=='__main__':main()