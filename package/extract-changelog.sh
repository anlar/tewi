#! /usr/bin/env bash

sed -n "/^## \[${1:1}\]/,/^## \[/p" CHANGELOG.md | sed '$d'
