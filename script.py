import base64
import hashlib
import json
import lzma
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request

subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--quiet', 'pandas', 'pyreadstat'])
import pandas as pd
import pyreadstat

root = Path('afro_raw_work')
src = root / 'official'
out = root / 'repo_payload'
src.mkdir(parents=True, exist_ok=True)
out.mkdir(parents=True, exist_ok=True)

sources = {
    'KEN_R10_2024_official.sav': 'https://www.afrobarometer.org/wp-content/uploads/2025/06/KEN_R10.Data_28June24.wtd_.final_.release_updated.13Feb25.sav',
    'MDG_R10_2024_official.csv': 'https://www.afrobarometer.org/wp-content/uploads/2025/11/MAD_R10.Data_02Dec24.wtd_.final_.release_updated.13Feb25.csv',
    'NGA_R10_2024_official.csv': 'https://www.afrobarometer.org/wp-content/uploads/2025/11/NIG_R10.Data_18Nov24.wtd_.final_.release_updated.13Feb25.csv',
    'TZA_R10_2024_official.sav': 'https://www.afrobarometer.org/wp-content/uploads/2025/11/TAN_R10.Data_20Sep24.wtd_.final_.release_updated.13Feb25.sav',
    'ZMB_R10_2024_official.csv': 'https://www.afrobarometer.org/wp-content/uploads/2025/11/ZAM_R10.Data_27Sep24.wtd_.final_.release_updated.13Feb25.csv',
    'ZAF_R9_2022_official.sav': 'https://www.afrobarometer.org/wp-content/uploads/2024/02/SAF_R9.data_.final_.wtd_release.30May23.sav',
}
expected_sha256 = {
    'KEN_R10_2024_official.sav': '6b53c17ddcd5cd5613446d2da2d8a034476bfd2c93baaf87d3e5a52d940a8ccd',
    'MDG_R10_2024_official.csv': 'e165d5d782beb9d531b1161581a6cd52698052a8b8d8cf5909d83b8e78a741da',
    'NGA_R10_2024_official.csv': 'abd2cbccb6f9739576e0c76c276672ae0ca49233b537b0c2e77a2c8d2e4dddb7',
    'TZA_R10_2024_official.sav': '009e0807e5bfda90001277b566ea2e3e5c0ead5489fa10ecc1f8667daf17a60e',
    'ZMB_R10_2024_official.csv': '6d4247ed626030f1663d38852a270ef5fc983c7b92397f738db7831690a2ff53',
    'ZAF_R9_2022_official.sav': 'd99670bc7c30be675ac789ee41f0034c379d333b16951ac78e2d9571a582f75b',
}

def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

manifest = {
    'generated_utc': pd.Timestamp.utcnow().isoformat(),
    'source': 'Afrobarometer official country data downloads',
    'note': 'Five paper countries use Round 10 (2024). South Africa uses the latest publicly released respondent-level file, Round 9 (2022); Round 10 (2025) summary results exist but respondent microdata were not publicly listed as of 2026-09-14.',
    'files': []
}

for name, url in sources.items():
    p = src / name
    print('Downloading', url)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=180) as r, open(p, 'wb') as f:
        shutil.copyfileobj(r, f)
    got = sha256(p)
    if got != expected_sha256[name]:
        raise RuntimeError(f'SHA mismatch for {name}: {got} != {expected_sha256[name]}')

    rec = {'official_filename': name, 'source_url': url, 'official_sha256': got, 'official_bytes': p.stat().st_size}
    if p.suffix.lower() == '.sav':
        df, meta = pyreadstat.read_sav(str(p), apply_value_formats=False)
        csv_name = name.replace('_official.sav', '_raw_codes.csv')
        csv_path = out / csv_name
        df.to_csv(csv_path, index=False)
        metadata = {
            'source_file': name,
            'number_rows': len(df),
            'number_columns': len(df.columns),
            'column_names': list(df.columns),
            'column_labels': dict(zip(meta.column_names, meta.column_labels)),
            'variable_value_labels': meta.variable_value_labels,
            'missing_ranges': meta.missing_ranges,
        }
        meta_path = out / name.replace('_official.sav', '_sav_metadata.json')
        meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
        rec.update({'repo_data_file': csv_name, 'repo_metadata_file': meta_path.name, 'rows': len(df), 'columns': len(df.columns), 'repo_data_sha256': sha256(csv_path)})
    else:
        dest = out / name
        shutil.copyfile(p, dest)
        df = pd.read_csv(dest, low_memory=False)
        rec.update({'repo_data_file': dest.name, 'rows': len(df), 'columns': len(df.columns), 'repo_data_sha256': sha256(dest)})
    manifest['files'].append(rec)

(out / 'MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(out / 'README.md').write_text('''# Afrobarometer respondent-level source data\n\nThis archive contains the complete respondent-level country files used for the Digital Empires Afrobarometer benchmark. Official CSV releases are preserved byte-for-byte. Official SAV releases are converted to CSV with raw numeric codes (`apply_value_formats=False`) and accompanied by JSON preserving column labels and value labels. Exact official source URLs and SHA-256 hashes are in `MANIFEST.json`.\n\nSouth Africa uses Round 9 (2022), the latest respondent-level public release located on 2026-09-14. Round 10 fieldwork was conducted in 2025 and its aggregate Summary of Results is used in the paper benchmark, but respondent-level Round 10 data were not publicly listed at that time.\n''', encoding='utf-8')

# Create a single solid tar.xz payload of repo-ready respondent data + metadata.
tar_path = Path('afrobarometer_raw_respondent_data.tar')
with tarfile.open(tar_path, 'w') as tf:
    for p in sorted(out.iterdir()):
        tf.add(p, arcname=p.name)

xz_path = Path(str(tar_path) + '.xz')
with open(tar_path, 'rb') as fi, lzma.open(xz_path, 'wb', preset=9 | lzma.PRESET_EXTREME) as fo:
    shutil.copyfileobj(fi, fo)

payload = base64.b64encode(xz_path.read_bytes()).decode('ascii')
Path('data').mkdir(exist_ok=True)
Path('data/wbuserdata.csv').write_text(payload + '\n', encoding='ascii')
print('payload chars', len(payload), 'archive bytes', xz_path.stat().st_size)
print(json.dumps(manifest, indent=2))
