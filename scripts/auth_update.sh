#!/bin/sh

. ./scripts/load_azd_env.sh

. ./scripts/load_python_env.sh

.venv/bin/python ./scripts/auth_update.py

. ./scripts/unload_azd_env.sh
