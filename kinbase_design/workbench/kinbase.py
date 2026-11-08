"""Explicit feedback/proposal/question actions; reading a preview never submits."""
from uuid import uuid4
from .. import kinbase
from ..storage import inside,identifier,write_json
from .ingest import fields


def handle(library,workspace,language_id,action,environ):
    data={k:v[0] for k,v in fields(environ).items()}
    if action=='feedback':
        result=kinbase.feedback(library,workspace,language_id,data.get('author',''),data.get('target',''),data.get('text',''),data.get('flag')=='yes')
        receipt_id=result['id']
    elif action=='propose':
        result=kinbase.propose(library,workspace,language_id,data.get('scope',''))
        receipt_id=result['id']
    elif action=='kinbase-question':
        result=kinbase.ask(library,data.get('question',''));receipt_id='question-'+uuid4().hex
        write_json(inside(workspace,'kinbase-receipts',receipt_id+'.json'),result)
    else:raise ValueError('Unknown Kinbase action')
    return '/languages/'+identifier(language_id)+'?receipt='+receipt_id
