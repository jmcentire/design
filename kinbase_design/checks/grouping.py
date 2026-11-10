"""Stable review identities and lossless grouping of rendered observations."""
import json
import re
from copy import deepcopy
from .math import effective_background


def resource(value):
    """Keep preview asset names, never a worker's temporary absolute URL."""
    if not isinstance(value, str):
        return value
    return re.sub(r'(?:file://[^\s\"\'()]*|[^\s\"\'()]*?/preview)/assets/', 'assets/', value)


def observation_context(node):
    if node.get('image'):
        return {'asset': node.get('asset') or resource(node.get('imageURL'))}
    layers = [{**layer, 'image': resource(layer.get('image', 'none'))}
              for layer in node.get('backgrounds', [])]
    background = effective_background(layers)
    if background is not None:
        return {'surface': background}
    # Transparent ancestors add no visual distinction to an unresolved surface.
    layers = [layer for layer in layers if layer.get('image', 'none') != 'none'
              or layer.get('uncertain') or layer.get('color') not in ('transparent', 'rgba(0, 0, 0, 0)')]
    return {'surface': layers, 'over_image': node.get('overImage', False)}


def group_rendered(findings):
    """One review item per semantic issue, retaining locations and varied evidence."""
    groups = {}
    for original in findings:
        finding = deepcopy(original)
        context = finding.pop('_context', None)
        key = json.dumps([finding['type'], finding['rule'], finding.get('target'),
                          context, finding.get('exception')], sort_keys=True)
        occurrence = {field: finding[field] for field in ('page', 'width', 'screenshot')}
        evidence = {field: value for field, value in finding.items()
                    if field not in {'page', 'width', 'screenshot', 'occurrences'}}
        if finding['rule']=='word-break':
            evidence.update(occurrence)
        if key not in groups:
            finding['occurrences'] = []
            finding['evidence'] = []
            groups[key] = finding
        group = groups[key]
        if occurrence not in group['occurrences']:
            group['occurrences'].append(occurrence)
        if evidence not in group['evidence']:
            group['evidence'].append(evidence)
    for group in groups.values():
        if len(group['evidence']) == 1:
            del group['evidence']
    return list(groups.values())


def screenshots(finding):
    return {item['screenshot'] for item in [finding, *finding.get('occurrences', [])]
            if item.get('screenshot')}
