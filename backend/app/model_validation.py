"""Compare independently measured receptor samples to matching modeled snapshots."""
import math
from pydantic import Field, AwareDatetime
from app.spray_transport import InputModel, SprayScenario, simulate_spray


class Measurement(InputModel):
    receptor_id: str = Field(min_length=1,max_length=80)
    ingredient: str = Field(min_length=1,max_length=120)
    at: AwareDatetime
    concentration_ug_m3: float = Field(ge=0,le=1e15)
    source: str = Field(min_length=1,max_length=1000)
    sample_kind: str = Field(pattern='^instantaneous$')


class ValidationRequest(InputModel):
    scenario: SprayScenario
    measurements: list[Measurement] = Field(min_length=1,max_length=1000)
    dataset_id: str = Field(min_length=1,max_length=200)
    held_out: bool


def validate_measurements(body):
    if body.scenario.physics is None or not body.scenario.receptors:
        raise ValueError('Validation requires physics assumptions and receptor coordinates.')
    result=simulate_spray(body.scenario)
    predicted={}
    from datetime import datetime
    for frame in result['snapshots']:
        at=datetime.fromisoformat(frame['at'])
        for receptor in frame['receptors']:
            predicted[(receptor['receptor_id'],receptor['ingredient'],at)]=receptor['concentration_ug_m3']
    keys=[(m.receptor_id,m.ingredient,m.at) for m in body.measurements]
    if len(keys)!=len(set(keys)): raise ValueError('Duplicate measurements for receptor, ingredient and time.')
    if any(k not in predicted for k in keys):
        raise ValueError('Every sample must exactly match a modeled receptor, ingredient and snapshot timestamp. Averaged samples cannot be compared to instantaneous predictions.')
    pairs=[{'receptor_id':m.receptor_id,'ingredient':m.ingredient,'at':m.at.isoformat(),
        'observed_ug_m3':m.concentration_ug_m3,'predicted_ug_m3':predicted[k],'source':m.source} for m,k in zip(body.measurements,keys)]
    errors=[p['predicted_ug_m3']-p['observed_ug_m3'] for p in pairs]
    return {'dataset_id':body.dataset_id,'held_out_declared_by_user':body.held_out,'sample_count':len(pairs),
        'mae_ug_m3':sum(abs(e) for e in errors)/len(errors),
        'rmse_ug_m3':math.sqrt(sum(e*e for e in errors)/len(errors)),
        'bias_ug_m3':sum(errors)/len(errors),'pairs':pairs,
        'status':'evaluated_supplied_samples',
        'limitations':['Measurement provenance and independence are supplied by the caller, not verified.',
            'No automatic accuracy certification or safety conclusion. No model fitting occurs on these evaluation samples.']}
