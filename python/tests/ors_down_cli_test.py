'''Tests for python/scripts/ors_down_cli.py.'''
from unittest.mock import patch

from python.scripts.ors_down_cli import main


class TestMain:
    '''Tests for the ors_down_cli main entry point.'''

    @patch('python.scripts.ors_down_cli.subprocess.run')
    @patch('python.scripts.ors_down_cli.ensure_host_only')
    def test_invokes_docker_compose_down(self, unused_mock_host, mock_run):
        '''Default invocation runs `docker compose down` without -v.'''
        del unused_mock_host
        main([])
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == 'docker'
        assert 'compose' in cmd
        assert 'down' in cmd
        assert '-v' not in cmd        # No volume purge by default.

    @patch('python.scripts.ors_down_cli.subprocess.run')
    @patch('python.scripts.ors_down_cli.ensure_host_only')
    def test_purge_graphs_passes_v_flag(self, unused_mock_host, mock_run):
        '''`--purge-graphs` appends -v so the ors_graphs volume is removed.'''
        del unused_mock_host
        main(['--purge-graphs'])
        cmd = mock_run.call_args.args[0]
        assert '-v' in cmd            # `docker compose down -v` removes volumes.
