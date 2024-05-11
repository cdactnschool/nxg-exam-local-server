#!/bin/bash
if [ -d "/opt/tnschools/tnschool-local-server" ]; then
   sudo git -C /opt/tnschools/tnschool-local-server reset --hard HEAD >> /var/log/examlogs/git_status.log 2>&1

   sudo git -C /opt/tnschools/tnschool-local-server pull http://cdactnschool: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@github.com/cdactnschool/nxg-exam-local-server.git >> /var/log/examlogs/git_status.log 2>&1

   if [ $? -eq 0 ]; then
       echo `date "+%F %H:%M:%S"` "git pull time" >> /var/log/examlogs/git_status.log
   else
       echo `date "+%F %H:%M:%S"` "git pull error time" >> /var/log/examlogs/git_status.log
   fi

else
   sudo git clone http://cdactnschool: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@github.com/cdactnschool/nxg-exam-local-server.git /opt/tnschools/tnschool-local-server  >> /var/log/examlogs/git_status.log 2>&1

   if [ $? -eq 0 ]; then
       echo `date "+%F %H:%M:%S"` "git clone successfully" >> /var/log/examlogs/git_status.log
   else
      echo `date "+%F %H:%M:%S"` "git clone error time" >> /var/log/examlogs/git_status.log
      rm -rf /opt/tnschools/tnschool-local-server
   fi
  
fi


sudo chown -R www-data:www-data  /opt/tnschools/tnschool-local-server/