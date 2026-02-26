#!/usr/bin/env bash
set -e

VERSION="$1"
if [ -z "$VERSION" ]; then
    echo "Verwendung: $0 <version>"
    exit 1
fi

echo "__version__ = \"$VERSION\"" > src/version.py

git add src/version.py
git commit -m "Bump version to $VERSION"
git tag "v$VERSION"
git push
git push --tags
