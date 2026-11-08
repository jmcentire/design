"""Automation boundary over the same operations used by the workbench."""
import argparse
import json
import logging
import sys
from wsgiref.simple_server import make_server, WSGIRequestHandler
from . import vocabulary
from .artifacts import import_file
from .assets import promote
from .config import roots
from .language import validate, resolve
from .language.versions import mint
from .storage import load_language


def parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--library', default=argparse.SUPPRESS)
    common.add_argument('--workspace', default=argparse.SUPPRESS)
    p = argparse.ArgumentParser(prog='kinbase-design', parents=[common])
    commands = p.add_subparsers(dest='command', required=True)
    for name in ('vocabulary','validate','resolve','build-preview','mint','import-artifact','promote','serve','check','capture','draft','save-draft','fidelity','questions','answer'):
        sub = commands.add_parser(name, parents=[common])
        if name in {'validate','resolve','build-preview','mint','promote','check'}:
            sub.add_argument('language_id')
        if name == 'resolve':
            sub.add_argument('scope')
            sub.add_argument('--state', default='default')
            sub.add_argument('--breakpoint')
        if name == 'build-preview':
            sub.add_argument('--out', required=True)
        if name == 'check':
            sub.add_argument('--out')
            sub.add_argument('--widths')
        if name == 'import-artifact':
            sub.add_argument('--file', required=True)
            sub.add_argument('--kind', choices=['image','mock','wireframe','figma-export','dtcg','asset','brief'])
        if name == 'capture':
            sub.add_argument('--url', action='append', required=True)
            sub.add_argument('--widths')
        if name == 'draft':
            sub.add_argument('--from', dest='artifacts', action='append', required=True)
            sub.add_argument('--language', required=True)
        if name in {'save-draft','fidelity','questions','answer'}:
            sub.add_argument('draft_id')
        if name == 'answer':
            sub.add_argument('question_id')
            sub.add_argument('candidate_id')
        if name == 'promote':
            sub.add_argument('--artifact', required=True)
            sub.add_argument('--asset-id', required=True)
            sub.add_argument('--kind', choices=['logo','font','image','icon'], required=True)
            sub.add_argument('--variant', required=True)
            sub.add_argument('--weight', type=int)
            sub.add_argument('--style', choices=['normal','italic'])
            sub.add_argument('--family')
        if name == 'serve':
            sub.add_argument('--host', choices=['127.0.0.1'], default='127.0.0.1')
            sub.add_argument('--port', type=int, default=8765)
    generate = commands.add_parser('generate', parents=[common])
    actions = generate.add_subparsers(dest='generate_action', required=True)
    for name in ('start','interview','moodboard','pair','choose','settled','derive'):
        sub = actions.add_parser(name, parents=[common])
        if name == 'start':
            sub.add_argument('--brief', required=True)
            sub.add_argument('--artifact', action='append', default=[])
        else:sub.add_argument('session')
        if name == 'interview':sub.add_argument('--answers', required=True)
        if name == 'moodboard':
            sub.add_argument('--pin');sub.add_argument('--remove')
        if name == 'choose':
            sub.add_argument('pair');sub.add_argument('choice', choices=['A','B','neither'])
            sub.add_argument('--comment', default='');sub.add_argument('--supersedes')
        if name == 'derive':sub.add_argument('--language', required=True)
    return p


def output(value):
    print(json.dumps(value, ensure_ascii=False, allow_nan=False))


def main(argv=None):
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s %(message)s')
    try:
        library, workspace = roots(getattr(args, 'library', None), getattr(args, 'workspace', None))
        if args.command == 'generate':
            from . import generate
            action=args.generate_action
            if action=='start':result=generate.start(library,workspace,args.brief,args.artifact)
            elif action=='interview':result=generate.interview(workspace,args.session,json.loads(args.answers))
            elif action=='moodboard':result=generate.moodboard(library,workspace,args.session,args.pin,args.remove)
            elif action=='pair':result=generate.pair(library,workspace,args.session)
            elif action=='choose':result=generate.choose(workspace,args.session,args.pair,args.choice,args.comment,args.supersedes)
            elif action=='settled':result=generate.settled(workspace,args.session)
            else:result=generate.derive(library,workspace,args.session,args.language)
            output(result)
            if isinstance(result,dict) and result.get('accepted') is False:return 1
        elif args.command == 'vocabulary':
            output(vocabulary.load(library))
        elif args.command == 'validate':
            result = validate(library, args.language_id)
            output(result)
            return 0 if result['accepted'] else 1
        elif args.command in {'resolve', 'build-preview'}:
            result = validate(library, args.language_id)
            if not result['accepted']:
                output(result)
                return 1
            document = load_language(library, args.language_id)
            if args.command == 'resolve':
                output(resolve(document, vocabulary.load(library, document['vocabulary']), args.scope, args.state, args.breakpoint))
            else:
                from .render import build_preview
                build_preview(library, args.language_id, args.out)
                output({'language': args.language_id, 'built': True})
        elif args.command == 'check':
            from .checks import check
            result = check(library, args.language_id, args.out, args.widths)
            output(result)
            return 0 if result['accepted'] else 1
        elif args.command == 'mint':
            result = mint(library, args.language_id)
            output(result)
            return 0 if 'ref' in result else 1
        elif args.command == 'import-artifact':
            output({'artifact': import_file(workspace, args.file, args.kind)})
        elif args.command == 'capture':
            from .artifacts.capture import capture
            output(capture(workspace,args.url,args.widths))
        elif args.command in {'draft','save-draft','questions','answer','fidelity'}:
            from .ingest import draft,save_draft,questions,answer
            if args.command=='draft':result=draft(library,workspace,args.artifacts,args.language)
            elif args.command=='save-draft':result=save_draft(library,workspace,args.draft_id)
            elif args.command=='questions':result=questions(workspace,args.draft_id)
            elif args.command=='answer':result=answer(library,workspace,args.draft_id,args.question_id,args.candidate_id)
            else:
                from .ingest.fidelity import fidelity
                result=fidelity(library,workspace,args.draft_id)
            output(result)
            if isinstance(result,dict) and result.get('accepted') is False:return 1
        elif args.command == 'promote':
            output(promote(library, workspace, args.language_id, args.artifact, args.asset_id,
                           args.kind, args.variant, args.weight, args.style, args.family))
        elif args.command == 'serve':
            from .workbench import create_app
            class RequestHandler(WSGIRequestHandler):
                def log_message(self, format, *values):
                    logging.getLogger('kinbase_design.server').info('request result=%s', (format % values)[:200])
            with make_server(args.host, args.port, create_app(library, workspace), handler_class=RequestHandler) as server:
                print(f'listening http://{args.host}:{server.server_port}/', flush=True)
                server.serve_forever()
        return 0
    except (ValueError, OSError, KeyError) as exc:
        output({'error': str(exc)})
        logging.getLogger(__name__).error('operation_failed command=%s language=%s error=%s', args.command, getattr(args,'language_id','-'), str(exc)[:300])
        return 2


if __name__ == '__main__':
    sys.exit(main())
