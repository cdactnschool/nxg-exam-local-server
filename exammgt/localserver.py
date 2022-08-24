from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import os
from django.conf import settings


class ServerRegistrationStatus(APIView):
        
    def post(self, request):
        
        reg_file = os.path.join(settings.MEDIA_ROOT, 'regstatus')
        
        try:
            with open(reg_file, 'r') as fp:
                reg_status = fp.read()
            return Response({'api_status':True,'message':reg_status})
        except Exception as e:
            print("Error reading regstatus file: ", e)
            reg_status = 'Not Registered'
            return Response({'api_status': False,'message':reg_status})
