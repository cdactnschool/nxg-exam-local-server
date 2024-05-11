
python manage.py makemigrations
python manage.py migrate

chown -R www-data:www-data /opt/tnschools/
#systemctl reload apache2
/etc/init.d/apache2 restart
