#!/usr/bin/env python3
"""Cross-platform Docker acceptance runner. Deletes only its own temporary container."""
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from client import Client

EVIDENCE = ROOT / 'evidence'
NAME = 'lab1-check-' + uuid.uuid4().hex[:10]
IMAGE = 'mtusi-messenger:lab1'


def main():
    EVIDENCE.mkdir(exist_ok=True)
    with (EVIDENCE / 'docker-verification.txt').open('w', encoding='utf-8') as report:
        def note(text):
            print(text, flush=True)
            report.write(text + '\n')
            report.flush()

        def command(*args, timeout=600):
            note('$ ' + ' '.join(args))
            result = subprocess.run(args, cwd=ROOT, text=True, encoding='utf-8', errors='replace',
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
            note(result.stdout)
            if result.returncode:
                raise RuntimeError('Command failed with exit code ' + str(result.returncode))
            return result.stdout.strip()

        def inspect(field):
            return command('docker', 'inspect', '--format', field, NAME, timeout=15)

        def ready():
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                result = subprocess.run(['docker', 'inspect', '--format', '{{.State.Health.Status}}', NAME],
                                        capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and result.stdout.strip() == 'healthy':
                    note('PASS Docker health status: healthy')
                    return
                time.sleep(0.5)
            raise RuntimeError('Container did not become healthy within 60 seconds')

        created = False
        try:
            command('docker', 'version')
            command('docker', 'build', '-t', IMAGE, '.')
            command('docker', 'run', '-d', '--name', NAME, '--cpus=2', '--memory=512m',
                    '-p', '127.0.0.1::8080', '-e', 'APP_ENV=verification', IMAGE)
            created = True
            binding = json.loads(inspect('{{json .NetworkSettings.Ports}}'))['8080/tcp'][0]
            base = 'http://127.0.0.1:' + binding['HostPort']
            ready()
            uid = command('docker', 'exec', NAME, 'id', '-u')
            if uid == '0' or not uid.isdigit():
                raise RuntimeError('Container must run as a non-root UID')
            note('PASS non-root UID=' + uid)
            command(sys.executable, 'scripts/check_contract.py')
            command(sys.executable, 'tests/smoke.py', '--base-url', base)
            command(sys.executable, 'tests_own/test_api.py', '--base-url', base)
            c = Client(base)
            a, b, e, chat = c.bootstrap()
            marker = 'PRIVATE_MESSAGE_' + uuid.uuid4().hex
            message = c.message(a, chat, marker)['json']
            page = c.call('GET', '/api/v1/chats/' + chat['id'] + '/messages', actor=a, schema='MessagePage')['json']
            if page['items'] != [message]:
                raise RuntimeError('Message not readable before stop')
            note('PASS created message is readable before stop')
            # Keep a request body incomplete to check shutdown of an in-flight request.
            import socket
            from urllib.parse import urlparse
            target = urlparse(base)
            slow = socket.create_connection((target.hostname, target.port), timeout=3)
            slow.sendall(b'POST /api/v1/users HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: 1000\r\n\r\n{')
            time.sleep(0.2)
            started = time.monotonic()
            command('docker', 'stop', '--time', '10', NAME, timeout=15)
            elapsed = time.monotonic() - started
            slow.close()
            exit_code = inspect('{{.State.ExitCode}}')
            if elapsed > 10 or exit_code != '0':
                raise RuntimeError(f'Shutdown failed: {elapsed:.3f}s, exit={exit_code}')
            note(f'PASS SIGTERM with incomplete request: elapsed={elapsed:.3f}s (<10), exit=0')
            import urllib.request
            try:
                urllib.request.urlopen(base + '/health/live', timeout=2)
            except OSError:
                note('PASS stopped process does not accept new requests')
            else:
                raise RuntimeError('Stopped process still serves HTTP')
            logs = command('docker', 'logs', NAME)
            (EVIDENCE / 'docker-server.jsonl').write_text(logs, encoding='utf-8')
            if marker in logs:
                raise RuntimeError('Message text leaked into logs')
            if 'request_id=' not in logs:
                raise RuntimeError('No useful request log found')
            note('PASS useful logs contain request IDs and do not contain message text')
            command('docker', 'start', NAME)
            ready()
            # Docker may assign a new ephemeral host port after restart.
            binding = json.loads(inspect('{{json .NetworkSettings.Ports}}'))['8080/tcp'][0]
            c = Client('http://127.0.0.1:' + binding['HostPort'])
            c.call('GET', '/api/v1/users/me', 401, actor=a)
            new_actor = c.user('after_restart')
            c.call('GET', '/api/v1/chats/' + chat['id'], 404, actor=new_actor)
            note('PASS restart: old user=401; old chat=404 for new user')
            note('PASS all Docker acceptance checks')
        except (OSError, RuntimeError, subprocess.TimeoutExpired, AssertionError) as ex:
            note('FAIL: ' + str(ex))
            return 1
        finally:
            if created:
                subprocess.run(['docker', 'rm', '-f', NAME], capture_output=True, timeout=20)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
