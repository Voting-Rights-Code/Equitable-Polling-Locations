'''Tests for run.py's generate_driving_distances_cli host-side orchestration.'''
# pylint: disable=protected-access
# Rationale: _ors_is_healthy is a module-level helper in run.py (not a class
# member). Pylint W0212 fires because it is accessed via ``run_module._name``;
# the warning is a false-positive here.
import subprocess
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

import run as run_module


class TestOrsIsHealthy:
    '''Tests for the ``_ors_is_healthy`` helper.'''

    @patch('run.urllib.request.urlopen')
    def test_returns_true_on_200(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        assert run_module._ors_is_healthy() is True

    @patch('run.urllib.request.urlopen', side_effect=urllib.error.URLError('refused'))
    def test_returns_false_on_url_error(self, unused_mock_urlopen):
        del unused_mock_urlopen
        assert run_module._ors_is_healthy() is False

    @patch('run.urllib.request.urlopen')
    def test_returns_false_on_non_200(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.getcode.return_value = 503
        mock_urlopen.return_value.__enter__.return_value = mock_response
        assert run_module._ors_is_healthy() is False


class TestGenerateDrivingDistancesOrchestration:
    '''Tests for the host-side special-case in ``main``.'''

    @patch('run.IN_CONTAINER', False)
    @patch('run._ors_is_healthy', return_value=False)
    @patch('run.subprocess.run')
    @patch('run.run_command')
    def test_invokes_ors_up_then_matrix_then_ors_down(
            self, mock_run_command, mock_subprocess_run, unused_mock_healthy):
        '''Default path: bring ORS up, run the matrix, then bring ORS down.'''
        del unused_mock_healthy
        with patch('sys.argv', ['run.py', 'generate_driving_distances_cli',
                                '--testing', '-l', 'cfg.yaml']):
            run_module.main()
        ors_up_calls = [
            c for c in mock_subprocess_run.call_args_list
            if any('ors_up_cli.py' in str(a) for a in c.args[0])
        ]
        ors_down_calls = [
            c for c in mock_subprocess_run.call_args_list
            if any('ors_down_cli.py' in str(a) for a in c.args[0])
        ]
        assert len(ors_up_calls) == 1
        assert len(ors_down_calls) == 1
        # Two run_command calls expected: buffer-prep then matrix.
        assert mock_run_command.call_count == 2
        all_run_command_calls = mock_run_command.call_args_list
        matrix_calls = [
            c for c in all_run_command_calls
            if 'generate_driving_distances_cli' in ' '.join(c.args[0])
        ]
        assert len(matrix_calls) == 1
        matrix_argv = matrix_calls[0].args[0]
        assert matrix_argv[:3] == ['python', '-m',
                                   'python.scripts.generate_driving_distances_cli']
        assert '--testing' in matrix_argv, (
            'The orchestrator must forward --testing so the synthetic testing '
            'config (whose location is underivable) works end-to-end.'
        )
        assert '-l' in matrix_argv
        assert 'cfg.yaml' in matrix_argv

    @patch('run.IN_CONTAINER', False)
    @patch('run._ors_is_healthy', return_value=False)
    @patch('run.subprocess.run')
    @patch('run.run_command')
    def test_skips_ors_down_when_keep_ors_running_flag_set(
            self, mock_run_command, mock_subprocess_run, unused_mock_healthy):
        '''--keep-ors-running should leave ORS up after the matrix completes.'''
        del unused_mock_healthy, mock_run_command
        with patch('sys.argv', ['run.py', 'generate_driving_distances_cli',
                                '--testing', '-l', 'cfg.yaml',
                                '--keep-ors-running']):
            run_module.main()
        ors_down_calls = [
            c for c in mock_subprocess_run.call_args_list
            if any('ors_down_cli.py' in str(a) for a in c.args[0])
        ]
        assert ors_down_calls == []

    @patch('run.IN_CONTAINER', False)
    @patch('run._ors_is_healthy', return_value=True)
    @patch('run.subprocess.run')
    @patch('run.run_command')
    def test_skips_ors_down_when_ors_was_already_up(
            self, mock_run_command, mock_subprocess_run, unused_mock_healthy):
        '''If ORS was already running, the orchestration must not tear it down.'''
        del unused_mock_healthy, mock_run_command
        with patch('sys.argv', ['run.py', 'generate_driving_distances_cli',
                                '--testing', '-l', 'cfg.yaml']):
            run_module.main()
        ors_down_calls = [
            c for c in mock_subprocess_run.call_args_list
            if any('ors_down_cli.py' in str(a) for a in c.args[0])
        ]
        assert ors_down_calls == []

    @patch('run.IN_CONTAINER', False)
    @patch('run._ors_is_healthy', return_value=False)
    @patch('run.subprocess.run')
    @patch('run.run_command')
    def test_still_tears_down_when_matrix_fails(
            self, mock_run_command, mock_subprocess_run, unused_mock_healthy):
        '''A SystemExit from the matrix step must still trigger ors_down cleanup.'''
        del unused_mock_healthy

        def fail_on_matrix(cmd, **_kwargs):
            if 'generate_driving_distances_cli' in ' '.join(cmd):
                raise SystemExit(1)

        mock_run_command.side_effect = fail_on_matrix
        with patch('sys.argv', ['run.py', 'generate_driving_distances_cli',
                                '--testing', '-l', 'cfg.yaml']):
            with pytest.raises(SystemExit):
                run_module.main()
        ors_down_calls = [
            c for c in mock_subprocess_run.call_args_list
            if any('ors_down_cli.py' in str(a) for a in c.args[0])
        ]
        assert len(ors_down_calls) == 1

    @patch('run.IN_CONTAINER', False)
    @patch('run._ors_is_healthy', return_value=False)
    @patch('run.subprocess.run')
    @patch('run.run_command')
    def test_still_tears_down_when_ors_up_fails(
            self, mock_run_command, mock_subprocess_run, unused_mock_healthy):
        '''An ors_up_cli failure must still trigger ors_down cleanup (#223).'''
        del unused_mock_healthy, mock_run_command

        def fake_subprocess_run(cmd, *args, **kwargs):
            del args, kwargs
            if any('ors_up_cli.py' in str(a) for a in cmd):
                raise subprocess.CalledProcessError(1, cmd)
            return MagicMock(returncode=0)

        mock_subprocess_run.side_effect = fake_subprocess_run
        with patch('sys.argv', ['run.py', 'generate_driving_distances_cli',
                                '--testing', '-l', 'cfg.yaml']):
            with pytest.raises(SystemExit):
                run_module.main()
        ors_down_calls = [
            c for c in mock_subprocess_run.call_args_list
            if any('ors_down_cli.py' in str(a) for a in c.args[0])
        ]
        assert len(ors_down_calls) == 1, (
            'Expected ors_down_cli to fire even when ors_up_cli failed; '
            'this regression test guards #223 fix.'
        )

    @patch('run.IN_CONTAINER', True)
    @patch('run.subprocess.run')
    @patch('run.run_command')
    def test_in_container_falls_through_to_normal_wrapper(
            self, mock_run_command, mock_subprocess_run):
        '''Inside the container, host-side orchestration is skipped.'''
        del mock_subprocess_run
        with patch('sys.argv', ['run.py', 'generate_driving_distances_cli',
                                '--testing', '-l', 'cfg.yaml']):
            run_module.main()
        # run_command should have been invoked exactly once with the normal
        # python -m wrapper form (no ORS lifecycle subprocesses).
        assert mock_run_command.call_count == 1

    @patch('run.IN_CONTAINER', False)
    @patch('run._ors_is_healthy', return_value=False)
    @patch('run.subprocess.run')
    @patch('run.run_command')
    def test_derives_state_from_config_when_orchestrating(
            self, mock_run_command, mock_subprocess_run, unused_mock_healthy, tmp_path):
        '''No --testing on argv -> orchestrator derives slug from config.location.

        Verifies the derived slug reaches the ors_up_cli subprocess. The
        in-container matrix step gets nothing forwarded — it re-derives
        the same state itself from the same -l config.
        '''
        del unused_mock_healthy
        cfg = tmp_path / 'cfg.yaml'
        cfg.write_text('config_set: prod\nlocation: Gwinnett_County_GA\n')
        with patch('sys.argv', ['run.py', 'generate_driving_distances_cli',
                                '-l', str(cfg)]):
            run_module.main()
        ors_up_calls = [
            c for c in mock_subprocess_run.call_args_list
            if any('ors_up_cli.py' in str(a) for a in c.args[0])
        ]
        assert len(ors_up_calls) == 1, 'ors_up_cli should be invoked exactly once'
        ors_up_argv = ors_up_calls[0].args[0]
        assert 'georgia' in ors_up_argv, (
            f'Expected derived state "georgia" passed to ors_up_cli; got argv {ors_up_argv}'
        )
        # Two run_command calls expected: buffer-prep then matrix.
        assert mock_run_command.call_count == 2, 'buffer-prep and matrix steps should fire'
        matrix_calls = [
            c for c in mock_run_command.call_args_list
            if 'generate_driving_distances_cli' in ' '.join(c.args[0])
        ]
        assert len(matrix_calls) == 1, 'matrix step should fire exactly once'
        matrix_argv = matrix_calls[0].args[0]
        assert '--testing' not in matrix_argv, (
            f'A normal derived run should forward no state flag — the container '
            f're-derives from the same -l config instead; got argv {matrix_argv}'
        )

    @patch('run.IN_CONTAINER', False)
    @patch('run._ors_is_healthy', return_value=False)
    @patch('run.subprocess.run')
    @patch('run.run_command')
    def test_errors_before_docker_when_state_not_derivable(
            self, mock_run_command, mock_subprocess_run, unused_mock_healthy, tmp_path):
        '''No --state, location='testing' -> exit 2 before any docker activity.'''
        del unused_mock_healthy, mock_run_command
        cfg = tmp_path / 'cfg.yaml'
        cfg.write_text('config_set: testing\nlocation: testing\n')
        with patch('sys.argv', ['run.py', 'generate_driving_distances_cli',
                                '-l', str(cfg)]):
            with pytest.raises(SystemExit) as exc_info:
                run_module.main()
        assert exc_info.value.code == 2
        assert mock_subprocess_run.call_count == 0, (
            'No subprocess (docker) calls should fire when state derivation fails'
        )
