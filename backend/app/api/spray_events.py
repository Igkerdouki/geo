"""Persistent event provenance. Scheduled notices never become confirmed sprays."""
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Header
from pydantic import Field, AwareDatetime, model_validator
from app.spray_transport import InputModel
from app.coverage import california_location
from app import workflow_store

router=APIRouter(prefix='/application-events')


class EventIngredient(InputModel):
    name: str = Field(min_length=1,max_length=120)
    applied_kg: float | None = Field(default=None,gt=0,le=100000)


class ApplicationEvent(InputModel):
    kind: Literal['scheduled','reported']
    source_id: str = Field(min_length=1,max_length=150)
    source: str = Field(min_length=1,max_length=500)
    source_url: str | None = Field(default=None,max_length=1000)
    start_at: AwareDatetime
    latest_start_at: AwareDatetime | None = None
    lat: float
    lon: float
    location_uncertainty_m: float = Field(ge=0,le=10000)
    ingredients: list[EventIngredient] = Field(min_length=1,max_length=20)
    application_method: str | None = Field(default=None,max_length=100)
    duration_minutes: int | None = Field(default=None,ge=1,le=1440)
    status: Literal['scheduled','started','completed','cancelled']
    notes: str = Field(default='',max_length=1500)

    @model_validator(mode='after')
    def check(self):
        california_location(self.lat,self.lon)
        if self.kind=='scheduled' and self.status not in {'scheduled','cancelled'}:
            raise ValueError('A scheduled notice cannot confirm that spraying started.')
        if self.kind=='reported' and self.status=='scheduled':
            raise ValueError('Use scheduled kind for intended applications.')
        if self.latest_start_at and self.latest_start_at<self.start_at:
            raise ValueError('Latest start must follow intended start.')
        if self.source_url and not self.source_url.startswith('https://'):
            raise ValueError('Source URL must use HTTPS.')
        return self


class NotificationImport(InputModel):
    events: list[ApplicationEvent] = Field(min_length=1,max_length=100)


def record_event(event, authentication='unverified_user_report'):
    data=event.model_dump(mode='json')
    event_id=hashlib.sha256((event.source+'\n'+event.source_id+'\n'+authentication).encode()).hexdigest()[:24]
    record={**data,'id':event_id,'authentication':authentication,
        'received_at':datetime.now(timezone.utc).isoformat(),
        'payload_sha256':hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest(),
        'verification':'Reported by caller; not an independently measured application.'}
    # Keep a separate immutable revision as well as the latest event state.
    workflow_store.save('event_revision',{**record,'event_id':event_id,'id':uuid4().hex})
    return workflow_store.save('application_event',record)


@router.post('/reports')
def report_application(body: ApplicationEvent):
    if body.kind!='reported': raise HTTPException(422,'Use the notification import for scheduled events.')
    try: return record_event(body)
    except Exception: raise HTTPException(503,'Event could not be saved.') from None


@router.post('/telemetry')
def telemetry(body: ApplicationEvent, authorization: str | None = Header(default=None)):
    token=os.getenv('GEO_INGEST_TOKEN')
    if not token: raise HTTPException(503,'Authenticated equipment ingestion is not configured.')
    if not hmac.compare_digest(authorization or '', 'Bearer '+token):
        raise HTTPException(401,'Invalid equipment credential.')
    if body.kind!='reported': raise HTTPException(422,'Telemetry must report an application state.')
    try: return record_event(body,'authenticated_equipment')
    except Exception: raise HTTPException(503,'Event could not be saved.') from None


@router.post('/spraydays/import')
def import_notifications(body: NotificationImport):
    if any(e.kind!='scheduled' or e.source!='SprayDays' or not (e.source_url or '').startswith('https://spraydays.cdpr.ca.gov/') for e in body.events):
        raise HTTPException(422,'Import requires scheduled SprayDays notices with their public source URLs.')
    if any(event.location_uncertainty_m<1140 for event in body.events):
        raise HTTPException(422,'Section-level notices require at least 1140 m location uncertainty.')
    results=[]
    try:
        for event in body.events:
            # The public section is approximate; require callers to retain this.
            if event.latest_start_at is None: event.latest_start_at=event.start_at+timedelta(days=4)
            results.append(record_event(event,'imported_notice_unverified'))
    except HTTPException: raise
    except Exception: raise HTTPException(503,'Import interrupted; refresh events to inspect saved records before retrying.') from None
    return {'events':results,'scope':'User-imported notices, not an automatic official feed or verified actual start.'}


@router.get('')
def events():
    try: return {'events':workflow_store.list_items('application_event'),
        'automatic_spraydays_feed':False,'telemetry_configured':bool(os.getenv('GEO_INGEST_TOKEN'))}
    except Exception: raise HTTPException(503,'Event store unavailable.') from None
