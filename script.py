import subprocess, sys
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'requests', 'pandas', 'pyreadstat'])
import requests, pandas as pd, pyreadstat, re, math
from io import StringIO

FILES = [
 ('KEN','R10','https://www.afrobarometer.org/wp-content/uploads/2025/06/KEN_R10.Data_28June24.wtd_.final_.release_updated.13Feb25.sav','sav'),
 ('MDG','R10','https://www.afrobarometer.org/wp-content/uploads/2025/11/MAD_R10.Data_02Dec24.wtd_.final_.release_updated.13Feb25.csv','csv'),
 ('NGA','R10','https://www.afrobarometer.org/wp-content/uploads/2025/11/NIG_R10.Data_18Nov24.wtd_.final_.release_updated.13Feb25.csv','csv'),
 ('TZA','R10','https://www.afrobarometer.org/wp-content/uploads/2025/11/TAN_R10.Data_20Sep24.wtd_.final_.release_updated.13Feb25.sav','sav'),
 ('ZMB','R10','https://www.afrobarometer.org/wp-content/uploads/2025/11/ZAM_R10.Data_27Sep24.wtd_.final_.release_updated.13Feb25.csv','csv'),
 ('ZAF','R9','https://www.afrobarometer.org/wp-content/uploads/2024/02/SAF_R9.data_.final_.wtd_release.30May23.sav','sav'),
]

def norm(x):
    s = str(x).strip().lower().replace('’',"'").replace('‘',"'")
    s = re.sub(r'\s+',' ',s)
    return s

POS = {
 'somewhat','a lot',
 'partiellement confiance','beaucoup confiance',
 'somewhat trust','a lot of trust',
}
NEG = {'not at all','just a little','pas du tout confiance','juste un peu confiance'}

def read_one(iso, rnd, url, fmt):
    r = requests.get(url, timeout=120); r.raise_for_status()
    fn = f'/tmp/{iso}_{rnd}.{fmt}'; open(fn,'wb').write(r.content)
    if fmt == 'sav':
        raw, meta = pyreadstat.read_sav(fn, apply_value_formats=False)
        lab, _ = pyreadstat.read_sav(fn, apply_value_formats=True)
        labels = dict(zip(meta.column_names, meta.column_labels))
        return raw, lab, labels
    df = pd.read_csv(fn, low_memory=False)
    return df.copy(), df.copy(), {c:c for c in df.columns}

def ci_col(df, wanted):
    m={str(c).lower():c for c in df.columns}
    return m.get(wanted.lower())

def find_zaf_vars(df, labels):
    out=[]
    for c in df.columns:
        t=(str(c)+' '+str(labels.get(c,''))).lower()
        if 'trust' in t and any(k in t for k in ['president','parliament','ruling party','anc']):
            out.append((c,labels.get(c,'')))
    return out

def top2_indicator(series):
    vals=series.map(norm)
    return vals.map(lambda x: 1.0 if x in POS else (0.0 if x in NEG else float('nan')))

def stats(ind, w):
    valid=ind.notna() & w.notna() & (w>0)
    unw=100*ind[valid].mean()
    wei=100*(ind[valid]*w[valid]).sum()/w[valid].sum()
    return int(valid.sum()), unw, wei

for iso,rnd,url,fmt in FILES:
    raw, lab, labels = read_one(iso,rnd,url,fmt)
    wcol=ci_col(raw,'withinwt_hh')
    print('\nCOUNTRY',iso,rnd,'rows',len(raw),'weight',wcol)
    if iso=='ZAF':
        cand=find_zaf_vars(raw,labels)
        print('ZAF TRUST CANDIDATES',cand)
        # Pick by label meaning rather than assumed question number.
        def pick(term):
            hits=[]
            for c,l in labels.items():
                t=(str(c)+' '+str(l)).lower()
                if 'trust' in t and term in t: hits.append(c)
            return hits[0] if hits else None
        cols={'president':pick('president'),'parliament':pick('parliament'),'ruling_party':pick('ruling party')}
        # Some R9 labels call the governing party by its proper name; fallback print all trust vars.
    else:
        cols={'president':ci_col(raw,'Q37A'),'parliament':ci_col(raw,'Q37B'),'ruling_party':ci_col(raw,'Q37E')}
    print('ITEM_COLS',cols)
    if not wcol:
        print('ERROR no withinwt_hh'); continue
    w=pd.to_numeric(raw[wcol], errors='coerce')
    for inst,c in cols.items():
        if not c:
            print('MISSING',inst); continue
        # For SAV use labelled values; for CSV the values are already labels.
        s=lab[c]
        print('VALUES',inst, s.value_counts(dropna=False).head(10).to_dict())
        ind=top2_indicator(s)
        n,unw,wei=stats(ind,w)
        print('RESULT',iso,rnd,inst,'n_valid',n,'unweighted',round(unw,4),'weighted_hh',round(wei,4),'weight_shift',round(wei-unw,4))
