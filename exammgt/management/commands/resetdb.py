from django.core.management.base import BaseCommand
from django.utils import timezone
#from apps.home.views import emailTiming
import os
from django.conf import settings

class Command(BaseCommand):
    help = 'Reset into a fresh DB'

    def handle(self, *args, **kwargs):
        time = timezone.now().strftime('%X')
        self.stdout.write("It's now %s" % time)
        #print(os.getcwd())
        #print(settings.BASE_DIR)

        db_path = settings.DATABASES['default']['NAME']
        print('dbPath',db_path)

        # print(os.system("which python"))
        python_path = str(os.popen('which python').read()).strip()
        #print('python path',python_path)

        if os.path.exists(db_path):
            os.remove(db_path)
        print(f"{python_path} {os.path.join(settings.BASE_DIR,'manage.py')} makemigrations")
        os.system(f"{python_path} {os.path.join(settings.BASE_DIR,'manage.py')} makemigrations")

        print(f"{python_path} {os.path.join(settings.BASE_DIR,'manage.py')} migrate")
        os.system(f"{python_path} {os.path.join(settings.BASE_DIR,'manage.py')} migrate")

        print(f"chown www-data:www-data {db_path}")
        os.system(f"chown www-data:www-data {db_path}")
        
        os.system("service apache2 restart")


        