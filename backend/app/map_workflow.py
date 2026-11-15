"""Deterministic map stage shared by satellite and town renderers."""
from hashlib import sha256
import json
from pydantic import BaseModel, Field
from typing import Literal
from app.coverage import california_location

class MapScenario(BaseModel):
    source_lat: float = Field(ge=32, le=42.1, allow_inf_nan=False)
    source_lon: float = Field(ge=-125, le=-114, allow_inf_nan=False)
    speed: float = Field(ge=0, le=60, allow_inf_nan=False)
    direction: float = Field(ge=0, lt=360, allow_inf_nan=False)
    stability: Literal['A','B','C','D','E','F'] = 'D'

def map_simulation(body: MapScenario):
    from app.api.spatial import PlumeSamples, plume_samples
    california_location(body.source_lat, body.source_lon)
    scenario = body.model_dump()
    result = {'id':sha256(json.dumps(scenario,sort_keys=True).encode()).hexdigest()[:20],
              'scenario':scenario, 'source':{'lat':body.source_lat,'lon':body.source_lon},
              'label':'modelled', 'stage':'deterministic simulation',
              'limitations':['Hypothetical source; historical use does not confirm current spraying.',
                             'Relative dispersion index, not measured exposure.']}
    if body.speed < .5:
        return {**result,'status':'calm','grid':None}
    size, extent = 129, 7000
    points = [{'east':(i/(size-1)-.5)*extent,'north':(j/(size-1)-.5)*extent}
              for j in range(size) for i in range(size)]
    samples = plume_samples(PlumeSamples(speed=body.speed,direction=body.direction,stability=body.stability,points=points))
    return {**result,'status':'complete','engine':samples['engine'],
            'normalization':samples['display_normalization'],
            'grid':{'size':size,'extent_m':extent,'values':samples['display_values']}}
