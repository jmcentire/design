"""Separate process gives the entire browser audit a hard wall-clock bound."""
import json
import sys
from ..storage import read_json
from .browser import inspect


def main():
    try:
        job=read_json(__import__('pathlib').Path(sys.argv[1]))
        findings=inspect(job['document'],job['vocabulary'],job['preview'],job['output'],job['widths'])
        print(json.dumps({'findings':findings},ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({'error':str(exc)}))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
