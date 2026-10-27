"""Byte identity and historical execution exceptions are separate evidence."""
from __future__ import annotations
from pathlib import Path, PurePosixPath
from .contracts import ContractError, file_hash, digest

EXECUTION_EXCEPTIONS = ({'run':'seed1001/C1_F1_A1','original_git_sha':'UNRECORDED_LOCAL_SHA',
    'status':'BLOCKED_EXTERNAL','resolved':False,
    'required_evidence':'Immutable original execution log or independently retained execution receipt; later HEAD is insufficient'},)

def contained_path(root, relative):
    p=PurePosixPath(relative)
    if not relative or p.is_absolute() or '..' in p.parts or '\\' in relative or ':' in relative:
        raise ContractError('unsafe manifest path')
    root=Path(root).resolve(); target=(root/relative).resolve()
    if not target.is_relative_to(root): raise ContractError('manifest path escapes source root')
    return target

def source_manifest(root, relatives):
    relatives=tuple(relatives)
    if len(set(relatives))!=len(relatives): raise ContractError('duplicate manifest path')
    files=[{'path':p,'sha256':file_hash(contained_path(root,p))} for p in sorted(relatives)]
    return {'schema_version':1,'scope':'CURRENT_BYTES_NOT_HISTORICAL_EXECUTION_PROOF',
            'files':files,'content_sha256':digest(files)}

def validate_manifest(root, manifest):
    if manifest.get('schema_version')!=1 or digest(manifest['files'])!=manifest.get('content_sha256'):
        raise ContractError('manifest schema/digest mismatch')
    seen=set()
    for item in manifest['files']:
        if item['path'] in seen: raise ContractError('duplicate manifest path')
        seen.add(item['path'])
        if file_hash(contained_path(root,item['path']))!=item['sha256']:
            raise ContractError(f'source hash mismatch: {item["path"]}')
    if not seen: raise ContractError('empty manifest')
    return {'status':'VERIFIED_COMPLETE','scope':'BYTE_IDENTITY_ONLY','files_verified':len(seen),
            'execution_exceptions':list(EXECUTION_EXCEPTIONS)}