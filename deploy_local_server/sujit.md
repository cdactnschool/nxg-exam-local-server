http://dvcs.chennai.cdac.in/secure_exam_software/nsg-exam-local-server.git









https://cdacschoolgituser-at-840620226347:T8ixzBq2otdjxRqc4F6zm0CX9dFhnGlhDay78H3vuAc%3D@git-codecommit.ap-south-1.amazonaws.com/v1/repos/CDACSchoolRepo




git clone http://cdactnschool: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@github.com/cdactnschool/nxg-exam-local-server.git




sudo apt-get install apache2 libapache2-mod-wsgi-py3
sudo a2dismod wsgi
sudo a2enmod wsgi




source /opt/tnschools/venv/bin/activate

cd /opt/tnschools/tnschool-local-server


pip install -r requirements.txt


python3 manage.py makemigrations

python3 manage.py migrate

chown -R www-data:www-data /opt/tnschools/

/etc/init.d/apache2 restart