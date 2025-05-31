#! /usr/bin/env sh

sed -n "/^## \[$1\]/,/^## \[/p" CHANGELOG.md | sed '$d'
