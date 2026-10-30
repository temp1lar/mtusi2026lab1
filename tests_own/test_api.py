#!/usr/bin/env python3
"""Own black-box acceptance tests. Public tests/contracts stay unchanged."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import threading
import time
import unittest
import uuid
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from client import Client

BASE = 'http://localhost:8080'

class Acceptance(unittest.TestCase):
    def setUp(self):
        self.c = Client(BASE)
        self.a, self.b, self.e, self.chat = self.c.bootstrap()
        self.path = '/api/v1/chats/' + self.chat['id']

    def error(self, method, path, status, code, **kwargs):
        response = self.c.call(method, path, status, **kwargs)
        self.assertEqual(response['json']['error']['code'], code)

    def collect(self, path, actor, schema, limit=2):
        items, cursors = [], set()
        cursor = None
        while True:
            suffix = '?limit=' + str(limit) + ('&cursor=' + quote(cursor, safe='') if cursor else '')
            page = self.c.call('GET', path + suffix, actor=actor, schema=schema)['json']
            items.extend(page['items'])
            cursor = page['next_cursor']
            if cursor is None:
                return items
            self.assertNotIn(cursor, cursors)
            cursors.add(cursor)
            self.assertLess(len(cursors), 200)

    def test_malformed_json_and_strict_fields(self):
        for raw in [b'{', b'null', b'[]', b'{"text":42}', b'{"text":null}', b'{}',
                    b'{"text":"a","sender_id":"fake"}', b'{"Text":"a"}',
                    b'{"text":"a","text":"b"}', b'{"text":"\\ud800"}', b'{"text":"\xff"}']:
            with self.subTest(raw=raw):
                self.error('POST', self.path + '/messages', 400, 'invalid_request', actor=self.a,
                           raw=raw, headers={'Content-Type': 'application/json'})
        self.error('POST', self.path + '/messages', 415, 'unsupported_media_type', actor=self.a,
                   raw=b'hello', headers={'Content-Type': 'text/plain'})

    def test_private_chat_and_authentication_order(self):
        for suffix in ['', '/messages', '/messages?limit=0']:
            self.error('GET', self.path + suffix, 404, 'not_found', actor=self.e)
        self.error('POST', self.path + '/messages', 404, 'not_found', actor=self.e, body={'text': ''})
        self.error('GET', '/api/v1/chats/not-a-uuid/messages?limit=0', 401, 'unauthorized')
        for value in [str(uuid.uuid4()), 'bad']:
            self.error('GET', '/api/v1/users/me', 401, 'unauthorized', headers={'X-User-Id': value})
        self.assertEqual(self.collect('/api/v1/chats', self.e, 'ChatPage'), [])

    def test_empty_and_unicode_messages(self):
        for text in ['', ' \t\r\n', '\u2003', '😀' * 4001]:
            self.error('POST', self.path + '/messages', 400, 'invalid_request', actor=self.a, body={'text': text})
        for text in ['Привет, 汉语 😀', '😀' * 4000]:
            message = self.c.message(self.a, self.chat, text)['json']
            self.assertEqual(message['text'], text)
            self.assertEqual(message['sender_id'], self.a['id'])

    def test_duplicate_username(self):
        self.error('POST', '/api/v1/users', 409, 'conflict', body=self.a['registration'])
        body = {'username': 'race_' + uuid.uuid4().hex[:16], 'display_name': 'Race'}
        barrier = threading.Barrier(10)
        def register(_):
            c = Client(BASE)
            barrier.wait(timeout=10)
            return c.call('POST', '/api/v1/users', [201, 409], body=body)['status']
        with ThreadPoolExecutor(max_workers=10) as pool:
            statuses = list(pool.map(register, range(10)))
        self.assertEqual(statuses.count(201), 1)
        self.assertEqual(statuses.count(409), 9)

    def test_user_validation(self):
        for body in [{'username': 'UPPER', 'display_name': 'a'}, {'username': 'ab', 'display_name': 'a'},
                     {'username': 'abc\n', 'display_name': 'a'}, {'username': 'abc', 'display_name': ' '},
                     {'username': 'abc', 'display_name': '😀' * 101},
                     {'username': 'abc', 'display_name': 'a', 'password': 'not-lab1'}]:
            self.error('POST', '/api/v1/users', 400, 'invalid_request', body=body)
        self.c.call('POST', '/api/v1/users', 201, schema='User',
                    body={'username': 'emoji_' + uuid.uuid4().hex[:16], 'display_name': '😀' * 100})

    def test_chat_atomic_validation(self):
        for members in [[self.a['id'], self.a['id']], [self.b['id']], [self.a['id'], str(uuid.uuid4())],
                        [], ['bad'], None, [None]]:
            self.error('POST', '/api/v1/chats', 400, 'invalid_request', actor=self.a,
                       body={'title': 'invalid', 'member_ids': members})
        self.assertEqual(len(self.collect('/api/v1/chats', self.a, 'ChatPage')), 1)

    def test_pagination_and_cursor_scope(self):
        sent = [self.c.message(self.a, self.chat, str(n))['json'] for n in range(7)]
        self.assertEqual(self.collect(self.path + '/messages', self.b, 'MessagePage'), sent)
        other = self.c.call('POST', '/api/v1/chats', 201, actor=self.a, schema='Chat',
                            body={'title': 'Other', 'member_ids': [self.a['id']]})['json']
        page = self.c.call('GET', self.path + '/messages?limit=1', actor=self.a, schema='MessagePage')['json']
        cursor = quote(page['next_cursor'], safe='')
        self.error('GET', '/api/v1/chats/' + other['id'] + '/messages?cursor=' + cursor,
                   400, 'invalid_request', actor=self.a)
        # Changing page size is legal; new insertions after the cursor remain visible.
        eighth = self.c.message(self.a, self.chat, '7')['json']
        rest = self.c.call('GET', self.path + '/messages?limit=100&cursor=' + cursor,
                           actor=self.a, schema='MessagePage')['json']
        self.assertEqual(rest['items'], sent[1:] + [eighth])
        self.assertIsNone(rest['next_cursor'])
        for _ in range(4):
            self.c.call('POST', '/api/v1/chats', 201, actor=self.a,
                        body={'title': 'page', 'member_ids': [self.a['id']]})
        chats = self.collect('/api/v1/chats', self.a, 'ChatPage')
        self.assertEqual(len(chats), 6)
        self.assertEqual(len({c['id'] for c in chats}), 6)
        self.assertEqual(chats, sorted(chats, key=lambda c: (c['created_at'], c['id'])))

    def test_invalid_query(self):
        for query in ['limit=0', 'limit=101', 'limit=-1', 'limit=1.5', 'limit=x', 'limit=',
                      'limit=1&limit=2', 'cursor=', 'cursor=broken', 'cursor=a&cursor=b']:
            self.error('GET', self.path + '/messages?' + query, 400, 'invalid_request', actor=self.a)
        self.error('GET', '/api/v1/chats/bad', 400, 'invalid_request', actor=self.a)

    def test_100_messages_from_10_clients(self):
        actors = [self.c.user('worker') for _ in range(10)]
        chat = self.c.call('POST', '/api/v1/chats', 201, actor=actors[0], schema='Chat',
                           body={'title': 'Race test', 'member_ids': [a['id'] for a in actors]})['json']
        barrier = threading.Barrier(10)
        def worker(index):
            client = Client(BASE)
            barrier.wait(timeout=10)
            return [client.message(actors[index], chat, f'worker={index};item={n}')['json'] for n in range(10)]
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=10) as pool:
            batches = list(pool.map(worker, range(10)))
        sent = [item for batch in batches for item in batch]
        received = self.collect('/api/v1/chats/' + chat['id'] + '/messages', actors[0], 'MessagePage', limit=13)
        self.assertEqual(len(received), 100)
        self.assertEqual(len({m['id'] for m in received}), 100)
        self.assertEqual({m['id']: m for m in received}, {m['id']: m for m in sent})
        print(f'\nRACE PASS: clients=10 sent=100 stored=100 unique=100 elapsed={time.monotonic()-started:.3f}s', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default=BASE)
    args, rest = parser.parse_known_args()
    BASE = args.base_url
    unittest.main(argv=[sys.argv[0]] + rest, verbosity=2)
