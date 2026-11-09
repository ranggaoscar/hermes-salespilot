"""Exercise accepted sends in an isolated package-only import environment."""

import os
from pathlib import Path
import subprocess
import sys
import textwrap
import tempfile
import unittest


def _check_package_send(tmp_path):
    root = Path(__file__).resolve().parents[1]
    script = textwrap.dedent('''
        import importlib.util
        import json
        from pathlib import Path
        import sys

        root = Path(sys.argv[1]).resolve()
        sys.path[:] = [p for p in sys.path if Path(p or '.').resolve() != root]
        assert 'accounts' not in sys.modules and 'inbox' not in sys.modules
        assert importlib.util.find_spec('accounts') is None
        assert importlib.util.find_spec('inbox') is None
        spec = importlib.util.spec_from_file_location(
            'isolated_salespilot', root / '__init__.py', submodule_search_locations=[str(root)]
        )
        package = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = package
        spec.loader.exec_module(package)
        from isolated_salespilot import commands, mail, plugin_settings, storage, tools

        storage.set_data_dir(Path(sys.argv[2]))
        commands._secrets = lambda: ('', '', '')
        seeded = json.loads(tools.import_customers({'seed_demo': True}))
        lead = next(item['id'] for item in seeded['prospects'] if item['decision'] == 'qualified')
        draft = json.loads(tools.draft_outreach({'lead_id': lead, 'channel': 'email'}))['draft']
        class Settings:
            def get_config(self, key, default):
                return {'smtp_host': 'smtp.example.com', 'from_address': 'nia@example.com'}.get(key, default)
        plugin_settings.bind(Settings())
        calls = []
        def transport(account, username, password, message):
            calls.append(str(message['Message-ID']))
            return 250, False
        mail.set_transport_for_tests(transport)
        class Host:
            def ask_choice(self, question, choices):
                return 'send'
        commands.bind(Host())
        first = json.loads(commands.slash_send(draft['id']))
        assert first['ok'] and first['smtp_accepted'], first
        assert not first['inbox_delivery_proven']
        message_id = first['delivery']['message_id']
        assert message_id and calls == [message_id]
        retry = json.loads(commands.slash_send(draft['id']))
        assert retry['ok'] and retry['reused'], retry
        assert calls == [message_id]
        with storage.unit_of_work() as conn:
            deliveries = conn.execute('SELECT * FROM deliveries').fetchall()
            messages = conn.execute('SELECT * FROM messages').fetchall()
            assert len(deliveries) == len(messages) == 1
            delivery, message = deliveries[0], messages[0]
            assert delivery['message_id'] == message_id and delivery['state'] == 'accepted'
            assert delivery['smtp_code'] == 250 and delivery['draft_id'] == draft['id']
            assert message['message_id'] == message_id and message['direction'] == 'outbound'
            assert message['lead_id'] == lead and message['delivery_state'] == 'accepted'
            assert message['evidence_level'] == 'smtp_accepted'
            events = [row for row in storage.list_events(conn, seeded['business_id']) if row['kind'] == 'message_sent']
            assert len(events) == 1, events
            assert json.loads(events[0]['payload_json'])['message_id'] == message_id
        assert 'accounts' not in sys.modules and 'inbox' not in sys.modules
    ''')
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    result = subprocess.run(
        [sys.executable, '-I', '-c', script, str(root), str(tmp_path)],
        cwd=tmp_path, env=env, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


class PackageSendTests(unittest.TestCase):
    def test_package_send_records_evidence_and_retry_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            _check_package_send(Path(tmp))
