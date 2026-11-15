"""Bounded passive-tracer scenarios; not a validated pesticide fate model."""
import math
from datetime import timedelta, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator
from app.coverage import california_location


def wind_conditions(lat, lon):
    # Explicit what-if winds do not require provider or database dependencies.
    from app.simulation import wind_conditions as fetch
    return fetch(lat, lon)


class InputModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Ingredient(InputModel):
    name: str = Field(min_length=1, max_length=120)
    applied_kg: float = Field(gt=0, le=100000)
    airborne_fraction: float = Field(ge=0, le=1)
    airborne_half_life_minutes: float | None = Field(default=None, ge=0.001)
    deposition_half_life_minutes: float | None = Field(default=None, ge=0.001)
    assumption_source: str = Field(min_length=1, max_length=500)
    droplet_diameter_um: float | None = Field(default=None,ge=1,le=1000)
    residual_diameter_um: float | None = Field(default=None,ge=1,le=1000)
    density_kg_m3: float = Field(default=1000,ge=500,le=2500)
    evaporation_um2_s: float = Field(default=0,ge=0,le=10000)
    volatilization_half_life_minutes: float | None = Field(default=None,ge=0.001)
    rain_scavenging_per_mm: float = Field(default=0,ge=0,le=10)
    @model_validator(mode='after')
    def droplet_bounds(self):
        if self.residual_diameter_um is not None and (self.droplet_diameter_um is None or self.residual_diameter_um>self.droplet_diameter_um):
            raise ValueError('Residual diameter requires an initial diameter at least as large.')
        if self.evaporation_um2_s and self.residual_diameter_um is None:
            raise ValueError('Evaporation requires a residual diameter; active ingredient does not disappear with water.')
        return self


class WindStep(InputModel):
    minute: int = Field(ge=0, le=120)
    speed_ms: float = Field(ge=0, le=30)
    from_deg: float = Field(ge=0, lt=360)
    temperature_c: float | None = Field(default=None,ge=-50,le=60)
    humidity_pct: float | None = Field(default=None,ge=0,le=100)
    rain_mm_hr: float | None = Field(default=None,ge=0,le=300)


class Physics(InputModel):
    release_height_m: float = Field(ge=0.1,le=100)
    mixing_height_m: float = Field(ge=1,le=3000)
    horizontal_diffusivity_m2_s: float = Field(ge=0.01,le=1000)
    vertical_diffusivity_m2_s: float = Field(ge=0.01,le=100)
    wind_height_exponent: float = Field(ge=0,le=0.5)
    terrain_east_grade: float = Field(default=0,ge=-0.5,le=0.5)
    terrain_north_grade: float = Field(default=0,ge=-0.5,le=0.5)
    assumption_source: str = Field(min_length=1,max_length=500)


class Receptor(InputModel):
    id: str = Field(min_length=1,max_length=80)
    lat: float
    lon: float
    height_m: float = Field(default=1.5,ge=0,le=100)


class Uncertainty(InputModel):
    wind_direction_deg: float = Field(default=20,ge=0,le=90)
    wind_speed_fraction: float = Field(default=0.25,ge=0,le=0.9)
    start_minutes: int = Field(default=0,ge=0,le=120)
    removal_rate_fraction: float = Field(default=0.25,ge=0,le=0.9)


class SprayScenario(InputModel):
    source_lat: float
    source_lon: float
    start_at: AwareDatetime
    event_kind: Literal['hypothetical', 'scheduled', 'reported'] = 'hypothetical'
    event_source: str = Field(min_length=1, max_length=500)
    application_method: Literal['unspecified','ground_boom','airblast','aerial','soil_injection'] = 'unspecified'
    formulation: str = Field(default='Unspecified',min_length=1,max_length=150)
    location_uncertainty_m: float = Field(ge=0, le=10000)
    duration_minutes: int = Field(ge=1, le=120)
    horizon_minutes: int = Field(default=60, ge=1, le=120)
    snapshot_interval_minutes: int = Field(default=5, ge=1, le=5)
    ingredients: list[Ingredient] = Field(min_length=1, max_length=10)
    wind: list[WindStep] | None = Field(default=None, min_length=1, max_length=121)
    physics: Physics | None = None
    receptors: list[Receptor] = Field(default_factory=list,max_length=10)
    uncertainty: Uncertainty | None = None

    @model_validator(mode='after')
    def validate_timeline(self):
        if self.duration_minutes > self.horizon_minutes:
            raise ValueError('Horizon must include the entire spray duration.')
        if len(self.ingredients)*self.duration_minutes*self.horizon_minutes*(11 if self.uncertainty else 1)>400000:
            raise ValueError('Scenario exceeds the computation budget. Reduce ingredients, duration or horizon, or disable sensitivity.')
        if self.wind is not None:
            minutes = [w.minute for w in self.wind]
            if minutes[0] != 0 or minutes != sorted(set(minutes)):
                raise ValueError('Wind steps must start at minute 0 and strictly increase.')
        names = [i.name.strip().casefold() for i in self.ingredients]
        if not all(names) or len(set(names)) != len(names):
            raise ValueError('Ingredient names must be nonempty and unique.')
        if self.receptors and self.physics is None:
            raise ValueError('Receptor estimates require explicit physics assumptions.')
        if self.physics is None and any(i.droplet_diameter_um is not None or i.evaporation_um2_s or i.volatilization_half_life_minutes or i.rain_scavenging_per_mm for i in self.ingredients):
            raise ValueError('Droplet, evaporation, vapor and rain parameters require explicit physics assumptions.')
        if len({r.id for r in self.receptors})!=len(self.receptors):
            raise ValueError('Receptor IDs must be unique.')
        return self


def settling_speed(diameter_um, density, temperature_c):
    """Sphere terminal velocity using Schiller–Naumann drag (screening assumption)."""
    if diameter_um is None: return 0.0
    diameter=diameter_um*1e-6
    temp=temperature_c+273.15
    viscosity=1.716e-5*(temp/273.15)**1.5*(273.15+111)/(temp+111)
    air_density=1.225*288.15/temp
    speed=(density-air_density)*9.80665*diameter**2/(18*viscosity)
    for _ in range(20):
        reynolds=max(1e-9,air_density*speed*diameter/viscosity)
        drag=24/reynolds*(1+0.15*reynolds**0.687) if reynolds<1000 else 0.44
        target=math.sqrt(4*diameter*(density-air_density)*9.80665/(3*air_density*drag))
        speed=(speed+target)/2
    return speed


def puff_concentration(parcel, receptor, request, minute):
    """Gaussian puff at a receptor; kg -> ug, with reflecting flat ground."""
    physics=request.physics
    age=(minute-parcel['born']-0.5)*60
    xy=math.sqrt(4+2*physics.horizontal_diffusivity_m2_s*age)
    z=math.sqrt(1+2*physics.vertical_diffusivity_m2_s*age)
    east=(receptor.lon-request.source_lon)*111320*math.cos(math.radians(request.source_lat))
    north=(receptor.lat-request.source_lat)*111320
    ground=physics.terrain_east_grade*parcel['east']+physics.terrain_north_grade*parcel['north']
    height=max(0.1,physics.release_height_m-ground)
    lateral=math.exp(-((east-parcel['east'])**2+(north-parcel['north'])**2)/(2*xy**2))
    vertical=math.exp(-(receptor.height_m-height)**2/(2*z*z))+math.exp(-(receptor.height_m+height)**2/(2*z*z))
    return (parcel['mass']+parcel.get('vapor',0))*1e9*lateral*vertical/((2*math.pi)**1.5*xy*xy*z)


def dispersion_footprints(parcels, request, minute):
    """Two-standard-deviation moment ellipses; not probability/safety contours."""
    features=[]
    if request.physics is None: return {'type':'FeatureCollection','features':features}
    scale=111320*math.cos(math.radians(request.source_lat))
    for index,ingredient in enumerate(request.ingredients):
        ps=[p for p in parcels if p['index']==index]
        mass=sum(p['mass']+p['vapor'] for p in ps)
        if mass<1e-15: continue
        weights=[(p['mass']+p['vapor'])/mass for p in ps]
        x=sum(w*p['east'] for w,p in zip(weights,ps)); y=sum(w*p['north'] for w,p in zip(weights,ps))
        diffusion=sum(w*(4+2*request.physics.horizontal_diffusivity_m2_s*(minute-p['born']-0.5)*60) for w,p in zip(weights,ps))
        xx=diffusion+sum(w*(p['east']-x)**2 for w,p in zip(weights,ps))
        yy=diffusion+sum(w*(p['north']-y)**2 for w,p in zip(weights,ps))
        xy=sum(w*(p['east']-x)*(p['north']-y) for w,p in zip(weights,ps))
        angle=0.5*math.atan2(2*xy,xx-yy)
        delta=math.hypot(xx-yy,2*xy)
        a=2*math.sqrt(max(0,(xx+yy+delta)/2)); b=2*math.sqrt(max(0,(xx+yy-delta)/2))
        ring=[]
        for i in range(25):
            t=i*2*math.pi/24
            east=x+a*math.cos(t)*math.cos(angle)-b*math.sin(t)*math.sin(angle)
            north=y+a*math.cos(t)*math.sin(angle)+b*math.sin(t)*math.cos(angle)
            ring.append([request.source_lon+east/scale,request.source_lat+north/111320])
        ring[-1]=ring[0]
        features.append({'type':'Feature','geometry':{'type':'Polygon','coordinates':[ring]},
            'properties':{'ingredient':ingredient.name,'kind':'dispersion_moment_ellipse',
                'color':['#a6ffe0','#edc16b','#7fc9ff','#e9a4ce','#c1b4ff'][index%5],
                'meaning':'Illustrative two-sigma moment ellipse of modeled puffs, not a probability or exposure threshold'}})
    return {'type':'FeatureCollection','features':features}


def simulate_spray(request: SprayScenario, _weather=None, _ensemble=True) -> dict:
    location = california_location(request.source_lat, request.source_lon)
    start = request.start_at.astimezone(timezone.utc)
    weather = None
    for receptor in request.receptors:
        california_location(receptor.lat,receptor.lon)
        if math.hypot((receptor.lat-request.source_lat)*111320,(receptor.lon-request.source_lon)*111320*math.cos(math.radians(request.source_lat)))>30000:
            raise ValueError('Receptors must be within 30 km of the source.')
    if request.wind is None:
        weather = _weather or wind_conditions(request.source_lat, request.source_lon)
        hours = sorted((datetime.fromisoformat(h['time_utc']).replace(tzinfo=timezone.utc),
                        h) for h in weather['hours'])
        winds = []
        for minute in range(request.horizon_minutes):
            at = start + timedelta(minutes=minute)
            eligible = [h for h in hours if timedelta(0) <= at-h[0] < timedelta(hours=1)]
            if not eligible:
                raise ValueError('Forecast does not cover the event time; supply explicit scenario winds.')
            _, h = eligible[-1]
            winds.append(WindStep(minute=minute, speed_ms=h['speed_ms'], from_deg=h['from_deg'],
                temperature_c=h.get('temperature_c'),humidity_pct=h.get('humidity_pct'),rain_mm_hr=h.get('rain_mm_hr')))
    else:
        winds = request.wind
    # Each minute releases one parcel per ingredient. Advection uses midpoint
    # timing for a new parcel, then full minutes for subsequent transport.
    parcels = []
    snapshots = []
    deposited = [0.0] * len(request.ingredients)
    degraded = [0.0] * len(request.ingredients)
    released = [0.0] * len(request.ingredients)
    scale = 111320 * math.cos(math.radians(request.source_lat))
    physics=request.physics
    for minute in range(request.horizon_minutes):
        wind = next(w for w in reversed(winds) if w.minute <= minute)
        angle = math.radians((wind.from_deg+180) % 360)
        if minute < request.duration_minutes:
            for index, ingredient in enumerate(request.ingredients):
                mass = ingredient.applied_kg * ingredient.airborne_fraction / request.duration_minutes
                released[index] += mass
                parcels.append(dict(index=index, east=0.0, north=0.0, mass=mass, vapor=0.0, born=minute,
                    diameter=ingredient.droplet_diameter_um))
        for parcel in parcels:
            dt = 0.5 if parcel['born'] == minute else 1.0
            height_factor=(physics.release_height_m/10)**physics.wind_height_exponent if physics else 1
            parcel['east'] += wind.speed_ms * height_factor * 60 * dt * math.sin(angle)
            parcel['north'] += wind.speed_ms * height_factor * 60 * dt * math.cos(angle)
            if math.hypot(parcel['east'],parcel['north'])>30000:
                raise ValueError('Transport exceeds 30 km screening domain. Reduce horizon or wind speed.')
            ingredient = request.ingredients[parcel['index']]
            decay = math.log(2)/ingredient.airborne_half_life_minutes if ingredient.airborne_half_life_minutes else 0
            deposit = math.log(2)/ingredient.deposition_half_life_minutes if ingredient.deposition_half_life_minutes else 0
            vaporize=0.0
            if physics:
                if ingredient.evaporation_um2_s:
                    if wind.temperature_c is None or wind.humidity_pct is None:
                        raise ValueError('Evaporation requires temperature and humidity for every wind step.')
                    # User coefficient is referenced to 20 C and dry air; a
                    # temperature/humidity sensitivity law, not fitted chemistry.
                    factor=max(0,(wind.temperature_c+273.15)/293.15)*(1-wind.humidity_pct/100)
                    parcel['diameter']=math.sqrt(max(ingredient.residual_diameter_um**2,
                        parcel['diameter']**2-ingredient.evaporation_um2_s*factor*dt*60))
                if ingredient.droplet_diameter_um is not None and wind.temperature_c is None:
                    raise ValueError('Settling requires temperature for every wind step.')
                ground=physics.terrain_east_grade*parcel['east']+physics.terrain_north_grade*parcel['north']
                depth=max(0.1,physics.mixing_height_m-ground)
                deposit+=settling_speed(parcel['diameter'],ingredient.density_kg_m3,wind.temperature_c if wind.temperature_c is not None else 20)*60/depth
                if ingredient.rain_scavenging_per_mm:
                    if wind.rain_mm_hr is None: raise ValueError('Rain removal requires precipitation for every wind step.')
                    deposit+=ingredient.rain_scavenging_per_mm*wind.rain_mm_hr/60
                vaporize=math.log(2)/ingredient.volatilization_half_life_minutes if ingredient.volatilization_half_life_minutes else 0
            # Existing vapor decays; transfers remain airborne and conserve mass.
            lost_vapor=parcel['vapor']*-math.expm1(-decay*dt)
            parcel['vapor']-=lost_vapor
            degraded[parcel['index']]+=lost_vapor
            rate = decay+deposit+vaporize
            removed = parcel['mass'] * -math.expm1(-rate*dt)
            if rate:
                degraded[parcel['index']] += removed * decay/rate
                deposited[parcel['index']] += removed * deposit/rate
                parcel['vapor'] += removed * vaporize/rate
            parcel['mass'] -= removed
        if (minute+1) % request.snapshot_interval_minutes == 0 or minute+1 == request.horizon_minutes:
            features = []
            budgets = []
            for index, ingredient in enumerate(request.ingredients):
                budgets.append(dict(ingredient=ingredient.name, released_airborne_kg=released[index],
                    airborne_kg=sum(p['mass']+p['vapor'] for p in parcels if p['index']==index),
                    vapor_kg=sum(p['vapor'] for p in parcels if p['index']==index),
                    deposited_kg=deposited[index], degraded_kg=degraded[index]))
            for parcel in parcels:
                features.append({'type':'Feature', 'geometry':{'type':'Point', 'coordinates':[
                    request.source_lon+parcel['east']/scale, request.source_lat+parcel['north']/111320]},
                    'properties':{'ingredient':request.ingredients[parcel['index']].name,
                        'color':['#a6ffe0','#edc16b','#7fc9ff','#e9a4ce','#c1b4ff'][parcel['index']%5],
                        'airborne_kg':parcel['mass']+parcel['vapor'], 'vapor_kg':parcel['vapor'],
                        'droplet_diameter_um':parcel['diameter'], 'release_minute':parcel['born']}})
            receptors=[]
            if physics:
                for receptor in request.receptors:
                    for index,ingredient in enumerate(request.ingredients):
                        receptors.append({'receptor_id':receptor.id,'ingredient':ingredient.name,
                            'concentration_ug_m3':sum(puff_concentration(p,receptor,request,minute+1) for p in parcels if p['index']==index)})
            snapshots.append({'minute':minute+1, 'at':(start+timedelta(minutes=minute+1)).isoformat(),
                'parcels':{'type':'FeatureCollection', 'features':features}, 'mass_balance':budgets,'receptors':receptors,
                'footprints':dispersion_footprints(parcels,request,minute+1)})
    result={'label':'modelled', 'engine':'Gaussian puff / mixed-layer removal screening' if physics else 'Passive tracer advection with assumed first-order removal',
        'event':request.model_dump(mode='json', exclude={'wind'}), 'location':location,
        'weather':weather or {'kind':'User-specified scenario winds'},
        'wind_steps':[w.model_dump() for w in winds], 'snapshots':snapshots,
        'limitations':[
            'Scheduled or reported input is not independently verified; this does not detect spraying.',
            'Points are parcel centers, not plume boundaries, concentrations, exposure or safety estimates.',
            'Ingredients share parcel advection; optional physics changes dilution, phase and removal, not resolved droplet trajectories.',
            'Optional physics uses assumed diffusivity, mixed-layer settling, D-squared evaporation and first-order transfers. Not AgDRIFT or a validated model.',
            'Application method/formulation are provenance metadata; no method-specific calibration or nozzle spectrum is inferred.',
            'Terrain is an optional planar grade, not a terrain dataset or building airflow solver. No chemical reaction products or resuspension.',
            'No chemical parameters inferred from Neon; missing half-lives mean removal is disabled.',
            'Ensemble ranges, when requested, are sensitivity ranges rather than probabilities. Weather represents one location.',
            'Deposited mass is cumulative only; no deposition footprint is predicted.']}
    if request.uncertainty and _ensemble:
        result['uncertainty']=ensemble(request,result,weather)
    return result


def ensemble(request, base, weather):
    """One-at-a-time sensitivity, retaining failed members and actual time shifts."""
    uncertainty=request.uncertainty
    members=[{'name':'baseline','result':base}]
    scale=111320*math.cos(math.radians(request.source_lat))
    perturbations=[]
    for sign in (-1,1):
        perturbations.extend([
            (f'source_east_{sign}',{'source_lon':request.source_lon+sign*request.location_uncertainty_m/scale}),
            (f'source_north_{sign}',{'source_lat':request.source_lat+sign*request.location_uncertainty_m/111320}),
            (f'time_{sign}',{'start_at':request.start_at+timedelta(minutes=sign*uncertainty.start_minutes)})])
        winds=[WindStep(**{**w, 'from_deg':(w['from_deg']+sign*uncertainty.wind_direction_deg)%360,
                           'speed_ms':min(30,w['speed_ms']*(1+sign*uncertainty.wind_speed_fraction))}) for w in base['wind_steps']]
        perturbations.append((f'wind_{sign}',{'wind':winds}))
        ingredients=[i.model_copy(update={k:getattr(i,k)/(1+sign*uncertainty.removal_rate_fraction) if getattr(i,k) else None
            for k in ('airborne_half_life_minutes','deposition_half_life_minutes','volatilization_half_life_minutes')}) for i in request.ingredients]
        perturbations.append((f'removal_{sign}',{'ingredients':ingredients}))
    for name,changes in perturbations:
        try:
            r=simulate_spray(request.model_copy(update={**changes,'uncertainty':None}),_weather=weather,_ensemble=False)
            members.append({'name':name,'result':r})
        except ValueError as exc: members.append({'name':name,'error':str(exc)})
    features=[]; budgets=[]
    for ingredient in request.ingredients:
        points=[]; masses=[]
        for member in members:
            if 'result' not in member: continue
            frame=member['result']['snapshots'][-1]
            points.extend(f['geometry']['coordinates'] for f in frame['parcels']['features'] if f['properties']['ingredient']==ingredient.name)
            masses.extend(b['airborne_kg'] for b in frame['mass_balance'] if b['ingredient']==ingredient.name)
        xs,ys=zip(*points); lo,hi,bottom,top=min(xs),max(xs),min(ys),max(ys)
        features.append({'type':'Feature','properties':{'ingredient':ingredient.name,'kind':'sensitivity_extent'},
            'geometry':{'type':'Polygon','coordinates':[[[lo,bottom],[hi,bottom],[hi,top],[lo,top],[lo,bottom]]]}})
        budgets.append({'ingredient':ingredient.name,'airborne_kg_min':min(masses),'airborne_kg_max':max(masses)})
    return {'method':'One-at-a-time source, start time, coupled wind direction/speed, and removal-rate perturbations; not a joint uncertainty distribution or confidence interval.',
        'members':[{'name':m['name'],'status':'error' if 'error' in m else 'complete','error':m.get('error')} for m in members],
        'extent':{'type':'FeatureCollection','features':features},'mass_ranges':budgets,
        'time_note':'Time perturbations change forecast selection; custom fixed wind is unchanged by shifting the clock.'}
