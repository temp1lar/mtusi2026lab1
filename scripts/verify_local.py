#!/usr/bin/env python3
"""Build and test a separate local process. Not a substitute for Docker evidence."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from client import Client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dotnet', default='dotnet')
    args = parser.parse_args()
    evidence = ROOT / 'evidence'
    evidence.mkdir(exist_ok=True)
    with (evidence / 'local-verification.txt').open('w', encoding='utf-8') as report:
        def note(text):
            print(text, flush=True)
            report.write(text + '\n')
            report.flush()
        def run(*command):
            note('$ ' + ' '.join(command))
            result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            note(result.stdout)
            if result.returncode:
                raise RuntimeError('Command failed: ' + str(result.returncode))
        run(args.dotnet, 'restore', 'src/Messenger', '--locked-mode')
        run(args.dotnet, 'build', 'src/Messenger', '-c', 'Release', '--no-restore')
        # Let OS choose an unused port, avoiding a user's existing API on 8080.
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        env = dict(os.environ, APP_HOST='127.0.0.1', APP_PORT=str(port), NO_PROXY='127.0.0.1,localhost', no_proxy='127.0.0.1,localhost')
        os.environ.update(NO_PROXY=env['NO_PROXY'], no_proxy=env['no_proxy'])
        dll = str(ROOT / 'src/Messenger/bin/Release/net10.0/Messenger.dll')
        log_path = evidence / 'local-server.jsonl'
        with log_path.open('w', encoding='utf-8') as logs:
            def start():
                process = subprocess.Popen([args.dotnet, dll], cwd=ROOT, env=env, stdout=logs, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError('Server exited before readiness; see local-server.jsonl')
                    try:
                        with urllib.request.urlopen(base + '/health/ready', timeout=1) as r:
                            if r.status == 200:
                                return process
                    except OSError:
                        time.sleep(0.1)
                process.kill()
                process.wait()
                raise RuntimeError('Server readiness timed out')
            process = start()
            try:
                run(sys.executable, 'scripts/check_contract.py')
                run(sys.executable, 'tests/smoke.py', '--base-url', base)
                run(sys.executable, 'tests_own/test_api.py', '--base-url', base)
                probe = subprocess.run([args.dotnet, dll, '--healthcheck'], env=env, timeout=4)
                if probe.returncode:
                    raise RuntimeError('Built-in health probe failed')
                note('PASS built-in --healthcheck')
                c = Client(base)
                a, b, e, chat = c.bootstrap()
                c.message(a, chat, 'PRIVATE_LOG_SENTINEL')
                slow = socket.create_connection(('127.0.0.1', port), timeout=2)
                slow.sendall(b'POST /api/v1/users HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: 1000\r\n\r\n{')
                time.sleep(0.2)
                started = time.monotonic()
                process.terminate()
                process.wait(timeout=10)
                elapsed = time.monotonic() - started
                slow.close()
                if process.returncode != 0 or elapsed >= 10:
                    raise RuntimeError(f'Shutdown: exit={process.returncode}, time={elapsed}')
                note(f'PASS local SIGTERM with incomplete request: {elapsed:.3f}s, exit=0')
                try:
                    urllib.request.urlopen(base + '/health/live', timeout=1)
                except OSError:
                    note('PASS stopped process rejects new connections')
                else:
                    raise RuntimeError('Stopped process still serves HTTP')
                process = start()
                c.call('GET', '/api/v1/users/me', 401, actor=a)
                new_actor = c.user('restart')
                c.call('GET', '/api/v1/chats/' + chat['id'], 404, actor=new_actor)
                note('PASS local restart clears users and chats')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
        logs = log_path.read_text(encoding='utf-8')
        if 'PRIVATE_LOG_SENTINEL' in logs:
            raise RuntimeError('Message leaked into logs')
        note('PASS no message sentinel in logs')
        note('PASS local verification; Docker still requires separate verification')

if __name__ == '__main__':
    main()
