#!/usr/bin/python
__Author__ = "Sujit Mandal"
__version__ = "1.0"


import os




def create_directory():
    opt = '/opt'
    local = os.path.join(opt, 'tnschools')
    migrationlogs = os.path.join(opt, f'{local}/migrationlogs')

    log_dir = "/var/log/examlogs/"


    if not os.path.exists(opt):
        os.mkdir(opt)

    if not os.path.exists(local):
        os.mkdir(local)
        

    if not os.path.exists(migrationlogs):
        os.mkdir(migrationlogs)
        
    if not os.path.exists(log_dir):
        os.mkdir(log_dir)
        


#!/usr/bin/python
__Author__ = "Sujit Mandal"
__version__ = "1.0"


import os




def create_directory():
    opt = '/opt'
    local = os.path.join(opt, 'tnschools')
    migrationlogs = os.path.join(opt, f'{local}/migrationlogs')

    log_dir = "/var/log/examlogs/"


    if not os.path.exists(opt):
        os.mkdir(opt)

    if not os.path.exists(local):
        os.mkdir(local)
        

    if not os.path.exists(migrationlogs):
        os.mkdir(migrationlogs)
        
    if not os.path.exists(log_dir):
        os.mkdir(log_dir)
        


def create_virtualenv():
    os.system("/bin/sh create_venv.sh")

    try:
        os.system("sudo chown -R www-data:www-data /opt/tnschools/venv")
    except:
        pass



def pull_server_from_git():
    os.system("/bin/sh download-from-git.sh")




if __name__ == '__main__':
    create_directory()
    pull_server_from_git()
    create_virtualenv()
  