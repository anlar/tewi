#! /usr/bin/env bash

# SPDX-FileCopyrightText: 2025 Anton Larionov
# SPDX-License-Identifier: GPL-3.0-or-later

sed -n "/^## \[${1:1}\]/,/^## \[/p" CHANGELOG.md | sed '$d'
