"""Content-addressed multi-file originals, published only after complete capture/import."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from ..config import ARTIFACT_MAX_BYTES, ARTIFACT_MAX_FILES, MAX_UPLOAD_BYTES
from ..storage import identifier, inside, read_json, write_json
from . import import_bytes


def member_name(name):
    path = PurePosixPath(name)
    if not name or name=='metadata.json' or path.is_absolute() or '..' in path.parts or '\\' in name or str(path) != name:
        raise ValueError('Invalid artifact member name')
    return name


def import_bundle(workspace, files, kind, details=None):
    if len(files) > ARTIFACT_MAX_FILES or sum(map(len, files.values())) > ARTIFACT_MAX_BYTES:
        raise ValueError('Artifact bundle exceeds configured limits')
    members = {member_name(name): {'sha256':hashlib.sha256(data).hexdigest(), 'size':len(data)}
               for name,data in sorted(files.items())}
    identity = {'kind':kind,'members':members,'details':details or {}}
    digest = hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    artifact_id = 'artifact-' + digest
    parent = inside(workspace,'artifacts'); parent.mkdir(parents=True,exist_ok=True)
    destination = inside(parent,artifact_id)
    if not destination.exists():
        with TemporaryDirectory(dir=parent,prefix='.capture-') as temp:
            for name,data in files.items():
                path=inside(temp,name); path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
            write_json(inside(temp,'metadata.json'),{'id':artifact_id,**identity,'created':datetime.now(timezone.utc).isoformat()})
            Path(temp).rename(destination)
    return artifact_id


def metadata(workspace, artifact_id):
    return read_json(inside(workspace,'artifacts',identifier(artifact_id),'metadata.json'))


def read_member(workspace, artifact_id, name):
    meta = metadata(workspace,artifact_id)
    detail = meta.get('members',{}).get(member_name(name))
    if detail is None:
        raise ValueError('Unknown artifact member')
    path = inside(workspace,'artifacts',artifact_id,name)
    if path.stat().st_size != detail['size'] or detail['size'] > ARTIFACT_MAX_BYTES:
        raise ValueError('Immutable artifact size mismatch')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=detail['sha256']:
        raise ValueError('Immutable artifact content mismatch')
    return data


def import_directory(workspace, directory, kind):
    if kind!='figma-export':
        raise ValueError('Directories must be imported as figma-export')
    directory=Path(directory)
    if directory.is_symlink():raise ValueError('Export symlinks are not supported')
    files={}; children=[]; total=0
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():raise ValueError('Export symlinks are not supported')
        if not path.is_file():continue
        size=path.stat().st_size; total+=size
        if size>MAX_UPLOAD_BYTES or total>ARTIFACT_MAX_BYTES or len(files)>=ARTIFACT_MAX_FILES:
            raise ValueError('Figma export exceeds configured limits')
        name=path.relative_to(directory).as_posix()
        if name=='metadata.json':name='export/metadata.json'
        if name in files:raise ValueError('Export member name collision')
        files[name]=path.read_bytes()
        file_kind='dtcg' if path.suffix.lower()=='.json' else 'image' if path.suffix.lower() in {'.png','.jpg','.jpeg','.webp'} else 'asset'
        children.append({'artifact':import_bytes(workspace,files[name],path.name,file_kind),'location':name,'kind':file_kind})
    if not files:raise ValueError('Export directory is empty')
    return import_bundle(workspace,files,kind,{'children':children})


def import_export_zip(workspace,data,filename):
    from io import BytesIO
    from zipfile import ZipFile,BadZipFile
    original=import_bytes(workspace,data,filename,'asset')
    files={};children=[];total=0
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries=[entry for entry in archive.infolist() if not entry.is_dir()]
            if len(entries)>ARTIFACT_MAX_FILES:raise ValueError('Export archive exceeds member limit')
            for entry in entries:
                name=entry.filename
                if name=='metadata.json':name='export/metadata.json'
                member_name(name)
                if name in files or (entry.external_attr>>16)&0o170000==0o120000:raise ValueError('Duplicate or linked export member')
                total+=entry.file_size
                if entry.file_size>MAX_UPLOAD_BYTES or total>ARTIFACT_MAX_BYTES:raise ValueError('Export archive exceeds byte limit')
                body=archive.read(entry);files[name]=body
                suffix=Path(name).suffix.lower();kind='dtcg' if suffix=='.json' else 'image' if suffix in {'.png','.jpg','.jpeg','.webp'} else 'asset'
                children.append({'artifact':import_bytes(workspace,body,Path(name).name,kind),'location':name,'kind':kind})
    except BadZipFile as exc:raise ValueError('Figma export upload must be a ZIP archive') from exc
    return import_bundle(workspace,files,'figma-export',{'original':original,'children':children})
