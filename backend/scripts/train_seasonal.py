"""Run from backend: python scripts/train_seasonal.py [--chemical 1855] [--save-neon]."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models.seasonal import fit
from app.spatial_tools import _db


def train(chemical=None, save_neon=False, end_year=None):
    with _db() as conn:
        conn.execute("SET statement_timeout TO '180s'")
        columns={r[0] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='pur_monthly'").fetchall()}
        if not {'year','month','lbs'}<=columns: raise ValueError('pur_monthly lacks required columns.')
        if 'county_cd' in columns: county='county_cd::text'
        elif 'comtrs' in columns: county='LEFT(comtrs,2)'
        else: raise ValueError('No county code or COMTRS section code found.')
        clauses=[]; args=[]
        if chemical is not None:
            if 'chem_code' not in columns: raise ValueError('No chemical code column.')
            clauses.append('chem_code=%s'); args.append(chemical)
        if end_year is not None: clauses.append('year<=%s'); args.append(end_year)
        where='WHERE '+' AND '.join(clauses) if clauses else ''
        rows = conn.execute(f'''SELECT year, month, {county}, SUM(lbs)::double precision,
            COUNT(*) FROM public.pur_monthly {where} GROUP BY year, month, {county}
            ORDER BY year, 3, month''',tuple(args)).fetchall()
        model = fit([dict(year=r[0], month=r[1], county_cd=r[2], lbs=r[3]) for r in rows], chemical)
        model['requested_end_year']=end_year
        model['county_mapping']='county_cd' if 'county_cd' in columns else 'first two characters of CDPR COMTRS'
        model['source_rows'] = sum(r[4] for r in rows)
        if save_neon:
            conn.execute('CREATE TABLE IF NOT EXISTS askgaia_models (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            key = 'seasonal:' + (str(chemical) if chemical is not None else 'all')
            # Preserve every fitted version, plus a pointer for inference.
            for model_id in (key + ':' + model['version'], key):
                conn.execute('INSERT INTO askgaia_models (id,payload) VALUES (%s,%s) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload', (model_id, json.dumps(model)))
    out = Path(__file__).resolve().parents[1] / 'data' / 'models'
    out.mkdir(parents=True, exist_ok=True)
    path = out / (model['model_type'] + '-' + model['version'] + '.json')
    path.write_text(json.dumps(model, indent=2))
    print(json.dumps({'artifact': str(path), 'version': model['version'], 'source_rows': model['source_rows'],
                      'validation': model['validation'], 'saved_to_neon': save_neon}, indent=2))
    return model


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--chemical', type=int); parser.add_argument('--save-neon', action='store_true'); parser.add_argument('--end-year',type=int)
    args = parser.parse_args()
    try: train(args.chemical, args.save_neon,args.end_year)
    except Exception as exc:
        print('Training failed (' + type(exc).__name__ + '). Check database access, pur_monthly schema and complete reporting years.', file=sys.stderr)
        raise SystemExit(1)
