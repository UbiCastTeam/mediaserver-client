from pathlib import Path
import subprocess

import pytest


all_scripts = [
    pytest.param(p, id=p.name)
    for p in sorted(Path('examples').iterdir())
    if p.name.endswith('.py') and not p.name.startswith('__')
]


@pytest.mark.parametrize('path', all_scripts)
def test_help(path):
    subprocess.run(['python3', str(path), '--help'], check=True)
