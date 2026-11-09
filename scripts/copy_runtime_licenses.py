import builtins
import importlib.metadata
from pathlib import Path
import sys

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
builtins.license._Printer__setup()
(out / 'Python-LICENSE.txt').write_text('\n'.join(builtins.license._Printer__lines))
dist = importlib.metadata.distribution('pyinstaller')
for item in dist.files:
    if item.name.upper().startswith(('COPYING', 'LICENSE')):
        source = Path(dist.locate_file(item))
        if source.is_file(): (out / ('PyInstaller-' + item.name)).write_bytes(source.read_bytes())
