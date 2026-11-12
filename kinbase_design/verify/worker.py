"""Separate process gives the whole site audit a hard wall-clock bound."""
import json
from pathlib import Path
import sys
from ..storage import read_json
from .browser import inspect


def main():
    try:
        job = read_json(Path(sys.argv[1]))
        findings, summary = inspect(job['document'], job['vocabulary'], job['pages'], job['output'], job['widths'], job['javascript'], job['preview'])
        print(json.dumps({'findings': findings, 'summary': summary}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({'error': str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
