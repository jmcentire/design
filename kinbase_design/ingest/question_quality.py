"""Pure evidence selection and grouping for actionable visual questions."""
from collections import Counter
from copy import deepcopy
import json
from ..findings import location
from .mapping import semantic_role
from .quantize import px
from .presentation import literal_node


def role_sizes(views):
    result={}
    for view in views:
        for node in view.get('nodes',[]):
            if literal_node(node):continue
            size=px(node.get('styles',{}).get('font-size'))
            if size is not None and size>0:result.setdefault(semantic_role(node),[]).append(size)
    # A captured heading is still stronger title evidence than a UA body size
    # when the page uses only lower-level headings.
    if not result.get('title') and result.get('subtitle'):result['title']=list(result['subtitle'])
    return result


def size_choices(observed,fallback):
    if not observed:return fallback,list(dict.fromkeys([fallback,14,20,28]))[:4]
    distinct=sorted(set(observed));default=Counter(observed).most_common(1)[0][0]
    if len(distinct)>4:distinct=[distinct[round(i*(len(distinct)-1)/3)] for i in range(4)]
    if len(distinct)==1:distinct=sorted({default,max(.5,round(default*.875*2)/2),max(.5,round(default*1.125*2)/2)})
    return default,distinct


def deduplicate(document,questions):
    groups={}
    for original in questions:
        question=deepcopy(original)
        current=location(document,question['pointer'])[1]
        choices={json.dumps(value,sort_keys=True):value for value in question['values']}
        key=json.dumps([current,sorted(choices)],sort_keys=True)
        target={k:v for k,v in question.items() if k!='values'}
        if key not in groups:
            question['values']=list(choices.values());question['value']=current;question['targets']=[]
            groups[key]=question
        if target not in groups[key]['targets']:groups[key]['targets'].append(target)
    return list(groups.values())
