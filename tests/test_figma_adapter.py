import json
import pytest
from kinbase_design.figma import snapshot, tokens_from, Client
from kinbase_design.artifacts.bundle import read_member, metadata
from kinbase_design.ingest.sources import collect

SOURCE = {'version': '42', 'document': {'id': '0:1', 'children': [
    {'id': '1:2', 'name': 'Editorial title', 'fills': [{'type': 'SOLID', 'color': {'r': 0, 'g': .5, 'b': 1}}],
     'style': {'fontFamily': 'Example Sans', 'fontSize': 32}}]}}

class API:
    def __init__(self): self.requests = []
    def get(self, path, **query):
        self.requests.append((path, query))
        return SOURCE

def test_snapshot_is_immutable_versioned_and_feeds_existing_ingest(tmp_path):
    api = API()
    first = snapshot(tmp_path, 'example', '42', api)
    second = snapshot(tmp_path, 'example', '42', api)
    assert first['artifact'] == second['artifact']
    assert api.requests[0] == ('files/example', {'version': '42'})
    assert json.loads(read_member(tmp_path, first['artifact'], 'figma.json')) == SOURCE
    meta = metadata(tmp_path, first['artifact'])
    assert meta['details']['source'] == {'provider': 'figma', 'file_key': 'example', 'version': '42'}
    result = collect(tmp_path, [first['artifact']])
    assert not result['problems']
    assert '#0080ff' in result['colors']
    assert '"Example Sans"' in result['source_facts']['font_families']

def test_version_and_input_validation_prevents_wrong_source(tmp_path):
    api = API()
    with pytest.raises(ValueError, match='different version'): snapshot(tmp_path, 'example', '43', api)
    with pytest.raises(ValueError): snapshot(tmp_path, 'https://evil.example/', api=api)
    assert len(api.requests) == 1

def test_no_cross_project_credential_fallback(monkeypatch):
    from kinbase_design.figma import client
    monkeypatch.delenv('FIGMA_ACCESS_TOKEN', raising=False)
    monkeypatch.setenv('MEA_FIGMA_API_KEY', 'must-not-use')
    with pytest.raises(ValueError, match='FIGMA_ACCESS_TOKEN'): client()

def test_transport_never_discloses_token_in_failure(monkeypatch):
    from urllib.error import HTTPError
    c = Client('secret-example')
    class Opener:
        def open(self, request, timeout):
            assert request.full_url == 'https://api.figma.com/v1/me'
            assert request.get_header('X-figma-token') == 'secret-example'
            raise HTTPError(request.full_url, 403, 'secret-example', {}, None)
    c.opener = Opener()
    with pytest.raises(ValueError) as error: c.get('me')
    assert '403' in str(error.value) and 'secret-example' not in str(error.value)

def test_redirect_does_not_forward_credential():
    from kinbase_design.figma import NoRedirect
    assert NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example') is None

def test_optional_sources_are_private_version_honest_and_feed_image_sampling(tmp_path):
    from io import BytesIO
    from PIL import Image
    pixels=BytesIO(); Image.new('RGB',(4,4),(255,0,0)).save(pixels,format='PNG')
    class Response(BytesIO): pass
    class Opener:
        def open(self, request, timeout):
            assert request.get_header('X-figma-token') is None
            assert request.full_url.startswith('https://figma-alpha-api.s3.us-west-2.amazonaws.com/')
            return Response(pixels.getvalue())
    class ExtraAPI(API):
        opener=Opener()
        def get(self,path,**query):
            if path.startswith('images/'):
                assert query['version']=='42'
                return {'images':{'1:2':'https://figma-alpha-api.s3.us-west-2.amazonaws.com/render.png'}}
            if path.endswith('/variables/local'):
                return {'meta':{'variables':{'v1':{'resolvedType':'COLOR','valuesByMode':{'dark':{'r':0,'g':1,'b':0,'a':1}}}}}}
            if path.endswith('/comments'):return {'comments':[{'id':'c1','message':'Prefer more breathing room','user':{'id':'u1'}}]}
            return super().get(path,**query)
    result=snapshot(tmp_path,'example','42',ExtraAPI(),nodes=['1:2'],variables=True,comments=True)
    meta=metadata(tmp_path,result['artifact'])
    evidence=meta['details']['observations']
    assert evidence[0]['file_version']=='42'
    assert all(e['file_version'] is None and e['association']=='live-unversioned' for e in evidence[1:])
    assert json.loads(read_member(tmp_path,result['artifact'],'comments.json'))['comments'][0]['id']=='c1'
    collected=collect(tmp_path,[result['artifact']])
    assert collected['references'] and '#00ff00' in collected['colors']
    assert not collected['problems']
    from kinbase_design.design_evidence import records
    observations=records(tmp_path,result['artifact'])
    comment=next(r for r in observations if r['source']['evidence_kind']=='comment-observation')
    assert 'Prefer more breathing room' in comment['statement']
    assert comment['source']['version'] is None and comment['author_kind']=='agent'

def test_optional_permission_failure_retains_core_snapshot_and_reports_gap(tmp_path):
    class Denied(API):
        def get(self,path,**query):
            if path.endswith('/comments'):raise ValueError('Figma request failed (HTTP 403)')
            return SOURCE
    result=snapshot(tmp_path,'example',api=Denied(),comments=True)
    assert read_member(tmp_path,result['artifact'],'figma.json')
    assert any('403' in gap for gap in result['gaps'])

def test_render_rejects_unobserved_nodes_and_untrusted_hosts(tmp_path):
    from kinbase_design.figma_extra import download_png
    with pytest.raises(ValueError,match='absent'):snapshot(tmp_path,'example',api=API(),nodes=['missing'])
    for url in ['http://figma.com/image','https://localhost/image','https://other.s3.us-west-2.amazonaws.com/a',
                'https://api.figma.com.evil.example/a','https://user:secret@figma.com/a']:
        with pytest.raises(ValueError):download_png(API(),url)

def test_variable_color_aliases_do_not_cross_modes_or_loop():
    from kinbase_design.figma_extra import color_tokens
    data={'meta':{'variables':{
        'a':{'resolvedType':'COLOR','valuesByMode':{'light':{'type':'VARIABLE_ALIAS','id':'b'}}},
        'b':{'resolvedType':'COLOR','valuesByMode':{'light':{'type':'VARIABLE_ALIAS','id':'a'}}}}}}
    assert color_tokens(data)=={}

def test_evidence_is_agent_observation_and_export_is_idempotent(tmp_path):
    from kinbase_design.design_evidence import records, export
    artifact=snapshot(tmp_path,'example','42',API())['artifact']
    values=records(tmp_path,artifact)
    assert values and all(v['author_kind']=='agent' for v in values)
    assert values[0]['source']['version']=='42' and values[0]['source']['node_id']=='1:2'
    assert values[0]['schema']=='design-evidence/1'
    out=tmp_path/'evidence'/'observations.jsonl'
    assert export(tmp_path,artifact,out)['status']=='prepared-not-submitted'
    assert export(tmp_path,artifact,out)['observations']==len(values)
    out.write_text('different')
    with pytest.raises(ValueError,match='different content'):export(tmp_path,artifact,out)

def test_repository_receipt_does_not_claim_company_adoption(tmp_path, monkeypatch):
    from kinbase_design import kinbase
    from types import SimpleNamespace
    monkeypatch.setattr(kinbase,'status',lambda *args:{'connected':True})
    monkeypatch.setattr(kinbase,'command',lambda *args,**kwargs:{'ok':True,'receipt':{'received':True}})
    receipt=kinbase.submit(tmp_path,'Observed spacing','concept',SimpleNamespace(repo=str(tmp_path)))
    assert receipt['status']=='received'
    assert receipt['delivery_scope']=='repository-evidence'
    assert receipt['company_publication']==receipt['adoption']=='not-verified'
