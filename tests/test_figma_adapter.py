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
