#!/usr/bin/env python3
"""Full OpenAPI and JSON Schema checks; install requirements-dev.txt first."""
import json
from pathlib import Path
from openapi_spec_validator import validate
from jsonschema import Draft202012Validator

root = Path(__file__).resolve().parents[1]
spec = json.loads((root/'contracts/openapi.json').read_text())
validate(spec)
from referencing import Registry, Resource
# The base URI resolves local #/components references inside examples.
resource = dict(spec, **{'$schema': 'https://json-schema.org/draft/2020-12/schema'})
registry = Registry().with_resource('urn:mtusi:openapi', Resource.from_contents(resource))
for name, example in json.loads((root/'contracts/examples.json').read_text()).items():
    schema = {'$ref': 'urn:mtusi:openapi#/components/schemas/' + name}
    Draft202012Validator(schema, registry=registry).validate(example)
for path in (root/'contracts').glob('*.schema.json'):
    schema = json.loads(path.read_text())
    Draft202012Validator.check_schema(schema)
    for example in schema.get('examples',[]):
        Draft202012Validator(schema).validate(example)
print('PASS: full OpenAPI 3.1 and JSON Schema validation; application NOT tested.')
