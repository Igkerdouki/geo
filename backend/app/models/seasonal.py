"""Learn seasonal county-level mass patterns from Neon PUR aggregates.

Missing monthly cells remain missing, never imputed as zero. The prediction is
conditional on observed reporting coverage, not the probability of spraying.
"""
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone

MODEL_TYPE = 'seasonal-shrinkage-v1'


def fit(rows, chemical=None):
    clean = []
    for r in rows:
        y, m, c, lbs = int(r['year']), int(r['month']), str(r['county_cd']).zfill(2), float(r['lbs'])
        if c not in {str(i).zfill(2) for i in range(1,59)} or not 1 <= m <= 12 or not 1900 <= y <= 2100 or not math.isfinite(lbs) or lbs < 0:
            raise ValueError('Invalid training aggregate; repair invalid rows before fitting.')
        clean.append({'year': y, 'month': m, 'county_cd': c, 'lbs': lbs})
    clean.sort(key=lambda r: (r['year'], r['county_cd'], r['month']))
    if len({(r['year'],r['county_cd'],r['month']) for r in clean}) != len(clean):
        raise ValueError('Expected one aggregate per county/year/month.')
    years = sorted({r['year'] for r in clean})
    if len(years) < 3: raise ValueError('At least three distinct years are required for temporal validation.')
    heldout_year = years[-1]
    training = [r for r in clean if r['year'] < heldout_year]
    heldout = [r for r in clean if r['year'] == heldout_year]

    def learn(data):
        group, month = defaultdict(list), defaultdict(list)
        for r in data:
            group[r['county_cd']].append(r['lbs']); month[(r['county_cd'],r['month'])].append(r['lbs'])
        return {c: {'baseline': sum(v)/len(v), 'months': {
            str(m): {'estimate_lbs': (sum(month[c,m])+3*sum(v)/len(v))/(len(month[c,m])+3),
                     'observed_years': len(month[c,m])} for m in range(1,13)}} for c,v in group.items()}

    fold = learn(training); errors, baseline_errors = [], []
    for r in heldout:
        if r['county_cd'] not in fold: continue
        g = fold[r['county_cd']]
        if not g['months'][str(r['month'])]['observed_years']: continue
        errors.append(abs(g['months'][str(r['month'])]['estimate_lbs'] - r['lbs']))
        baseline_errors.append(abs(g['baseline'] - r['lbs']))
    if not errors: raise ValueError('No held-out counties overlap the training data.')
    mae, baseline = sum(errors)/len(errors), sum(baseline_errors)/len(baseline_errors)
    digest = hashlib.sha256(json.dumps(clean, sort_keys=True).encode()).hexdigest()
    return {'model_type': MODEL_TYPE, 'version': digest[:16], 'data_sha256': digest,
            'trained_at': datetime.now(timezone.utc).isoformat(), 'chemical': chemical,
            'years': years, 'aggregate_rows': len(clean), 'parameters': learn(clean),
            'reporting_coverage': {str(y): sum(r['year'] == y for r in clean) for y in years},
            'coverage_warning': 'Observed county-month cells only. Reporting completeness is not verified; a partial latest year can bias validation.',
            'validation': {'split': 'latest year held out, no random split', 'heldout_year': heldout_year,
                'training_years': [y for y in years if y < heldout_year], 'test_rows': len(errors),
                'mae_lbs': mae, 'baseline_mae_lbs': baseline, 'beats_baseline': mae < baseline},
            'scope': 'California county-month reported active-ingredient pounds; missing months excluded. Not field-specific, current spraying, emission rate or exposure.'}


def predict(model, county_cd, month):
    if not 1 <= month <= 12: raise ValueError('Month must be 1–12.')
    group = model['parameters'].get(str(county_cd).zfill(2))
    if not group: raise ValueError('No trained county data; prediction withheld.')
    cell = group['months'][str(month)]
    if not cell['observed_years']: raise ValueError('No observations for this county/month; prediction withheld.')
    return {'label': 'modelled', 'county_cd': str(county_cd).zfill(2), 'month': month,
            'chemical': model['chemical'], 'expected_reported_lbs': round(cell['estimate_lbs'], 2),
            'observed_years': cell['observed_years'], 'model_version': model['version'],
            'trained_at': model['trained_at'], 'training_years': model['years'],
            'validation': model['validation'], 'scope': model['scope']}


def load_model(chemical=None):
    from app.spatial_tools import _db
    key = 'seasonal:' + (str(chemical) if chemical is not None else 'all')
    with _db() as conn:
        if conn.execute("SELECT to_regclass('public.askgaia_models')").fetchone()[0] is None:
            raise ValueError('Historical model is not trained. Run scripts/train_seasonal.py.')
        row = conn.execute('SELECT payload FROM askgaia_models WHERE id=%s', (key,)).fetchone()
    if not row: raise ValueError('Historical model is not trained. Run scripts/train_seasonal.py.')
    return json.loads(row[0])


def seasonal_prior(county_cd: str, month: int, chemical: int | None = None) -> dict:
    """Read the trained county-month historical-use model and its held-out metrics. Not a spray forecast."""
    return predict(load_model(chemical), county_cd, month)
