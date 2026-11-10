#!/usr/bin/env python3
"""Opt-in stdin → JSON adapter using the user's existing Codex CLI login."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    limit=4*1024*1024
    raw=sys.stdin.buffer.read(limit+1)
    if len(raw)>limit:raise ValueError('Adapter input exceeds byte limit')
    request=json.loads(raw)
    prompt=('Act only as a JSON interpreter for this request. Do not use tools, inspect files, run commands, '
            'or modify anything. Return only the requested JSON, without Markdown.\n'+json.dumps(request,ensure_ascii=False))
    with tempfile.TemporaryDirectory(prefix='design-codex-') as directory:
        output=Path(directory)/'response.json'
        result=subprocess.run(['codex','exec','--sandbox','read-only','--ephemeral','--skip-git-repo-check',
                               '--cd',directory,'--output-last-message',str(output),'-'],
                              input=prompt,text=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=110)
        if result.returncode:raise ValueError('Codex interpretation failed with exit '+str(result.returncode))
        if not output.exists() or output.stat().st_size>limit:raise ValueError('Codex returned no bounded response')
        value=json.loads(output.read_text())
        json.dump(value,sys.stdout,ensure_ascii=False,allow_nan=False)


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.TimeoutExpired) as exc:
        print(str(exc),file=sys.stderr);sys.exit(1)
