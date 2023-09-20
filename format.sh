#!/bin/bash

autoflake --remove-all-unused-imports --ignore-init-module-imports -i ./**/*.py
isort .
black .
