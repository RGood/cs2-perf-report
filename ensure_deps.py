"""Install what requirements.txt lists if it is not already installed. Called by the .bat launchers before they start anything.

The check reads installed package metadata only (no pip, no network), so it costs a fraction of a second when everything is present.
pip runs only when a package is missing or older than the minimum version. Exit code 0 = ready, 1 = could not install.
"""
from __future__ import annotations
import os, re, subprocess, sys
from importlib import metadata

HERE = os.path.dirname(os.path.abspath(__file__))
REQ = os.path.join(HERE, 'requirements.txt')


def version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r'\d+', v)[:4])


def unmet() -> list[tuple[str, str]]:
    """Requirement lines that are not satisfied, each with the reason."""
    out = []
    for line in open(REQ, encoding='utf-8'):
        line = line.split('#')[0].strip()
        if not line: continue
        m = re.match(r'^([A-Za-z0-9_.\-]+)\s*(?:>=\s*([0-9][0-9A-Za-z.]*))?', line)
        if m is None: continue
        name, minimum = m.group(1), m.group(2)
        try: have = metadata.version(name)
        except metadata.PackageNotFoundError:
            out.append((line, 'not installed')); continue
        if minimum and version_tuple(have) < version_tuple(minimum): out.append((line, f'installed {have} is older'))
    return out


def main() -> int:
    missing = unmet()
    if not missing: return 0
    print('CS2 Performance Report: installing required Python packages (first run only).')
    for line, why in missing: print(f'  {line}   ({why})')
    r = subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', '-r', REQ])
    still = unmet()
    if r.returncode != 0 or still:
        print('\nCould not install: ' + ', '.join(line for line, _ in still) if still else '\npip reported an error.')
        print(f'Try it by hand:  "{sys.executable}" -m pip install -r "{REQ}"')
        return 1
    print('Packages installed.\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
