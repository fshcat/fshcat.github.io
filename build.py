#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path

def run_command(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    return result.returncode == 0

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Build the site')
    parser.add_argument('--markdown-dir', default='markdown_sources',
                        help='Directory containing markdown files')
    parser.add_argument('--assets-dir',
                        help='Directory containing images')
    parser.add_argument('--clean', action='store_true',
                        help='Clean all generated project directories before building')

    args = parser.parse_args()

    markdown_dir = Path(args.markdown_dir)
    assets_dir = args.assets_dir or str(markdown_dir / 'images')

    if not markdown_dir.exists():
        print(f"Error: Markdown directory '{markdown_dir}' not found")
        return 1

    print("Building site...")

    if args.clean:
        print("Cleaning existing project directories...")
        for item in Path('.').iterdir():
            if item.is_dir() and (item / '.metadata.json').exists():
                import shutil
                shutil.rmtree(item)
                print(f"Removed {item}")

    print("Converting markdown files to HTML...")
    if not run_command([
        sys.executable, 'convert.py',
        str(markdown_dir),
        '--batch',
        '--assets-dir', assets_dir
    ]):
        print("Failed to convert markdown files")
        return 1

    print("Updating main index page...")
    if not run_command([sys.executable, 'update_index.py']):
        print("Failed to update index.html")
        return 1

    print("Build complete.")

    projects = []
    for item in Path('.').iterdir():
        if item.is_dir() and (item / 'index.html').exists() and (item / '.metadata.json').exists():
            projects.append(item.name)

    if projects:
        print(f"Generated {len(projects)} project page(s):")
        for project in sorted(projects):
            print(f"  {project}")

if __name__ == '__main__':
    sys.exit(main())
