#!/bin/bash


cd /opt/tnschools/tnschool-local-server


pip install -r requirements.txt

cd /opt/tnschools/tnschool-local-server

python3 manage.py makemigrations

python3 manage.py migrate

chown -R www-data:www-data /opt/tnschools/

/etc/init.d/apache2 restart