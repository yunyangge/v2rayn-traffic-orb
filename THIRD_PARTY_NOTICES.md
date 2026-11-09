# Third-party notices

The application source is MIT licensed. Release archives include a Python runtime and the PyInstaller bootloader, which retain their original licenses.

- **CPython**: Python Software Foundation License Version 2 and bundled historical notices. Full notices: https://docs.python.org/3/license.html
- **PyInstaller bootloader**: GPL-2.0-or-later with the PyInstaller bootloader exception, permitting distributions of the generated application under the application's own terms. https://pyinstaller.org/en/stable/license.html
- **PyInstaller runtime hooks and additional runtime modules**: Apache-2.0. The full Apache-2.0 text is included in `licenses/PyInstaller-COPYING.txt` along with PyInstaller's other terms.
- Python standard-library native extensions may include **OpenSSL / LibreSSL**, **zlib**, **libffi**, **bzip2**, **liblzma** depending on the build environment; their license notices are retained with the Python distribution and build dependency notices. Source projects: https://www.openssl.org/source/license.html, https://www.libressl.org/, https://zlib.net/zlib_license.html, https://github.com/libffi/libffi/blob/master/LICENSE, https://sourceware.org/bzip2/, https://tukaani.org/xz/

The build process copies CPython's full `LICENSE.txt` into the release when available. System Apple frameworks are dynamically linked and are not redistributed as project source. v2rayN and Xray themselves are **not** bundled.

See [licensing scope](docs/licensing.md) for the separation between Traffic Orb's original code, separately installed v2rayN/Xray applications, and the bundled Python/PyInstaller runtime.
