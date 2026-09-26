'''Tests for python/scripts/ors_down_cli.py.'''
from unittest.mock import patch

from python.scripts.ors_down_cli import main


class TestMain:
    '''Tests for the ors_down_cli main entry point.'''

    @patch('python.scripts.ors_down_cli.subprocess.run')
    @patch('python.scripts.ors_down_cli._ensure_host_only')
    def test_invokes_docker_compose_down(self, unused_mock_host, mock_run):
        '''Default invocation runs `docker compose down`.'''
        del unused_mock_host
        main([])
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == 'docker'
        assert 'compose' in cmd
        assert 'down' in cmd

    @patch('python.scripts.ors_down_cli.subprocess.run')
    @patch('python.scripts.ors_down_cli._ensure_host_only')
    def test_supplies_ors_state_placeholder_for_compose_parse(self, unused_mock_host, mock_run):
        '''compose -f references ${ORS_STATE:?...}; teardown must set it.'''
        del unused_mock_host
        with patch.dict('python.scripts.ors_down_cli.os.environ', {}, clear=True):
            main([])
        env = mock_run.call_args.kwargs.get('env')
        assert env is not None
        assert env.get('ORS_STATE') == 'unset'
