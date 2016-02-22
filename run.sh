#!/bin/sh
CONFIG='dev-config.py'; export CONFIG
PYTHONPATH="$(cd "$(dirname "$0")" && pwd -P)"; export PYTHONPATH

# Uncomment and add the VCAP_SERVICES settings from cf env <your-app>
#VCAP_SERVICES=""; export VCAP_SERVICES

exec bluemix_promocodes/__init__.py
