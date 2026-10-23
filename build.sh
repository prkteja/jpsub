#!/bin/bash
# Build the single-file binary and a release tarball in dist/.
set -euo pipefail
cd "$(dirname "$0")"

[ -d .venv ] || uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-build.txt

.venv/bin/pyinstaller --noconfirm --clean --log-level WARN \
  --distpath dist --workpath build packaging/jpsub.spec

version=$(.venv/bin/python -c 'import jpsub; print(jpsub.__version__)')
name="jpsub-$version-linux-$(uname -m)"
rm -rf "dist/$name"
mkdir -p "dist/$name"
cp dist/jpsub install.sh README.md LICENSE THIRD_PARTY_NOTICES.md "dist/$name/"
tar -C dist -czf "dist/$name.tar.gz" "$name"
rm -rf "dist/$name"
(cd dist && sha256sum "$name.tar.gz" > "$name.tar.gz.sha256")

echo
echo "Binary:  dist/jpsub"
echo "Release: dist/$name.tar.gz"
