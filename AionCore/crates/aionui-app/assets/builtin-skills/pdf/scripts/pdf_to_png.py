#!/usr/bin/env python3
"""Render PDF pages to PNG using the bundled Poppler runtime."""
import argparse
import os
import subprocess
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_pdf')
    parser.add_argument('output_dir')
    parser.add_argument('--dpi', type=int, default=200)
    parser.add_argument('--first-page', type=int)
    parser.add_argument('--last-page', type=int)
    args = parser.parse_args()
    if args.dpi <= 0:
        raise SystemExit('--dpi must be positive')
    source = Path(args.input_pdf)
    if not source.is_file():
        raise SystemExit('input PDF does not exist: %s' % source)
    runtime = os.environ.get('AIONUI_PDF_RUNTIME', '')
    poppler = os.environ.get('AIONUI_PDF_POPPLER') or (str(Path(runtime) / 'poppler') if runtime else '')
    exe = Path(poppler) / ('pdftoppm.exe' if os.name == 'nt' else 'pdftoppm')
    if not exe.is_file():
        raise SystemExit('pdftoppm not found: %s' % exe)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    command = [str(exe), '-png', '-r', str(args.dpi)]
    if args.first_page is not None: command += ['-f', str(args.first_page)]
    if args.last_page is not None: command += ['-l', str(args.last_page)]
    command += [str(source), str(output / 'page')]
    subprocess.check_call(command)

if __name__ == '__main__':
    main()
