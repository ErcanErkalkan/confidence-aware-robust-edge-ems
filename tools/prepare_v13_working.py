"""Prepare a separate internal v13 source draft from the original v12 ZIP.

No frozen manuscript or numerical historical table value is overwritten.
"""
from __future__ import annotations
from pathlib import Path,PurePosixPath
import argparse
import difflib
import json
import re
import sys
import zipfile
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
WORK=Path(__file__).resolve().parents[1];sys.path.insert(0,str(WORK/'src'))
from crmt_edge_ems.contracts import file_hash,canonical,ContractError

ABSTRACT=r'''This internal working revision audits Confidence-Aware Risk-Calibrated Multiobjective Tuning (CRMT), an offline framework combining a mean-plus-tail empirical risk, paired-bootstrap Pareto decisions and adaptive allocation while keeping the online controller structure fixed. Historical experiments compared five methods across 30 optimizer seeds with 12,600 TRAIN controller--block evaluations per method and seed. The reported approximation-set indicators were evaluated on VALIDATION for TRAIN-generated fronts; they are not TRAIN-only quality measurements. Internal and previously exposed external OPSD replay results support objective-specific differences, without uniform operational superiority. Historical one-factor ablations do not establish independent operational benefits for confidence or adaptive allocation; full CRMT and NO\_ADAPTIVE have identical reported held-out objective vectors in all 30 seeds, with selected-controller identity agreement reported in the prior audit. Equal TRAIN budgets do not imply equal validation work or total computational cost. Subsequent synthetic diagnostics do not establish nominal 95\% archive-wide coverage, and family-bound violations, false dominance and false Pareto removals must be distinguished. The recovered historical source package contains 160 verifiable artifacts but retains one unresolved execution-SHA exception. R19 remains a draft shortlist-fidelity protocol; no new confirmatory AUDIT or independent operational TEST has been completed. The revised evidence supports a reproducible research implementation and a narrower, explicitly conditional scientific interpretation. Author review and final verification of the publication claims remain pending.'''

NEW_LIMITS=r'''
\section{Current evidence status and prospective boundaries}
\label{sec:current_boundaries}
This section describes the current audit status; it does not add operational experimental results to the historical tables. Historical TRAIN, VALIDATION, internal TEST and OPSD outcomes are exposed evidence. Repartitioning them, or assigning new optimizer seeds, cannot create a new independent operational TEST.

\paragraph{Confidence calibration.} The original F1 procedure adjusts four objectives within each pair. This is not a proof of simultaneous validity across all candidate pairs, finite-sample bootstrap accuracy, serial dependence or adaptive sample selection. Historical R21 reports substantial family-bound undercoverage, including 67.5\% and 77.5\% in two IID legacy scenarios, and approximately 10--11.25\% in shared max-T IID scenarios. These are family-bound failures, not automatically false-removal rates. R22 changes the estimand to daily averages. R23 is a separately versioned conditional pooled-risk prototype with bounded-support, stationarity and known finite-dependence assumptions that have not been verified for the operational source. No archive-wide nominal 95\% guarantee is asserted here.

\paragraph{Membership and capacity.} In 18 of 20 historical factorial cells F0 is a subset of F1; two seed1001 cells contain an F0-only candidate. The universal subset statement is invalid. R19 fixes C1/A1, B=K=10, a common 256-candidate pool and identical 12,600-event DISCOVERY ledgers. B10 is output shortlist capacity, not a native archive RAM limit. Ranking uses only DISCOVERY-derived all-candidate min--max normalization, then $L_\infty$, $L_1$ and lexical ID; selection must remain within each natural archive and must block if fewer than ten candidates exist. Backfill is disabled. AUDIT outcomes cannot influence this selection.

\paragraph{Prospective inference and sample size.} The proposed outcome is $\Delta_{\mathrm{Miss}}=\mathrm{MissRate}(F1)-\mathrm{MissRate}(F0)$, with negative values favoring F1 against a finite empirical AUDIT Pareto reference. Optimizer seed is the paired primary analysis unit, conditional on the fixed dataset. A sign-flip procedure needs independent symmetric differences or a justified paired randomization; it is not an exact test of arbitrary zero-mean differences. Thirty seeds (draft IDs 2001--2030), the minimum important difference, paired variability, multiplicity and failed-run policies need prospective approval. The draft remains unlocked. \textbf{Evidence status: new R19 confirmatory results NOT AVAILABLE; new independent operational TEST NOT AVAILABLE.}

\paragraph{Source provenance.} The current local audit rehashes 160/160 historical source artifacts and verifies equality of the scientific DISCOVERY records in 20/20 F0/F1 pairs. Strict preflight passes 19 pairs and rejects one due to \texttt{seed1001/C1\_F1\_A1}: \texttt{UNRECORDED\_LOCAL\_SHA}. A later Git HEAD or a new hash cannot recover the original execution identity. A 63-entry older frozen-source manifest contains six exact byte matches, 34 line-ending-normalized matches and 23 content differences; the discrepancy is documented rather than rewritten away.

\paragraph{Physical and external-data limits.} Grid-cap windows are declared scenarios; measured downstream grid power is not an uncontrolled baseline. Inverter subsystems remain physically separate. The LFP objective is a model-based proxy, not measured lifetime extension. Software runtime and scenario safety-veto tests do not establish certified real-time behavior, HIL or field deployment. R26--R30 provider and public-metadata screens do not admit a new four-objective operational dataset: storage flags do not establish SOC, chemistry, command observability or contractual grid caps. Provider rights, usable raw measurements, exposure review and independent preregistration remain missing. No manuscript release is authorized by the engineering audit.

\paragraph{Total cost.} Equal TRAIN evaluation budgets, equal output shortlist capacity and measured total CPU/wall/RSS are separate comparison conditions. Larger natural archives can cause different VALIDATION workloads. Historical runtime proxies cannot recover unmeasured bootstrap or phase CPU. Process peak RSS is a lifetime high-water mark, not phase-isolated memory, and no energy-consumption measurement is claimed.
'''

def prepare(root):
    original=root/'06_MANUSCRIPT_AND_PUBLICATION/01_MANUSCRIPT_SNAPSHOT (1)/CRMT_MANUSCRIPT_SOURCE_v12.zip'
    target=root/'06_MANUSCRIPT_AND_PUBLICATION/03_NEXT_REVISION/v13'
    if target.exists() and any(target.iterdir()): raise ContractError('v13 directory not empty; preserve existing working revision')
    target.mkdir(parents=True,exist_ok=True)
    originals={}
    with zipfile.ZipFile(original) as z:
        for info in z.infolist():
            if info.is_dir():continue
            rel=PurePosixPath(info.filename).parts[1:]
            if not rel or '..' in rel:raise ContractError('unsafe manuscript ZIP path')
            # Keep original compiled v12 PDF only in the frozen source ZIP.
            if rel[-1].endswith(('.pdf','.spl')) and len(rel)==1:continue
            destination=target.joinpath(*rel);destination.parent.mkdir(parents=True,exist_ok=True)
            data=z.read(info);destination.write_bytes(data)
            if destination.suffix=='.tex': originals[destination.relative_to(target).as_posix()]=data.decode('utf-8-sig')
    changes=[]
    for rel,before in originals.items():
        text=before
        if rel=='MANUSCRIPT_ASOC_FULL_v12.tex':
            text=text.replace(r'\input{SECTIONS_1_2_ASOC_v12.tex}',r'\input{SECTIONS_1_2_ASOC_v13.tex}').replace(r'\input{SECTIONS_3_12_ASOC_v12.tex}',r'\input{SECTIONS_3_12_ASOC_v13.tex}')
            a=text.index(r'\begin{abstract}')+len(r'\begin{abstract}');b=text.index(r'\end{abstract}')
            text=text[:a]+'\n'+ABSTRACT+'\n'+text[b:]
            text=text.replace('under Distribution Shift}',r'under Distribution Shift\\[0.5em]\large Internal v13 working draft\\\normalsize 27 October 2026 --- author review pending}')
            marker=r'\section*{Declaration of generative AI and AI-assisted technologies in the manuscript preparation process}'
            a=text.index(marker)+len(marker);b=text.index(r'\bibliographystyle',a)
            text=text[:a]+'\nThis internal revision used AI assistance for source-code remediation, regression tests, draft editing and engineering plots. Original historical data and v12 remain preserved. New synthetic engineering experiments are explicitly labeled and are not operational results. Author verification of final wording, references, disclosures and publication claims remains pending; no signature or author approval is implied.\n\n'+text[b:]
        if rel.startswith('SECTIONS_'):
            replacements={
                'training search quality':'validation-evaluated quality of TRAIN-generated fronts',
                'training approximation set':'validation-evaluated approximation set generated during TRAIN',
                'training approximation':'validation-evaluated TRAIN-generated approximation',
                'TRAIN approximation-set quality':'validation-evaluated approximation-set quality of TRAIN-generated fronts',
                'TRAIN approximation-quality':'validation-evaluated approximation-quality of TRAIN-generated fronts',
                'TRAIN approximation quality':'validation-evaluated quality of TRAIN-generated fronts',
                'Equal-budget TRAIN optimizer quality':'Validation-evaluated approximation-set quality of TRAIN-generated fronts',
                'TRAIN search quality':'TRAIN-generated front quality evaluated on VALIDATION',
                'family-wise one-sided confidence bounds':'pairwise nominal one-sided bootstrap bounds',
                'family-wise $\\alpha=0.05$, with Bonferroni control across the four objectives':'nominal pairwise $\\alpha=0.05$ and an objective-wise Bonferroni adjustment; archive-wide nominal coverage is not established',
                'equal-budget advantage in approximation-set quality':'equal-TRAIN-evaluation advantage in validation-evaluated approximation-set quality',
                'under exact budget parity':'under equal TRAIN simulator-evaluation budgets, with total-cost parity unestablished',
                'Equal-budget TRAIN approximation quality':'Validation-evaluated quality of TRAIN-generated fronts under equal TRAIN budgets',
                'Statistical claims are restricted to the frozen TRAIN protocol.':'Indicators are measured on historical VALIDATION; equal TRAIN evaluations do not imply equal total computation.',
                'under the fixed TRAIN budget':'under the fixed TRAIN evaluation budget, with quality measured on VALIDATION',
            }
            for a,b in replacements.items():text=text.replace(a,b)
            text=text.replace('NO\\_ADAPTIVE was numerically identical to full CRMT for all four held-out objective summaries under the predeclared protocol.',
                'NO\\_ADAPTIVE was numerically identical to full CRMT in all four reported held-out objectives across 30/30 optimizer seeds; the previous audit also reports 30/30 selected-controller identity agreement. This revision directly checks the outcome-vector equality; it does not reconstruct every selected-parameter artifact.')
            # Old vector schematics carry obsolete TRAIN-only quality labels.
            # Replace only in v13 with explicit text schematics; preserve assets.
            text=text.replace(r'\makebox[\textwidth][c]{\includegraphics[width=0.88\paperwidth]{figures/F1_CRMT_framework_v12.pdf}}',
                r'\fbox{\parbox{0.9\linewidth}{Offline: TRAIN candidate generation and allocation; risk and pairwise confidence archive.\\VALIDATION: approximation-set evaluation and deterministic representative selection.\\Historical internal TEST and OPSD: exposed post-selection replay.\\Prospective R19 and independent TEST: blocked pending external evidence.}}')
            text=text.replace(r'\makebox[\textwidth][c]{\includegraphics[width=0.92\paperwidth]{figures/F2_cross_stage_evidence_v12.pdf}}',
                r'\fbox{\parbox{0.9\linewidth}{(a) TRAIN generates fronts; quality indicators are evaluated on VALIDATION.\\(b) Shared VALIDATION normalization selects a controller.\\(c) Historical internal and OPSD outcomes are objective-specific.\\Equal TRAIN evaluations do not establish equal validation work, CPU or RAM.}}')
            text=text.replace('The vector schematic follows the executed protocol and contains no synthetic performance coordinates.',
                'This v13 text schematic distinguishes historical evidence layers and contains no new performance result.')
            text=text.replace('The figure is a programmatic vector summary of already reported frozen evidence and contains no synthetic performance coordinates or additional statistical analysis.',
                'The v13 text schematic makes the measurement partition explicit; no new operational result is introduced.')
            text=text.replace('The TRAIN panel reports the observed CRMT medians for hypervolume, IGD+, and additive epsilon together with the supported protocol-specific inference;',
                'TRAIN-generated fronts are scored on VALIDATION for hypervolume, IGD+, and additive epsilon;')
            text=text.replace('Panel (a) restates the frozen validation-evaluated approximation-quality of TRAIN-generated fronts result,',
                'Panel (a) states that quality is measured on VALIDATION for TRAIN-generated fronts,')
            if rel=='SECTIONS_3_12_ASOC_v12.tex':
                text=text.replace(r'\section{Reproducibility}',NEW_LIMITS+'\n'+r'\section{Reproducibility}')
                text=text.replace('This structure permits deterministic verification that the reported tables and figures originate from the locked confirmatory chain rather than from post-hoc reruns.',
                    'These records support artifact verification within their recorded scope; the unresolved execution-SHA exception prevents an unconditional claim of complete execution provenance.')
                text=text.replace('Figure~\\ref{fig:crmt_architecture} is a programmatically drawn explanatory schematic of the executed CRMT workflow. Figure~\\ref{fig:cross_stage_evidence} is a programmatic vector synthesis of numerical values and significance statements already reported in the frozen result tables and data-derived figures.',
                    'The v13 text schematics state the evidence partitions and claim limits. The three optimizer-quality plots are regenerated from the unchanged archived seed-level CSV with corrected VALIDATION labels.')
        if rel=='tables/tab_optimizer_quality.tex':
            text=re.sub(r'\\caption\{[^\n]+',r'\\caption{Historical validation-evaluated approximation-set quality of TRAIN-generated fronts. TRAIN simulator budgets are equal; total VALIDATION and computational cost is not established as equal.}',text)
        newrel=rel.replace('_v12.tex','_v13.tex')
        destination=target/newrel;destination.write_text(text,encoding='utf-8')
        if newrel!=rel:(target/rel).unlink() # only the newly extracted duplicate
        if text!=before:
            diff='\n'.join(difflib.unified_diff(before.splitlines(),text.splitlines(),fromfile='v12/'+rel,tofile='v13/'+newrel,lineterm=''))
            patchpath=target/'revision_diffs'/Path(rel+'.diff');patchpath.parent.mkdir(parents=True,exist_ok=True);patchpath.write_text(diff+'\n',encoding='utf-8')
            changes.append({'source':rel,'working':newrel,'changed_lines':len(diff.splitlines())})
    # Regenerate only mislabeled optimizer-quality plots, using original values.
    csvpath=root/'05_RESULTS_AND_EVIDENCE/01_INITIAL_30_SEED_EVIDENCE (2)/optimizer_quality_seed.csv'
    df=pd.read_csv(csvpath);methods=['SOBOL','NSGAII','MOPSO','MODE','CRMT']
    for col,name,label in [('hypervolume','F1a_optimizer_hypervolume.png','Hypervolume (higher is better)'),('igd_plus','F1b_optimizer_igd_plus.png','IGD+ (lower is better)'),('additive_epsilon','F1c_optimizer_additive_epsilon.png','Additive epsilon (lower is better)')]:
        fig,ax=plt.subplots(figsize=(7,3.8),layout='constrained')
        ax.boxplot([df.loc[df.method==m,col].to_numpy() for m in methods],tick_labels=methods)
        ax.set(ylabel=label,title='Historical VALIDATION-evaluated TRAIN-generated fronts')
        ax.grid(axis='y',alpha=.2);fig.savefig(target/'figures'/name,dpi=180);plt.close(fig)
    receipt={'status':'INTERNAL_WORKING_DRAFT_AUTHOR_REVIEW_PENDING','v12_source_sha256':file_hash(original),
        'historical_plot_data_sha256':file_hash(csvpath),'changes':changes,
        'claim_status':'Historical numeric tables retained; no new operational results; external TEST and preregistration NO_GO',
        'bibliography':'Original citation keys and bibliography preserved, not independently reverified in this remediation',
        'authorizations':'No author approval, submission or publication implied'}
    (target/'V13_REVISION_RECEIPT.json').write_bytes(canonical(receipt))
    (target/'HIGHLIGHTS_v13.md').write_text('''# Internal v13 highlights (author review pending)

- Historical fronts are generated on TRAIN and quality is evaluated on VALIDATION.
- Equal TRAIN evaluations do not establish equal total computational cost.
- Confidence and adaptive operational contributions remain unsupported independently.
- Archive-wide 95% coverage and new independent TEST claims are not supported.
- R19 is a draft; external data, power review and independent preregistration remain blocked.
''',encoding='utf-8')
    print(json.dumps({'target':str(target),'changed_source_files':len(changes),'v12_preserved':True}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--canonical-root',type=Path,default=WORK.parents[1]);a=p.parse_args();prepare(a.canonical_root)
