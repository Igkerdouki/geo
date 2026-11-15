import httpx
from app import neon_http

def test_parameterized_named_and_array_arguments():
    q=neon_http.parameters('SELECT * FROM x WHERE a=%(name)s AND b=ANY(%(ids)s)',{'name':"x';DROP TABLE x;--",'ids':[1,2]})
    assert q['query']=='SELECT * FROM x WHERE a=$1 AND b=ANY($2)'
    assert q['params']==["x';DROP TABLE x;--",'{"1","2"}']

def test_neon_response_type_decoding_and_transaction(monkeypatch):
    def post(url,**kw):
        assert url=='https://example.neon.tech/sql'
        assert len(kw['json']['queries'])==2
        return httpx.Response(200,json={'results':[{'fields':[],'rows':[]},{'fields':[{'dataTypeID':23},{'dataTypeID':1700},{'dataTypeID':16},{'dataTypeID':3802}], 'rows':[['2','3.5','t','{"x":1}']]}]})
    monkeypatch.setattr(neon_http.httpx,'post',post)
    assert neon_http.batch('postgresql://u:p@example.neon.tech/db',[('CREATE TABLE x(a int)',()),('SELECT 2,3.5,true,json',())])[-1]==[(2,3.5,True,{'x':1})]
