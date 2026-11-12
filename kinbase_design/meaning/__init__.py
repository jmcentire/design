"""The meaning layer: what a source's tokens mean, in Vocabulary terms, and who says so.

Discover drafts candidate mappings with provenance. Ground restricts every mapping to
Vocabulary enums and the closed property set. A reviewer's local choice orders above a
candidate; only Kinbase's scoped authority certifies. Queries label every mapping with
its standing, so a proposal is never presented as a rule.
"""
from ..vocabulary import load as load_vocabulary
from . import graph
from .language import draft, apply, check
from .query import impact, define


def discover(library, workspace, corpus, artifact_ids, only=()):
    return graph.discover(workspace, load_vocabulary(library), corpus, artifact_ids, only)


def show(library, workspace, corpus):
    return graph.show(workspace, load_vocabulary(library), corpus)


def choose(library, workspace, corpus, subject, author, meaning=None, gap=None, accept=False, note=''):
    return graph.choose(workspace, load_vocabulary(library), corpus, subject, author, meaning, gap, accept, note)


def sync(library, workspace, corpus):
    return graph.sync(library, workspace, load_vocabulary(library), corpus)


def propose(library, workspace, corpus, author, subjects=()):
    return graph.propose(library, workspace, load_vocabulary(library), corpus, author, subjects)


__all__ = ['discover', 'show', 'choose', 'sync', 'propose', 'draft', 'apply', 'check', 'impact', 'define']
