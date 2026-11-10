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
    assert 'source_nodes' not in first
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

def test_source_selection_preserves_server_context_and_versioned_evidence(tmp_path):
    # Native files(ids=...) selects the source server-side; returned ancestors,
    # other pages and component dependencies remain immutable source evidence.
    from copy import deepcopy
    from kinbase_design.design_evidence import export
    source = deepcopy(SOURCE)
    first = source['document']['children'][0]
    second = deepcopy(first); second['id'] = 'component-A'
    dependency = deepcopy(first); dependency['id'] = '9:9'
    source['document']['children'] = [
        {'id': '0:2', 'type': 'CANVAS', 'children': [first, second]},
        {'id': '0:3', 'type': 'CANVAS', 'children': [dependency]}]
    class SelectedAPI(API):
        def get(self, path, **query):
            self.requests.append((path, query))
            return source
    api = SelectedAPI()
    selected = snapshot(tmp_path, 'example', '42', api, source_nodes=['component-A', ' 1:2 ', 'component-A'])
    assert api.requests == [('files/example', {'version': '42', 'ids': '1:2,component-A'})]
    assert json.loads(read_member(tmp_path, selected['artifact'], 'figma.json')) == source
    again = snapshot(tmp_path, 'example', '42', api, source_nodes=['1:2', 'component-A'])
    narrower = snapshot(tmp_path, 'example', api=api, source_nodes=['1:2'])
    assert api.requests[-1] == ('files/example', {'ids': '1:2'})
    assert again['artifact'] == selected['artifact'] != narrower['artifact']
    assert selected['source_nodes'] == ['1:2', 'component-A']
    assert metadata(tmp_path, selected['artifact'])['details']['source'] == {
        'provider': 'figma', 'file_key': 'example', 'version': '42', 'source_nodes': ['1:2', 'component-A']}
    assert metadata(tmp_path, narrower['artifact'])['details']['source']['version'] == '42'
    out = tmp_path / 'observations.jsonl'
    receipt = export(tmp_path, selected['artifact'], out)
    observations = [json.loads(line) for line in out.read_text().splitlines()]
    assert receipt['status'] == 'prepared-not-submitted'
    assert {r['source']['node_id'] for r in observations} == {'1:2', 'component-A', '9:9'}
    assert all(r['source']['version'] == '42' and r['source']['digest'] == selected['artifact']
               for r in observations)
    assert '#0080ff' in collect(tmp_path, [selected['artifact']])['colors']

def test_missing_selected_source_node_leaves_no_artifact(tmp_path):
    api = API()
    for invalid in (' ', '1:2,4:5'):
        with pytest.raises(ValueError):
            snapshot(tmp_path, 'example', api=api, source_nodes=[invalid])
    assert api.requests == []
    with pytest.raises(ValueError, match='4:5'):
        snapshot(tmp_path, 'example', api=API(), source_nodes=['1:2', '4:5'])
    assert not (tmp_path / 'artifacts').exists() or not list((tmp_path / 'artifacts').iterdir())

def test_cli_forwards_repeated_source_nodes_to_native_file_query(library, monkeypatch, capsys):
    from kinbase_design import cli, figma
    api = API()
    # Authorized external-client construction seam: run the real CLI, snapshot,
    # query construction and artifact writer; only the external API is synthetic.
    monkeypatch.setattr(figma, 'client', lambda: api)
    cli.main(['figma', 'pull', '--file-key', 'example', '--version', '42',
              '--source-node', '1:2', '--source-node', ' 0:1 ', '--source-node', '1:2',
              '--library', str(library.library), '--workspace', str(library.workspace)])
    result = json.loads(capsys.readouterr().out)
    assert api.requests == [('files/example', {'version': '42', 'ids': '0:1,1:2'})]
    assert result['source_nodes'] == ['0:1', '1:2']
    assert metadata(library.workspace, result['artifact'])['details']['source']['source_nodes'] == ['0:1', '1:2']
    assert json.loads(read_member(library.workspace, result['artifact'], 'figma.json')) == SOURCE

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

def test_evidence_identity_survives_source_edits_without_colliding(tmp_path):
    from copy import deepcopy
    from kinbase_design.design_evidence import records
    class ChangingAPI(API):
        def __init__(self, version, size, comment):
            self.source=deepcopy(SOURCE)
            self.source['version']=version
            self.source['lastModified']='2026-11-01T00:00:00Z' if version=='42' else '2026-11-02T00:00:00Z'
            node=self.source['document']['children'][0]
            node['style']['fontSize']=size
            if version=='43':node['style'].pop('fontFamily')
            other=deepcopy(node); other['id']='2:3'
            self.source['document']['children'].append(other)
            self.comment=comment
        def get(self,path,**query):
            if path.endswith('/comments'):
                return {'comments':[{'id':'c1','message':self.comment},
                                    {'id':'c2','message':'A distinct comment'},
                                    {'message':'No stable identity'}]}
            return self.source
    old=records(tmp_path,snapshot(tmp_path,'example',api=ChangingAPI('42',32,'Old'),comments=True)['artifact'])
    new=records(tmp_path,snapshot(tmp_path,'example',api=ChangingAPI('43',40,'Revised'),comments=True)['artifact'])
    assert len(old)==len(new)==4
    assert len({r['id'] for r in old})==4
    assert {r['id'] for r in old}=={r['id'] for r in new}
    by_id={r['id']:r for r in old}
    for record in new:
        previous=by_id[record['id']]
        assert previous['source']['digest']!=record['source']['digest']
        if record['source']['evidence_kind']=='node-values':
            assert previous['source']['version']=='42' and record['source']['version']=='43'
            assert previous['statement']!=record['statement']
            assert record['source']['time_basis']=='source-modified'
            assert previous['updated_at'] < record['updated_at']
            assert record['updated_at']=='2026-11-02T00:00:00Z'
            assert 'font_family' not in record['statement']
        elif record['source']['comment_id']=='c1':
            assert record['source']['time_basis']=='observed'
            assert 'Revised' in record['statement'] and 'Old' in previous['statement']
    other=records(tmp_path,snapshot(tmp_path,'differentfile',api=ChangingAPI('43',40,'Revised'),comments=True)['artifact'])
    assert not {r['id'] for r in other}&{r['id'] for r in new}
