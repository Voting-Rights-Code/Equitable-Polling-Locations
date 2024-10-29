'''
coverage run -m pytest tests\test_model_run_cli_bergen_nj.py
coverage report -m
'''

import model_run_cli

import argparse

parser = argparse.ArgumentParser(prog='cli')
parser.add_argument('configs', nargs='+', help='One or more yaml configuration files to run.')
parser.add_argument('-c', '--concurrent', default=1, type=int, help='')
parser.add_argument('-v', '--verbose', action='count', default=2, help='Print extra logging.')
parser.add_argument('-l', '--logdir', default="logs", type=str, help='The directory to output log files to')

what = parser.parse_args(["./Bergen_NJ/Bergen_NJ.yaml"])

def test_main():
    MAIN = model_run_cli.main(what)
    assert MAIN != ""
