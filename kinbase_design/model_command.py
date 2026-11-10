"""The existing opt-in JSON command boundary, shared by mapping and feedback."""
import json
import os
import shlex
import subprocess
from .config import INGEST_LLM_TIMEOUT_SECONDS, MAX_JSON_BYTES


class CommandUnavailable(ValueError):
    pass


def configured():
    return bool(os.environ.get('KINBASE_DESIGN_LLM_COMMAND'))


def request(payload, timeout=INGEST_LLM_TIMEOUT_SECONDS):
    command=os.environ.get('KINBASE_DESIGN_LLM_COMMAND')
    if not command:raise CommandUnavailable('KINBASE_DESIGN_LLM_COMMAND is not configured')
    data=json.dumps(payload,ensure_ascii=False,allow_nan=False)
    if len(data.encode())>MAX_JSON_BYTES:raise ValueError('Adapter input exceeds byte limit')
    try:
        args=shlex.split(command)
        if not args:raise CommandUnavailable('Configured model command is empty')
        result=subprocess.run(args,input=data,text=True,capture_output=True,timeout=timeout)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise CommandUnavailable('Configured model command unavailable: '+str(exc)[:300]) from exc
    if result.returncode:raise CommandUnavailable('Configured model command failed with exit '+str(result.returncode))
    if len(result.stdout.encode())>MAX_JSON_BYTES:raise ValueError('Adapter output exceeds byte limit')
    return json.loads(result.stdout,parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Invalid JSON number '+value)))
