"""Test-owned external Kinbase seam, not a substitute for Kinbase behavior.

Copies are launched as real executables named kinbase and kin. Responses are test
inputs in responses.json beside this file; every argv is appended to calls.jsonl.
Only the public M4 command grammar is implemented. No network or product imports.
"""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parent
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with (root / "calls.jsonl").open("a") as output:
    output.write(json.dumps({"executable": name, "argv": args}) + "\n")
responses = json.loads((root / "responses.json").read_text())

if name == "kinbase" and args and args[0] == "explain":
    # Flag ordering is not contractual. Require exactly the existing options,
    # without swallowing unknown positional values or additional switches.
    if len(args) != 7 or args.count("--repo") != 1 or args.count("--decision") != 1 or args.count("--json") != 1:
        raise SystemExit(2)
    key = args[1]
    if key not in responses["explain"]:
        raise SystemExit(2)
    print(json.dumps(responses["explain"][key]))
elif name == "kinbase" and len(args) == 3 and args[:2] == ["questions", "ask"]:
    print(json.dumps(responses["questions"][args[2]]))
elif name == "kin" and args[:2] == ["kinbase", "submit"]:
    if len(args) != 8 or args.count("--repo") != 1 or args.count("--type") != 1 or args.count("--json") != 1:
        raise SystemExit(2)
    kind = args[args.index("--type") + 1]
    if kind not in {"concept", "question", "decision"}:
        raise SystemExit(2)
    print(json.dumps(responses["submit"][kind]))
else:
    print("Unsupported command at independent Kinbase seam", file=sys.stderr)
    raise SystemExit(2)
