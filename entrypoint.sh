#!/bin/bash

set -e

python manage.py migrate
python manage.py collectstatic --noinput

gunicorn -b unix:/code/cream.sock --log-level=debug cream.wsgi:application
