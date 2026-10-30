#!/usr/bin/env python3
"""Offline structural checks; full schema validation is a separate target."""
import ast
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def main():
    lab = json.loads((ROOT/'lab.json').read_text())['number']
    spec = json.loads((ROOT/'contracts/openapi.json').read_text())
    assert spec['openapi']=='3.1.0'
    assert spec['info']['version']=='1.%d.0'%lab
    operation_ids = set()
    def walk(value):
        if isinstance(value,dict):
            if '$ref' in value:
                pointer = value['$ref']
                assert pointer.startswith('#/'), 'unexpected external reference'
                target = spec
                for part in pointer[2:].split('/'):
                    target = target[part.replace('~1','/').replace('~0','~')]
            for v in value.values():
                walk(v)
        elif isinstance(value,list):
            for v in value:
                walk(v)
    walk(spec)
    for route,methods in spec['paths'].items():
        placeholders = set(re.findall(r'\{([^}]+)\}',route))
        for method,op in methods.items():
            assert op['operationId'] not in operation_ids, 'duplicate operationId'
            operation_ids.add(op['operationId'])
            params = {p['name'] for p in op.get('parameters',[]) if p['in']=='path' and p.get('required')}
            assert placeholders==params, 'path parameter mismatch: '+route
            for response in op['responses'].values():
                assert 'X-Request-Id' in response['headers']
                if lab>=3:
                    assert 'X-Instance-Id' in response['headers']
    assert ('/api/v1/auth/sessions' in spec['paths']) == (lab>=2)
    assert ('/api/v1/attachments/{attachment_id}' in spec['paths']) == (lab>=4)
    for file in list((ROOT/'tests').glob('*.py'))+list((ROOT/'scripts').glob('*.py')):
        ast.parse(file.read_text(),filename=str(file))
    for file in ROOT.rglob('*.json'):
        if any(part in {'.git','.venv','node_modules','vendor','output'} for part in file.parts):
            continue
        json.loads(file.read_text())
    for required in ('README.md','COURSE.md','CONTRIBUTING.md','REPORT.md','contracts/README.md','tests/smoke.py','tests/README.md'):
        assert (ROOT/required).is_file(), 'missing '+required
    print('PASS: offline skeleton structure, local refs and Python syntax; application NOT tested.')

if __name__=='__main__':
    main()
