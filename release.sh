#!/usr/bin/env bash
set -e

VERSION="$1"
MSG="$2"

if [ -z "$VERSION" ]; then
    echo "Verwendung: $0 <version> [\"commit message\"]"
    exit 1
fi

# Ausstehende Änderungen committen (außer version.py)
if ! git diff --quiet || ! git diff --cached --quiet; then
    if [ -z "$MSG" ]; then
        echo "Fehler: Es gibt uncommittete Änderungen, aber keine Commit-Message angegeben."
        echo "Verwendung: $0 <version> \"<beschreibung der änderungen>\""
        exit 1
    fi
    git add -A
    git reset src/version.py 2>/dev/null || true
    git commit -m "$MSG"
fi

# Version bumpen und taggen
echo "__version__ = \"$VERSION\"" > src/version.py
git add src/version.py
git commit -m "Bump version to $VERSION"
git tag "v$VERSION"
git push
git push --tags
