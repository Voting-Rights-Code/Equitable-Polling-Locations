'''Tests for python/scripts/ors_up_cli.py.'''
import os
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from python.scripts.ors_up_cli import (
    HEALTH_POLL_INTERVAL_S,
    HEALTH_POLL_TIMEOUT_S,
    _dir_size_bytes,
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
        assert HEALTH_POLL_TIMEOUT_S == 2700   # 45 minutes

    @patch('python.scripts.ors_up_cli.time.sleep', lambda _: None)
    @patch('python.scripts.ors_up_cli.urllib.request.urlopen')
    def test_invokes_on_iteration_each_poll(self, mock_urlopen):
        '''Each failed poll iteration must invoke the on_iteration callback with elapsed seconds.'''
        mock_response = MagicMock()
        mock_response.getcode.return_value = 503
        mock_urlopen.return_value.__enter__.return_value = mock_response
        calls = []
        poll_health(
            'http://x/health',
            timeout_s=1,
            poll_interval_s=0.1,
            on_iteration=calls.append,
        )
        assert calls, 'Expected on_iteration to fire at least once'
        assert all(isinstance(c, int) for c in calls), \
            'on_iteration argument must be an integer elapsed-seconds count'

    @patch('python.scripts.ors_up_cli.time.sleep', lambda _: None)
    @patch('python.scripts.ors_up_cli.urllib.request.urlopen')
    def test_skips_on_iteration_when_health_passes_immediately(self, mock_urlopen):
        '''A first-poll 200 should NOT invoke the callback.'''
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        calls = []
        assert poll_health(
            'http://x/health',
            timeout_s=10,
            on_iteration=calls.append,
        ) is True
        assert not calls, 'Callback must not fire when no waiting was needed'


class TestDirSizeBytes:
    '''Tests for the ``_dir_size_bytes`` helper.'''

    def test_returns_zero_for_nonexistent_path(self, tmp_path):
        '''A path that does not exist must produce 0 without raising.'''
        assert _dir_size_bytes(str(tmp_path / 'missing')) == 0

    def test_returns_zero_for_empty_dir(self, tmp_path):
        '''An empty directory must report 0 bytes.'''
        assert _dir_size_bytes(str(tmp_path)) == 0

    def test_sums_file_sizes(self, tmp_path):
        '''Top-level file sizes must be summed.'''
        (tmp_path / 'a').write_bytes(b'x' * 1000)
        (tmp_path / 'b').write_bytes(b'y' * 500)
        assert _dir_size_bytes(str(tmp_path)) == 1500

    def test_recurses_into_subdirs(self, tmp_path):
        '''File sizes nested under subdirectories must be summed too.'''
        sub = tmp_path / 'sub'
        sub.mkdir()
        (sub / 'nested').write_bytes(b'z' * 2048)
        assert _dir_size_bytes(str(tmp_path)) == 2048


class TestMainOrchestration:
    '''Tests for the ``main`` orchestration function.'''

    @patch('python.scripts.ors_up_cli.os.makedirs')
    @patch('python.scripts.ors_up_cli.poll_health', return_value=True)
    @patch('python.scripts.ors_up_cli.subprocess.run')
    @patch('python.scripts.ors_up_cli.download_pbf_if_missing',
           return_value='/abs/path/datasets/openrouteservice/georgia-latest.osm.pbf')
    @patch('python.scripts.ors_up_cli._ensure_host_only')
    @pytest.mark.xfail(
        reason='ORS-infra test isolation, owned by #226 (driving-distance-tools worktree): '
               'mocked os.makedirs suppresses log-dir creation, so open() fails when ./logs '
               'is absent in a fresh checkout.',
        strict=False,
    )
    def test_validates_state_then_downloads_then_spawns(
        self, unused_mock_host, mock_download, mock_run, unused_mock_poll, unused_mock_makedirs,
    ):
        '''main(['georgia']) must call download, then docker compose up -d.'''
        del unused_mock_host, unused_mock_poll, unused_mock_makedirs
        main(['georgia'])
        mock_download.assert_called_once_with('georgia')
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == 'docker'
        assert 'compose' in cmd
        assert '-f' in cmd
        assert any('docker-compose.ors.yml' in arg for arg in cmd)
        assert 'up' in cmd
        assert '-d' in cmd

    @patch('python.scripts.ors_up_cli.os.makedirs')
    @patch('python.scripts.ors_up_cli.poll_health', return_value=True)
    @patch('python.scripts.ors_up_cli.subprocess.run')
    @patch('python.scripts.ors_up_cli.download_pbf_if_missing',
           return_value='/abs/path/datasets/openrouteservice/georgia-latest.osm.pbf')
    @patch('python.scripts.ors_up_cli._ensure_host_only')
    @pytest.mark.xfail(
        reason='ORS-infra test isolation, owned by #226 (driving-distance-tools worktree): '
               'mocked os.makedirs suppresses log-dir creation, so open() fails when ./logs '
               'is absent in a fresh checkout.',
        strict=False,
    )
    def test_passes_ors_state_env(
        self, unused_mock_host, unused_mock_download, mock_run, unused_mock_poll, unused_mock_makedirs,
    ):
        '''docker compose up -d must be invoked with ORS_STATE set in the subprocess env.'''
        del unused_mock_host, unused_mock_download, unused_mock_poll, unused_mock_makedirs
        main(['georgia'])
        env = mock_run.call_args.kwargs.get('env')
        assert env is not None
        assert env.get('ORS_STATE') == 'georgia'

    @patch('python.scripts.ors_up_cli.poll_health', return_value=True)
    @patch('python.scripts.ors_up_cli.subprocess.run')
    @patch('python.scripts.ors_up_cli.download_pbf_if_missing',
           return_value='/abs/path/datasets/openrouteservice/georgia-latest.osm.pbf')
    @patch('python.scripts.ors_up_cli._ensure_host_only')
    def test_pre_creates_per_state_graphs_dir(
        self, unused_mock_host, unused_mock_download, unused_mock_run, unused_mock_poll, tmp_path,
    ):
        '''main must mkdir the per-state graphs dir before invoking docker compose.'''
        del unused_mock_host, unused_mock_download, unused_mock_run, unused_mock_poll
        with patch('python.scripts.ors_up_cli.ORS_GRAPHS_DIR', str(tmp_path)):
            main(['georgia', '--logdir', str(tmp_path / 'logs')])
        assert (tmp_path / 'georgia').is_dir()

    @patch('python.scripts.ors_up_cli.os.makedirs')
    @patch('python.scripts.ors_up_cli.poll_health', return_value=False)
    @patch('python.scripts.ors_up_cli.subprocess.run')
    @patch('python.scripts.ors_up_cli.download_pbf_if_missing',
           return_value='/abs/path/datasets/openrouteservice/georgia-latest.osm.pbf')
    @patch('python.scripts.ors_up_cli._ensure_host_only')
    @pytest.mark.xfail(
        reason='ORS-infra test isolation, owned by #226 (driving-distance-tools worktree): '
               'mocked os.makedirs suppresses log-dir creation, so open() fails when ./logs '
               'is absent in a fresh checkout.',
        strict=False,
    )
    def test_exits_nonzero_when_health_times_out(
        self, unused_mock_host, unused_mock_download, mock_run, unused_mock_poll, unused_mock_makedirs,
    ):
        '''A health-poll timeout must surface as a non-zero exit code.'''
        del unused_mock_host, unused_mock_download, unused_mock_poll, unused_mock_makedirs
        with pytest.raises(SystemExit) as exc_info:
            main(['georgia'])
        assert exc_info.value.code != 0
        log_dump_calls = [
            call for call in mock_run.call_args_list
            if 'logs' in call.args[0] and '--tail=50' in call.args[0]
        ]
        assert log_dump_calls, 'Expected a docker compose logs --tail=50 invocation on timeout'

    @patch('python.scripts.ors_up_cli._ensure_host_only')
    def test_rejects_unknown_state_slug(self, unused_mock_host):
        '''An unknown slug must exit non-zero with a clear error.'''
        del unused_mock_host
        with pytest.raises(SystemExit) as exc_info:
            main(['atlantis'])
        assert exc_info.value.code != 0

    @patch('python.scripts.ors_up_cli._ensure_host_only')
    def test_requires_positional_state_arg(self, unused_mock_host):
        '''Missing the state arg must trigger argparse error (exit code 2).'''
        del unused_mock_host
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 2

    @patch('python.scripts.ors_up_cli._ensure_host_only')
    def test_logdir_override_creates_log_file(self, mock_host, tmp_path):
        '''--logdir override should be honored (and produce a log file).'''
        del mock_host
        with patch('python.scripts.ors_up_cli.subprocess.run'), \
             patch('python.scripts.ors_up_cli.download_pbf_if_missing',
                   return_value=os.path.join(str(tmp_path), 'georgia-latest.osm.pbf')), \
             patch('python.scripts.ors_up_cli.poll_health', return_value=True), \
             patch('python.scripts.ors_up_cli.ORS_GRAPHS_DIR', str(tmp_path / 'graphs')):
            main(['georgia', '--logdir', str(tmp_path)])
        assert any(p.name.endswith('_ors_up.log') for p in tmp_path.iterdir())
