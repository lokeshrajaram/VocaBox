#!/usr/bin/env python3
import argparse
import os

from vocabox import app
from vocabox.testing import run_self_tests
from vocabox.utils import multiprocessing_available


def main():
    parser = argparse.ArgumentParser(description="Run the VocaBox Flask application.")
    parser.add_argument('--selftest', action='store_true', help='run built-in smoke tests and exit')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', default=5000, type=int)
    parser.add_argument('--debug', action='store_true', help='enable Flask debug/reloader')
    args = parser.parse_args()

    mp_ok = multiprocessing_available()
    env_debug = os.environ.get('VOCA_DEBUG', '').lower() in ('1', 'true', 'yes')
    safe_debug = (args.debug or env_debug) and mp_ok

    run_kwargs = dict(host=args.host, port=args.port)
    if safe_debug:
        run_kwargs.update(dict(debug=True, use_reloader=True, use_debugger=True))
    else:
        run_kwargs.update(dict(debug=False, use_reloader=False, use_debugger=False, use_evalex=False))

    if args.selftest:
        run_self_tests(app)
    else:
        app.run(**run_kwargs)


if __name__ == '__main__':
    main()
