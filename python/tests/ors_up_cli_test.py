'''Tests for python/scripts/ors_up_cli.py.'''
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from python.scripts.ors_up_cli import (
    HEALTH_POLL_INTERVAL_S,
    HEALTH_POLL_TIMEOUT_S,
    main,
    poll_health,
)


class TestPollHealth:
    '''Tests for the ``poll_health`` helper.'''

    @patch('python.scripts.ors_up_cli.time.sleep', lambda _: None)
    @patch('python.scripts.ors_up_cli.urllib.request.urlopen')
    def test_returns_true_when_health_ok(self, mock_urlopen):
        '''A single 200 response should short-circuit to True.'''
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        assert poll_health('http://x/health', timeout_s=10) is True

    @patch('python.scripts.ors_up_cli.time.sleep', lambda _: None)
    @patch('python.scripts.ors_up_cli.urllib.request.urlopen')
    def test_returns_false_after_timeout(self, mock_urlopen):
        '''Persistent non-200 responses must eventually return False.'''
        mock_response = MagicMock()
        mock_response.getcode.return_value = 503
        mock_urlopen.return_value.__enter__.return_value = mock_response
        assert poll_health(
            'http://x/health',
            timeout_s=1,
            poll_interval_s=0.1,
        ) is False

    @patch('python.scripts.ors_up_cli.time.sleep', lambda _: None)
    @patch(
        'python.scripts.ors_up_cli.urllib.request.urlopen',
        side_effect=urllib.error.URLError('refused'),
    )
    def test_treats_connection_error_as_not_ready(self, unused_mock_urlopen):
        '''A raised URLError must be treated as "not ready yet".'''
        del unused_mock_urlopen
        assert poll_health(
            'http://x/health',
            timeout_s=1,
            poll_interval_s=0.1,
        ) is False

    def test_default_constants_are_sane(self):
        '''Default constants should match the documented values.'''
        assert HEALTH_POLL_INTERVAL_S == 10
        assert HEALTH_POLL_TIMEOUT_S == 2700   # 45 minutes (state-sized graphs can take 20-30 min)


class TestMainOrchestration:
    '''Tests for the ``main`` orchestration function.'''

    @patch('python.scripts.ors_up_cli.poll_health', return_value=True)
    @patch('python.scripts.ors_up_cli.subprocess.run')
    @patch('python.scripts.ors_up_cli._ensure_host_only')
    def test_invokes_docker_compose_up(self, unused_mock_host, mock_run, unused_mock_poll):
        '''``main`` must shell out to ``docker compose -f <file> up -d``.'''
        del unused_mock_host, unused_mock_poll
        main([])
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == 'docker'
        assert 'compose' in cmd
        assert '-f' in cmd
        assert any('docker-compose.ors.yml' in arg for arg in cmd)
        assert 'up' in cmd
        assert '-d' in cmd

    @patch('python.scripts.ors_up_cli.poll_health', return_value=False)
    @patch('python.scripts.ors_up_cli.subprocess.run')
    @patch('python.scripts.ors_up_cli._ensure_host_only')
    def test_exits_nonzero_when_health_times_out(
        self, unused_mock_host, mock_run, unused_mock_poll,
    ):
        '''A health-poll timeout must surface as a non-zero exit code.'''
        del unused_mock_host, unused_mock_poll
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code != 0
        log_dump_calls = [
            call for call in mock_run.call_args_list
            if 'logs' in call.args[0] and '--tail=50' in call.args[0]
        ]
        assert log_dump_calls, 'Expected a docker compose logs --tail=50 invocation on timeout'
