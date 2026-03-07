#!/usr/bin/env bash
ruff format && ruff check &&
mypy --strict --strict --strict main.py