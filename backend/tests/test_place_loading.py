import httpx
import pytest
from fastapi import HTTPException
from app.api import place


def test_unavailable_tiles_return_explicit_retryable_error(monkeypatch):
    class Offline:
        def __init__(self,**kw):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,url):raise httpx.ConnectError('offline')
    monkeypatch.setattr(place.httpx,'Client',Offline)
    place._CACHE.clear()
    with pytest.raises(HTTPException) as error:
        place.place(lat=35.2045,lon=-118.8317,radius_m=1000,name='Arvin')
    assert error.value.status_code==503
    assert 'geometry' in error.value.detail
