sudo apt update

sudo apt install font-manager
-> install Latha.ttf font in the misc folder

sudo apt-get install python3-venv 

sudo apt-get install python3-dev

sudo apt-get install libssl-dev swig gcc

mkdir schoolserver

cd schoolserver

python3 -m venv venv

source venv/bin/activate

git clone http://dvcs.chennai.cdac.in/boss-assessment/tnschool-local-server.git

cd tnschool-local-server

pip install -r requirements.txt

mkdir /opt/examlogs
# sudo chown www-data:www-data /opt/examlogs # if running from apache

python manage.py makemigrations

python manage.py migrate

python manage.py createsuperuser

python manage.py runserver 0.0.0.0:8080
