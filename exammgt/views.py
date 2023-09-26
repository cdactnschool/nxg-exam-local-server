from crypt import methods
from django.shortcuts import render


from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate

from rest_framework.parsers import JSONParser
from django.shortcuts import get_object_or_404
from django.forms.models import model_to_dict
import random


from .serializers import ExamEventsScheduleSerializer, QuestionsSerializer, ChoicesSerializer, ExamMetaSerializer, QpSetsSerializer
from .models import Profile, ExamResponse, EventAttendance, ExamMeta, QpSet, Question, Choice, MiscInfo 
from scheduler.models import participants, scheduling, event

import datetime
import os
import json
from django.contrib.auth.models import User,Group
from django.urls import reverse
import math
from django.contrib.sites.shortcuts import get_current_site

from tnschoollocalserver.tn_variables import AUTH_ENABLE, AUTH_FIELDS, CENTRAL_SERVER_IP, CERT_FILE, DB_STUDENTS_SCHOOL_CHILD_COUNT, RESIDUAL_DELETE_DAYS, DATABASES, MEDIA_ROOT, SUPER_USERNAME, SUPER_PASSWORD, BASE_DIR, central_server_adapter, MEDIUM

import hashlib
import requests
from requests.exceptions import ConnectionError

import pandas as pd
import sqlite3

import logging

import shutil
import time

import subprocess

from django.db import transaction
from django.db import connection as dbconnect

# check for sqlite3 pragma

import sqlite3

def is_database_corrupted():
    try:
        conn = sqlite3.connect(DATABASES['default']['NAME'])
        cursor = conn.cursor()
        cursor.execute('PRAGMA integrity_check;')
        result = cursor.fetchone()[0]
        conn.close()
        if result == 'ok':
            return False
        else:
            return True
    except sqlite3.Error:
        return True

logger      = logging.getLogger('monitoringdebug')
accesslog   = logging.getLogger('accesslog')
errorlog    = logging.getLogger('errorlog')
infolog     = logging.getLogger('infolog')
api_log      = logging.getLogger('api_log')
api_errorlog = logging.getLogger('api_error')
student_log = logging.getLogger('student_log')

import sqlite3
import py7zr

from django.db.models import Q

S3BUCKET_REF_URL = ''


# print('---------Centeral server IP----------',CENTRAL_SERVER_IP)

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    '''
    Customized Token Pair Serialization for generation token along with username and groups field
    '''
    def validate(self, attrs):
        data = super().validate(attrs)
        refresh = self.get_token(self.user)
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)

        print('data:',data)

        # Add extra responses here
        data['username']    = self.user.username
        data['groups']      = self.user.groups.values_list('name', flat=True)[0]
        data['name_text']   = self.user.profile.name_text
        data['section']     = self.user.profile.section
        data['student_class']=self.user.profile.student_class
        data['usertype']    = self.user.profile.usertype
        data['priority']    = self.user.profile.priority
        data['udise_code']  = self.user.profile.udise_code
        data['district_id'] = self.user.profile.district_id
        data['block_id']    = self.user.profile.block_id
        data['school_id']   = self.user.profile.school_id
        data['api_status']  = True    
        data['message']     = 'User authenticated'
        
        return data
        


class MyTokenObtainPairView(TokenObtainPairView):
    '''
    Class to use the custom Token pair Serializer
    '''
    serializer_class = MyTokenObtainPairSerializer

def connection():
    try:
        print('=============================')
        conn = sqlite3.connect(DATABASES['default']['NAME'])
        return conn
    except Exception as e:
        print('connection error :',e)
        return None


def fetch_school_details(mycursor,school_id):

    '''
    Based on [school_id]
    `````````````````````
    Function to fetch school details like
        school_id
        district_id
        block_id
        udise_code
    
    '''

    auth_fields = AUTH_FIELDS

    query = f"SELECT {auth_fields['school']['school_id']}, {auth_fields['school']['district_id']}, {auth_fields['school']['block_id']}, {auth_fields['school']['udise_code']} FROM {auth_fields['school']['auth_table']} WHERE {auth_fields['school']['school_id']} = {school_id} LIMIT 1"
    print('Fetch school details query :',query)
    mycursor.execute(query)
    school_detail_response = mycursor.fetchall()
    print('~~~~ ~~~~~~ ~~~~~~~',school_detail_response[0])
    if len(school_detail_response) == 0:
        return None,None,None,None
    else:
        return school_detail_response[0]

def create_local_user(request,data):
    
    '''
    
    Function to create a user instance based on username and password

    Add the user to a group based on 'user_type' field
    
    '''
    print('````````````````',data)
    if User.objects.filter(username=data['username']).exists():
        print('UserExists')
        # db_user = User.objects.get(username=data['username'])
        # if not db_user.check_password(data['password']):
        #     db_user.set_password(data['password'])
    else:
        db_user = User.objects.create_user(username=data['username'],password = data['password'])
        db_user.save()

    # if Profile.objects.filter(user=db_user).exists():
    #     profile_instance = Profile.objects.get(user=db_user)
    # else:
        profile_instance = Profile.objects.create(user=db_user)
    
    #print('^^^^^^^^^^^^^^^^^^^^^^',data)
        if 'priority' in data:
            profile_instance.priority       = data['priority']
        
        if 'name_text' in data:
            profile_instance.name_text      = data['name_text']
        
        if 'section' in data:
            profile_instance.section        = data['section']
        
        if 'user_type' in data:
            profile_instance.usertype       = data['user_type']
        
        if 'udise_code' in data:
            profile_instance.udise_code     = data['udise_code']
        
        if 'district_id' in data:
            profile_instance.district_id    = data['district_id']
        
        if 'block_id' in data:
            profile_instance.block_id       = data['block_id']
        
        if 'school_id' in data:
            profile_instance.school_id      = data['school_id']

        if 'student_class' in data:
            profile_instance.student_class  =data['student_class']

        profile_instance.save()
    # if db_user.groups.exists():
    #     for g in db_user.groups.all():
    #         db_user.groups.remove(g)
        if data['user_type']:
            my_group = Group.objects.get(name=data['user_type']) 
            my_group.user_set.add(db_user)

    print('Obtaining user pair')
    try:
        print('Token URL',request.build_absolute_uri(reverse('token-obtain-pair')))
        x = requests.post(request.build_absolute_uri(reverse('token-obtain-pair')),data = {'username':data['username'],'password':data['password']})
        x.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(e.response.text)
    
    print("========")
    print('x value',x)
    res_data = x.json()
    

    # Access log entry

    accesslog.info(json.dumps({'school_id':data['school_id'],'emisusername':data['username'],'usertype':data['user_type'],'action':'Login','datetime':str(datetime.datetime.now())},default=str))
    
    print('User account details ',res_data)

    #return Response(res_data)
    return res_data

class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        try:

            refresh_token = RefreshToken.for_user(request.user)
            refresh_token.blacklist()
            accesslog.info(json.dumps({'school_id':request.user.profile.school_id,'emisusername':request.user.username,'usertype':request.user.profile.usertype,'action':'Logout','datetime':str(datetime.datetime.now())},default=str))
            return Response({'api_status':True,'message':'Logout successful'})
        except Exception as e:
            print('Exception in logout :',e)
            return Response({'api_status':False,'message':'Error in logging out','exception':str(e)})



class db_auth(APIView):

    '''
    Class to authenticate with the remote db
    Type of users
    ``````````````
        -> student
        teacher_hm
            -> teacher
            -> hm
        -> department

    Input parameters
    `````````````````
        {
            "username" : "xxxxxxxx",
            "password" : "yyyyyyyy"
        }

    Ouptut parameters
    `````````````````
        {
        "refresh": "eyJn-...-KQ2o",
        "access": "eyJ0-....-6zMn8",
        "username": "xxxxxxx",
        "groups": "xxxxxxx",
        "usertype": "xxxxxxx",
        "priority": 123,
        "udise_code": "123456",
        "district_id": "123456",
        "block_id": "123456",
        "school_id": "123456",
        "api_status": true,
        "message": "User authenticated"
        }

    '''

    def post(self,request):

        try:

            # Check for db

            if not os.path.exists(DATABASES['default']['NAME']):
                return Response({'api_status': False, 'message': 'Database file not found!! Contact 14417'})
            
            if is_database_corrupted():
                return Response({'api_status': False, 'message': 'Database is corrupted!! Kindly restart the school server and check'})

            cn = connection()

            if cn == None:
                data = {}
                data['api_status'] = False
                data['message'] = 'School server Not reachable'
                return Response(data)
            

            mycursor = cn.cursor()

            data = JSONParser().parse(request)
            possible_type = ''
            user_detail = {}

            auth_fields = AUTH_FIELDS

            Group_count = Group.objects.all().count()
            print('Group count',Group_count)

            query = f"SELECT COUNT(*) FROM emisuser_teacher"
            try:
                mycursor.execute(query)
                teacher_count_response = mycursor.fetchone()
                teacher_count = teacher_count_response[0]
            except:
                teacher_count = 0
            print('teacherCount',teacher_count,type(teacher_count))

            '''
            if Group_count < 5 or teacher_count == 0:
                print('Deleting the tables for registeration')
                query = f"DELETE FROM students_school_child_count;"
                mycursor.execute(query)
                cn.commit()
                
                print('Deleting the miscinfo table')
                query = f"DELETE FROM exammgt_miscinfo;"
                mycursor.execute(query)
                cn.commit()
                return Response({'api_status':False,'message':'Refresh the page to Re-Register'})
            '''

            # Check if credentials are loaded or not

            # Check for superuser
            superadmin_user_obj = authenticate(
                username=data['username'], password=data['password'])


            if superadmin_user_obj is not None and superadmin_user_obj.is_staff == True:
                user_detail['user_type'] = 'superadmin_user'
                user_detail['username'] = data['username']
                user_detail['password'] = data['password']
                user_detail['priority'] = auth_fields['superadmin_user']['superadmin_user_priority']

                query = f"SELECT {auth_fields['school']['school_id']}, {auth_fields['school']['district_id']}, {auth_fields['school']['block_id']}, {auth_fields['school']['udise_code']} FROM {auth_fields['school']['auth_table']} LIMIT 1"

                mycursor.execute(query)
                school_detail_response = mycursor.fetchall()

                user_detail['udise_code'] = school_detail_response[0][3]
                user_detail['district_id'] = school_detail_response[0][1]
                user_detail['block_id'] = school_detail_response[0][2]
                user_detail['school_id'] = school_detail_response[0][0]
                token_response = create_local_user(request, user_detail)
                try:
                    print('Starting to close')
                    cn.close()
                    print('Closing Authentication Connection')
                except:
                    pass
                return Response(token_response)



            # Teacher /HM
            # if str(data['username']).isnumeric() and (len(str(data['username'])) == auth_fields['teacher_hm']['username_len']):

            possible_type = 'teacher_hm'
            #print('Possible user type - ',possible_type)
            query = f"SELECT {auth_fields['teacher_hm']['username_field']}, {auth_fields['teacher_hm']['hash_field']} FROM {auth_fields['teacher_hm']['auth_table']} WHERE {auth_fields['teacher_hm']['username_field']} = {data['username']} AND status = 'Active' LIMIT 1"     

                    
            #print('###########',query)
            mycursor.execute(query)
            auth_detail_response = mycursor.fetchall()
            
            # if len(auth_detail_response) == 0:
            #     return Response({'api_status':False,'message':'Incorrect username'})
            print('Records matching the username @ teacher_hm',auth_detail_response, len(auth_detail_response))

            if len(auth_detail_response) != 0:
                #print(auth_detail_response)
                print('Records matching the username @ teacher_hm',auth_detail_response)

                # logger - addd number of records returned & print without LIMIT

                #auth_detail_response = auth_detail_response[0]
                #print('!!!!!',auth_detail_response)
                #print(hashlib.md5(data['password'].encode('utf-8')).hexdigest())
                #print(auth_detail_response[1])

                # use first record


                if hashlib.md5(data['password'].encode('utf-8')).hexdigest() == auth_detail_response[0][1]:

                    query = f"SELECT {auth_fields['teacher_hm']['type_checker_field']},{auth_fields['teacher_hm']['school_key_ref_master']},{auth_fields['teacher_hm']['name_field_master']} FROM {auth_fields['teacher_hm']['master_table']} WHERE {auth_fields['teacher_hm']['type_checker_foreign_key']} = {data['username']}"
                    print('!!!',query)
                    
                    mycursor.execute(query)
                    teacher_hm_master_response = mycursor.fetchall()

                    if len(teacher_hm_master_response) == 0:
                        return Response({'api_status':False,'message':'User Authenticated but no details in Master table'})

                    print('**teacher_hm_master_response',teacher_hm_master_response[0])
                    user_detail['school_id'] = teacher_hm_master_response[0][1]
                    user_detail['name_text'] = teacher_hm_master_response[0][2]
                    #print('*****************',teacher_hm_master_response[0][0],list(auth_fields['teacher_hm']['type_checker_value']))
                    
                    
                    # Fetch school, district, block details
                    user_detail['school_id'], user_detail['district_id'], user_detail['block_id'], user_detail['udise_code'] = fetch_school_details(mycursor=mycursor,school_id=user_detail['school_id'])
                    #print(user_detail)

                    # Differentiate between teacher and hm
                    if teacher_hm_master_response[0][0] in list(auth_fields['teacher_hm']['type_checker_value']):
                        possible_type = 'hm'
                        user_detail['user_type'] = 'hm'
                        user_detail['user_type_id'] = teacher_hm_master_response[0][0]
                        user_detail['username'] = data['username']
                        user_detail['password'] = data['password']
                        user_detail['priority'] = auth_fields['teacher_hm']['hm_priority']
                        print('Given user is HM')
                        print('=====\n',user_detail)
                        token_response = create_local_user(request,user_detail)
                        cn.close()
                        return Response(token_response)
                    else:
                        possible_type = 'teacher'
                        user_detail['user_type'] = 'teacher'
                        user_detail['user_type_id'] = teacher_hm_master_response[0][0]
                        user_detail['username'] = data['username']
                        user_detail['password'] = data['password']
                        user_detail['priority'] = auth_fields['teacher_hm']['teacher_priority']

                        print('Given user is a teacher')
                        print('=====\n',user_detail)
                        token_response = create_local_user(request,user_detail)
                        cn.close()
                        return Response(token_response)

                # else:
                #     return Response({'api_status':False,'possible_type':possible_type,'message':'Incorrect Username/password'})

            
            # School login

            if str(data['username']).isnumeric() and len(str(data['username'])) == 11:
                possible_type = 'school'

                query = f"SELECT user_id, password FROM emis_login WHERE user_id = {data['username']}"
                mycursor.execute(query)

                auth_detail_response = mycursor.fetchall()

                if len(auth_detail_response) > 0:
                    if hashlib.md5(data['password'].encode('utf-8')).hexdigest() == auth_detail_response[0][1]:
                        school_query = f"SELECT udise_code, district_id, block_id, school_id FROM students_school_child_count WHERE udise_code = {data['username']};"

                        print(f'School login query : {query}')

                        mycursor.execute(school_query)
                        school_user_response = mycursor.fetchall()

                        if len(school_user_response) == 0:
                            return Response({'message': 'Invalid Credentials', 'api_status': False, 'possible_type': 'School Login'})

                        user_detail['user_type'] = 'school'
                        user_detail['username'] = data['username']
                        user_detail['password'] = data['password']
                        user_detail['name_text'] = data['username']
                        user_detail['priority'] = 15
                        user_detail['udise_code'] = school_user_response[0][0]
                        user_detail['district_id'] = school_user_response[0][1]
                        user_detail['block_id'] = school_user_response[0][2]
                        user_detail['school_id'] = school_user_response[0][3]

                        token_response = create_local_user(request, user_detail)
                        cn.close()
                        return Response(token_response)
            
            # student


            # elif (str(data['username']).isnumeric()) and (len(str(data['username'])) == auth_fields['student']['username_len']):
            # elif (str(data['username']).isnumeric()):
            possible_type = 'student'

            query = f"SELECT {auth_fields['student']['username_field']},{auth_fields['student']['hash_field']},{auth_fields['student']['school_field_foreign']} FROM {auth_fields['student']['auth_table']} WHERE {auth_fields['student']['username_field']} = {data['username']} AND status = 'Active' LIMIT 1"

            print(query)
            mycursor.execute(query)
            auth_detail_response = mycursor.fetchall()
            
            print('Records matching the username @ student',auth_detail_response)


            if len(auth_detail_response) == 0:
                return Response({'api_status':False,'message':'No data found'})
            
            user_detail['emis_user_id'] = auth_detail_response[0][2]
            
            #print('Records matching the username',auth_detail_response)

            if hashlib.md5(data['password'].encode('utf-8')).hexdigest() == auth_detail_response[0][1]:
                user_detail['user_type'] = 'student'

                # Fetch school id

                query = f"SELECT {auth_fields['student']['school_key_ref_master']},{auth_fields['student']['name_field_master']},{auth_fields['student']['student_class']},{auth_fields['student']['section_field_master']} FROM {auth_fields['student']['master_table']} WHERE {auth_fields['student']['school_field_foreign_ref']} = {user_detail['emis_user_id'] }"
                #print('school id fetch query',query)

                mycursor.execute(query)
                school_id_fetch = mycursor.fetchall()

                if len(school_id_fetch) == 0:
                    return Response({'api_status':False,'message':'User Authenticated but no details in Master table'})

                #print('----------',school_id_fetch[0][0])
                user_detail['school_id'] = school_id_fetch[0][0]
                user_detail['name_text'] = school_id_fetch[0][1]
                user_detail['student_class'] = school_id_fetch[0][2]
                user_detail['section'] = school_id_fetch[0][3]


                # Fetch school, district, block details
                user_detail['school_id'], user_detail['district_id'], user_detail['block_id'], user_detail['udise_code'] = fetch_school_details(mycursor=mycursor,school_id=user_detail['school_id'])

                user_detail['username'] = data['username']
                user_detail['password'] = data['password']
                user_detail['priority'] = auth_fields['student']['student_priority']

                print('@@@@@@@@@@@@@@@@',user_detail)
                token_response = create_local_user(request,user_detail)
                cn.close()
                return Response(token_response)
                # else:
                #     return Response({'api_status':False,'possible_type':possible_type,'message':'Incorrect Username/password'})
            
            try:
                cn.close()
                print('Closing Authentication Connection')
            except:
                pass
            
            # No authentication for department user in local
            # else:
            return Response({'api_status':False,'message':'Incorrect Username/password'})
        
        except Exception as e:
            return Response({'api_status':False,'message':'Error in authenticating','exception':str(e)})

class CandidateResponse(APIView):

    '''
    Class to mark response of for each question per candidate

    input parameters
    ````````````````

    qid <- question_id
    qp_set_id
    event_id
    ans <- answer id
    correct_choice <- id of the correct choice
    review <- bool whether marked for review or not
    participant_pk <- participant pk
    
    '''
    
    def post(self,request,*args, **kwargs):
        
        with transaction.atomic():
            data = JSONParser().parse(request)

            filter_fields = {
                'student_username':request.user.username,
                'question_id':data['qid'],
                'qp_set_id':data['qp_set_id'],
                'event_id':data['event_id'],
                'participant_pk':data['participant_pk']
            }

            def update_exam_response(object_edit, data):
                object_edit.selected_choice_id = None if data['ans'] == '' else data['ans']
                object_edit.question_result = data['correct_choice']
                object_edit.review = data['review']
                object_edit.save()


            try:
                print('Store response username',request.user.username)
                print('Store response filter fields',filter_fields)
                # object_edit = get_object_or_404(ExamResponse,**filter_fields)
                object_edit_filter = ExamResponse.objects.filter(**filter_fields)
                
                # If already a response record exists
                if object_edit_filter.count() == 1:
                    object_edit = object_edit_filter[0]
                    update_exam_response(object_edit, data)
                    return Response({'api_status': True,'message':'updated'})
                
                # If not response of this filters exists
                elif object_edit_filter.count() == 0:
                    try:
                        object_edit = ExamResponse.objects.create(**filter_fields)
                        update_exam_response(object_edit, data)
                        return Response({'api_status': True,'message':'New entry Created'})
                    except Exception as e:
                        return Response({'api_status': False,'message':'Error in creating new entry'})
                
                else: # If more than one response exists for this same filters
                    try:
                        latest_object = object_edit_filter.latest('created_on')
                        object_edit_filter.exclude(pk=latest_object.pk).delete()
                        object_edit = latest_object
                        update_exam_response(object_edit, data)
                        return Response({'api_status': True,'message':'Duplicate entries Deleted'})
                    except Exception as e:
                        return Response({'api_status': False,'message':'Error in Deleting the duplicate entries'})
            
            except Exception as e:
                return Response({'api_status': False,'message': 'Error in saving response','exception':str(e)})




def get_summary(event_id,participant_pk,student_username):

    '''
    
    Function to return the summary content

    Return Fields
    `````````````
    total_questions     - Total number of questions
    not_answered        - Total questions not answered (Total number of questions - Number of visited questions)
    answered            - Total number of questions where answered field is not null
    reviewed            - Total number of questions where 'review' button is set as True
    vistedQuestions     - Total number of visited questions (Total number of entries in ExamResponse table)
    correct_answered    - Total number of questions which are correct (selected_choice_id == question_result)
    wrong_answered      - Total number of question which are incorrectly marked (selected_choice_id != question _result)

    '''

    
    try:
        if participant_pk != None:
            event_attendance_query = EventAttendance.objects.filter(event_id = event_id ,participant_pk = participant_pk,student_username = student_username)
        else:
            event_attendance_query = EventAttendance.objects.filter(event_id = event_id ,student_username = student_username)
        dict_obj = {}
        dict_obj['total_question'] = '-'
        dict_obj['not_answered'] = '-'
        dict_obj['answered'] = '-'
        dict_obj['reviewed'] = '-'
        dict_obj['vistedQuestion'] = '-'
        dict_obj['correct_answered'] = '-'
        dict_obj['wrong_answered'] = '-'
        dict_obj['qp_set'] = '-'


        if event_attendance_query:
            event_attendance_object             = event_attendance_query[0]

            print('========')
            dict_obj['total_question']      = event_attendance_object.total_questions
            dict_obj['not_answered']        = event_attendance_object.total_questions - event_attendance_object.answered_questions
            dict_obj['answered']            = event_attendance_object.answered_questions
            dict_obj['reviewed']            = event_attendance_object.reviewed_questions
            dict_obj['vistedQuestion']      = event_attendance_object.visited_questions
            dict_obj['correct_answered']    = event_attendance_object.correct_answers
            dict_obj['wrong_answered']      = event_attendance_object.wrong_answers
            dict_obj['qp_set']              = event_attendance_object.qp_set

        
        return dict_obj

    except Exception as e:
        print('Exception in the get_summary function',e)
        return {}

class summary(APIView):
    '''
    
    class to return the summary content when the candidate submits the exam

    input field
    ```````````

    event_id <- id or schedule_id
    participant_pk <- participant_pk id of the participant table
    '''

    if AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated
    
    def post(self,request,*args, **kwargs):

        try:
        
            data = JSONParser().parse(request)
            #print(data,data['event_id'])
            #print('---------',data['event_id'],request.user.username) 
            try:
                return Response(get_summary(event_id = data['event_id'],participant_pk = data['participant_pk'],student_username = request.user.username))
            except:
                return Response(get_summary(event_id = data['event_id'],participant_pk = None, student_username = request.user.username))
                

        except Exception as e:
            return Response({'api_status':False,'message':'Error in generating summary','exception':f'Exception occured in message : {e}'})

class SummaryAll(APIView):
    '''
    class to return list of summaries

    input field
    ````````````

    event_id <- id or schedule_id


    '''
    if AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated
    
    def post(self,request,*args, **kwargs):

        try:
            summary_list = []
            data = JSONParser().parse(request)

            for attendance_object in EventAttendance.objects.filter(event_id=data['event_id'], participant_pk = data['participant_pk']):
                #print(attendance_object.event_id,attendance_object.student_username)
                
                if attendance_object.end_time != None:
                #summary_consolidated 
                    try:
                        summary_consolidated = get_summary(event_id = attendance_object.event_id,participant_pk = data['participant_pk'],student_username = attendance_object.student_username)
                    except:
                        summary_consolidated = get_summary(event_id = attendance_object.event_id,participant_pk = None,student_username = attendance_object.student_username)
                    summary_consolidated['completed'] = 1
                else:
                    summary_consolidated={}
                    summary_consolidated['total_question'] = '-'
                    summary_consolidated['not_answered'] = '-'
                    summary_consolidated['answered'] = '-'
                    summary_consolidated['reviewed'] = '-'
                    summary_consolidated['vistedQuestion'] = '-'
                    summary_consolidated['correct_answered'] = '-'
                    summary_consolidated['wrong_answered'] = '-'
                    summary_consolidated['completed'] = 0

                summary_consolidated['username'] = attendance_object.student_username
                #summary_consolidated['name'] = attendance_object.student_id.profile.name_text
                #summary_consolidated['section'] = attendance_object.student_id.profile.section
                #summary_consolidated['class'] = attendance_object.student_id.profile.student_class

                summary_list.append(summary_consolidated)
            
            return Response(summary_list)

        except Exception as e:
            print(e)
            return Response({'api_status':False,'message':f'Exception occured {e}'})


class GetMyEvents(APIView):

    '''
    Class to fetch events for the users

    Note: For students, additional filter of class standard is added
    
    '''

    if AUTH_ENABLE: 
        permission_classes = (IsAuthenticated,) # Allow only if authenticated 
    
    def post(self,request,*args, **kwargs): 
        
        try:
            #data = JSONParser().parse(request)

            # Filter based on the window allowed window size
            print('Fetch schedules between',(datetime.datetime.now().date() - datetime.timedelta(days=30)),(datetime.datetime.now().date() + datetime.timedelta(days=30)))
            
            events_queryset = scheduling.objects.filter(
                event_enddate__gte = (datetime.datetime.now().date() - datetime.timedelta(days=30)),    # Greater than exam end date
                event_startdate__lte = (datetime.datetime.now().date() + datetime.timedelta(days=30))   # Lesser than exam start date
            )

            if request.user.profile.usertype == 'student':  # filter class for students
                events_queryset = events_queryset.filter(class_std=request.user.profile.student_class)
                # Addition of section
                events_queryset = events_queryset.filter(Q(class_section=None) | Q(class_section=request.user.profile.section))

                # Get emis_user_id
                cn = connection()

                if cn == None:
                    data = {}
                    data['api_status'] = False
                    data['message'] = 'School server Not reachable'
                    return Response(data)
                
                mycursor = cn.cursor()

                query = f"SELECT emis_user_id FROM emisuser_student WHERE emis_username = {request.user.username} "

                mycursor.execute(query)
                emis_user_id_response = mycursor.fetchall()
                emis_user_id = emis_user_id_response[0][0]

                print('_+_+_+_+_+_+',emis_user_id)

                try:
                    query = f"SELECT education_medium_id, group_code_id FROM students_child_detail WHERE id in (select emis_user_id FROM emisuser_student WHERE emis_username = {request.user.username});"

                    # print('Mother tounge query',query)
                    mycursor.execute(query)
                    student_master_response = mycursor.fetchall()
                    student_master_lang = student_master_response[0][0]
                    student_master_group = int(student_master_response[0][1])

                    print('Student master language',student_master_lang)
                    print('Student master group',student_master_group,type(student_master_response[0][1]))
                
                except Exception as e:
                    return Response({'api_status':False,'message':f"Error in fetching student's mother tounge",'exception':str(e)})

                mycursor.close()

                # Filter for student language

                events_queryset = events_queryset.filter(class_medium = student_master_lang)

                # Filter for stream for higher secondary

                events_queryset = events_queryset.filter(
                    # Q(class_group=None) | Q(class_group__startswith=f"{student_master_group}-")
                    Q(class_group=None) | Q(class_group__icontains=f"{student_master_group}-")
                    )

                # print('stream query set',events_queryset.query)

                scheduling_list_ids = list(events_queryset.values_list('schedule_id',flat = True))
                # scheduling_list_ids = [1,2,3,4,5,6,7,8,9]
                print('-=-=-=-=-',scheduling_list_ids)

                participants_queryset = participants.objects.filter(schedule_id__in = scheduling_list_ids)

                participants_queryset = participants_queryset.filter(
                    Q(participant_category="DISTRICT") |
                    Q(participant_category="BLOCK") |
                    Q(participant_category="SCHOOL") |
                    Q(participant_category="STUDENT", participant_id = emis_user_id)
                )

                participants_list_ids = list(participants_queryset.values_list('schedule_id',flat=True))

                # participants_list_ids = [1,2,3,4,5]

                events_queryset = events_queryset.filter(schedule_id__in = participants_list_ids)


            sch_id_list = list(events_queryset.values_list('schedule_id',flat=True))
            
            event_data = []
            
            if len(sch_id_list) > 0:
            
                with dbconnect.cursor() as c:
                    get_events_query = f'''SELECT 
                    sch.schedule_id, 
                    sch.event_title, 
                    sch.class_std, 
                    sch.class_section, 
                    sch.class_group, 
                    sch.class_subject, 
                    sch.class_medium, 
                    sch.event_startdate, 
                    sch.event_enddate, 
                    sch.event_starttime, 
                    sch.event_endtime, 
                    sch.exam_category,
                    sch.is_1_n,
                    par.id as participant_pk,
                    par.section,
                    par.allocation_status,
                    par.generation_status
                    FROM scheduler_scheduling sch
                    LEFT JOIN scheduler_participants par WHERE par.schedule_id = sch.schedule_id
                    '''
                    
                    if len(sch_id_list) == 1:
                        get_events_query = f"{get_events_query} AND sch.schedule_id = {sch_id_list[-1]}"
                    else:
                        get_events_query = f"{get_events_query} AND sch.schedule_id IN {tuple(sch_id_list)}"
                        
                    
                    if request.user.profile.usertype == 'student':
                        get_events_query = f'{get_events_query} AND ((sch.is_1_n = 0) OR (sch.is_1_n = 1 AND par.section = "{request.user.profile.section}"))'
                    
                    # print('query set',get_events_query)
                    
                    c.execute(get_events_query)
                    
                    columns = [col[0] for col in c.description]
                    
                    
                    for schedule in c.fetchall():
                        single_event = {columns[i]: schedule[i] for i in range(len(columns))}
                        
                        #  Get class section for 1:n allocation
                        if single_event['is_1_n'] == 1:
                            single_event['class_section'] = single_event['section']
                        
                        
                        #  Get exam_status
                        '''
                        Return if Exam is started/not completed/Completed

                        0 -> Exam not Started
                        1 -> Exam not Completed
                        2 -> Exam Completed

                        '''
                        
                        try:
                        
                            if request.user.profile.usertype in ['teacher','hm','superadmin_user','school']:
                                single_event['exam_status'] = None
                            else:
                                attendance_obj = EventAttendance.objects.filter(event_id=single_event['schedule_id'],participant_pk = single_event['participant_pk'],student_username=str(request.user.username))
                                
                                # print('Length of attendance object',len(attendance_obj))
                                
                                if len(attendance_obj) == 0:
                                    single_event['exam_status'] = 0
                                else:
                                    print('---------length of attendance',len(attendance_obj),attendance_obj)
                                    if attendance_obj[0].end_time == None:
                                        single_event['exam_status'] = 1
                                    
                                    elif attendance_obj[0].end_time != None:
                                        single_event['exam_status'] = 2
                                    else:
                                        single_event['exam_status'] = None
                            print(single_event['schedule_id'],single_event['participant_pk'],'Exam status',single_event['exam_status'])
                            
                        except Exception as e:
                            print('Exception in fetching exam_status ',e)
                            single_event['exam_status'] = None
                        
                        # event_status
                        '''
                        Return if Event is live/old/upcoming

                        0 -> Live
                        1 -> Upcoming
                        2 -> Old

                        '''
                        try:
                            
                            # print('Event start date',single_event['event_startdate'])
                            
                            if datetime.datetime.strptime(str(single_event['event_startdate']), "%Y-%m-%d").date() <= datetime.datetime.now().date() <= datetime.datetime.strptime(str(single_event['event_enddate']), "%Y-%m-%d").date():
                                single_event['event_status'] = 0
                            elif datetime.datetime.strptime(str(single_event['event_startdate']), "%Y-%m-%d").date() > datetime.datetime.now().date():
                                single_event['event_status'] = 1
                            elif datetime.datetime.strptime(str(single_event['event_enddate']), "%Y-%m-%d").date() < datetime.datetime.now().date():
                                single_event['event_status'] = 2
                            else :
                                single_event['event_status'] = None
                            print(single_event['schedule_id'],single_event['participant_pk'],'Event Timing Status',single_event['event_status'])
                        except Exception as e:
                            print('Excetion in getting event status',e)
                            single_event['event_status'] = None
                            
                        # event_completion_status Return count of candidates who have completed the exam
                        try :    
                            if request.user.profile.usertype == 'student':
                                single_event['event_completion_status'] = None
                            else:
                                single_event['event_completion_status'] = EventAttendance.objects.filter(event_id=single_event['schedule_id'],participant_pk = single_event['participant_pk']).exclude(end_time=None).count()
                            
                            print(single_event['schedule_id'],single_event['participant_pk'],'Event Completion Status',single_event['event_completion_status'])
                        
                        except Exception as e:
                            print('Exception in getting event_completion_status',e)
                            single_event['event_completion_status'] = None
                        
                        #  exam_correct
                        '''
                        Return the total number of correct answers of the candidate

                        Return marks from the attendance_object
                        Return '-' if Exam is not submitted
                        Return 'A' if not attempted

                        '''
                        try:
                            if request.user.profile.usertype in ['teacher','hm','superadmin_user','school']:
                                single_event['exam_correct'] = None
                            
                            else:
                                
                                meta_status_query = ExamMeta.objects.filter(event_id = single_event['participant_pk'],participant_pk = single_event['schedule_id'])
                                # print('meta status query',meta_status_query)
                                if len(meta_status_query) == 0:
                                    print('No meta data available',single_event['participant_pk'],single_event['schedule_id'])
                                    single_event['exam_correct'] = '-'
                                else:
                                    meta_status_object = meta_status_query[0]
                                    attendance_obj_qs = EventAttendance.objects.filter(event_id=single_event['schedule_id'],participant_pk = single_event['participant_pk'],student_username=request.user.username)
                                    
                                    
                                    if len(attendance_obj_qs) == 0:
                                        single_event['exam_correct'] =f"A/{meta_status_object.no_of_questions}"
                                    else:
                                        
                                        if attendance_obj_qs[0].end_time == None:
                                            single_event['exam_correct'] =  f"-/{meta_status_object.no_of_questions}"
                                        else:
                                            single_event['exam_correct'] =  f"{attendance_obj_qs[0].correct_answers}/{meta_status_object.no_of_questions}"
                                    
                            print(single_event['schedule_id'],single_event['participant_pk'],'Student correct count',single_event['exam_correct'])

                        except Exception as e:
                            print('Exception in getting exam_correct ',e)
                            single_event['exam_correct'] = None
                        
                        # meta_status
                        '''
                        Check if meta data is set for the event

                        0 -> Meta data not set
                        1 -> Meta data set

                        '''
                        try:
                            if ExamMeta.objects.filter(event_id = single_event['participant_pk'],participant_pk = single_event['schedule_id']).count() == 0:
                                single_event['meta_status'] = 0
                            else:
                                single_event['meta_status'] = 1
                            print(single_event['schedule_id'],single_event['participant_pk'],'Meta Status',single_event['meta_status'])
                                
                        except Exception as e:
                            print('Exception in getting meta_status ',e)
                            single_event['meta_status'] = 0
                        
                        
                        #  total_candidates
                        
                        try:
                            if request.user.profile.usertype == 'student':
                                single_event['total_candidates'] = None
                            cn = connection()
                            mycursor = cn.cursor()

                            query = f" SELECT COUNT(l.{AUTH_FIELDS['student']['username_field']}) FROM {AUTH_FIELDS['student']['auth_table']} l LEFT JOIN {AUTH_FIELDS['student']['master_table']} r ON l.{AUTH_FIELDS['student']['school_field_foreign']} = r.{AUTH_FIELDS['student']['school_field_foreign_ref']} WHERE r.{AUTH_FIELDS['student']['student_class']} = {single_event['class_std']}"
                            if single_event['class_section'] != None:
                                query = f"{query} AND r.{AUTH_FIELDS['student']['section_field_master']} = '{single_event['class_section']}'"
                            
                            if single_event['class_group'] != None:
                                # query = f"{query} AND r.group_code_id = {single_event['class_group'].split('-')[0]}"
                                if isinstance(eval(single_event['class_group']), list):
                                    group_list = [i.split('-')[0] for i in eval(single_event['class_group'])]
                                    if len(group_list) == 1:
                                        group_values = f"({group_list[0]})"
                                    else:
                                        group_values = tuple(group_list)
                                    query = f"{query} AND r.group_code_id IN {group_values}"

                            mycursor.execute(query)
                            student_count_result = mycursor.fetchall()
                            single_event['total_candidates'] = student_count_result[0][0]
                            
                            # print('Total candidates',student_count_result[0][0])
                            
                            cn.close()
                            
                            print(single_event['schedule_id'],single_event['participant_pk'],'Total candidates count',single_event['total_candidates'])
                            
                        except Exception as e:
                            print('Exception in getting total_candidates',e)
                            single_event['total_candidates'] = None
                            
                        
                        #  duration_mins
                        '''
                        Fetch the exam duration from the ExamMeta table
                        '''
                        
                        try:
                            if request.user.profile.usertype != 'student':
                                single_event['duration_mins'] = 'NA'
                            else:
                                attendance_obj = EventAttendance.objects.filter(event_id=single_event['schedule_id'],participant_pk = single_event['participant_pk'],student_username=request.user.username)
                                
                                if len(attendance_obj) == 0:
                                    print('No attendance')
                                    meta_duration_query = ExamMeta.objects.filter(event_id = single_event['participant_pk'],participant_pk = single_event['schedule_id'])
                                    if len(meta_duration_query) == 0:
                                        single_event['duration_mins'] = '-'
                                    else:
                                        single_event['duration_mins']  = meta_duration_query[0].duration_mins
                                else:
                                    single_event['duration_mins']  = math.ceil(attendance_obj[0].remaining_time/60) # Return remaining time in minutes
                                
                        except Exception as e:
                            print('Exception in getting duration_mins',e)
                            single_event['duration_mins'] = '-'
                            
                            
                        #  user_type
                        try:
                            single_event['user_type'] = request.user.profile.usertype
                        except Exception as e:
                            print('Exception in getting user_type',e)
                            single_event['user_type'] = None
                            
                            
                        #  lang_desc
                        
                        try:
                            single_event['lang_desc'] = MEDIUM[int(single_event['class_medium'])]
                        except Exception as e:
                            print('Exception in getting lang_desc',e)
                            single_event['lang_desc'] = 0
                        
                        
                        event_data.append(single_event)
                        # print(single_event)
            
            events_serialized = ExamEventsScheduleSerializer(events_queryset,many=True,context={'user':request.user})

            events_serialized_data = {
                'api_status':True,
                'data':event_data
                # 'data':events_serialized.data
            }

            return Response(events_serialized_data)

        except Exception as e:
            return Response({'api_status':False,'message':f'Error in getting my events','exception':str(e)})

class UpdateRemtime(APIView):
    '''
    
    Store remaining time (Seconds)

    Input fields
    ````````````
    event_id <- id
    student_id <- request.user.username

    rem_time <- remaining time in seconds
    
    participant_pk <- participant_pk value
    
    '''
    def post(self,request,*args, **kwargs):
        try:
            data = JSONParser().parse(request)
            data['event_id'] = data['id']

            attendance_object_check = EventAttendance.objects.filter(event_id = data['event_id'] , participant_pk = data['participant_pk'],student_username = request.user.username)

            if attendance_object_check:
                attendance_object_check = attendance_object_check[0]
                attendance_object_check.remaining_time = data['rem_time']
                attendance_object_check.save()

                return Response({'api_status': True, 'message':'Remaining time updated successfully'})
            else:
                return Response({'api_status':False,'message':'No entry in the table availble for update'})
            #rem_time
        except Exception as e:
            return Response({'api_status':False,'message':'No respose available','Exception':e})

class ExamSubmit(APIView):

    '''

    submit the exam
    set end_time in the EventAttendance table
    
    '''
    #permission_classes = (IsAuthenticated,) # Allow only if authenticated
    def post(self,request,*args, **kwargs):
        try:
            data = JSONParser().parse(request)
            data['event_id'] = data['id']
        except Exception as e:
            return Response({'api_status':False,'message':"event_id 'id' not passed",'exception':e})

        attendance_object_check = EventAttendance.objects.filter(event_id = data['event_id'] , participant_pk = data['participant_pk'],student_username = request.user.username)

        #print('Attendance object ',len(attendance_object_check))

        # Fetch the total number of question from the meta data

        if len(attendance_object_check) != 0:


            attendance_object_check = attendance_object_check[0]
            attendance_object_check.end_time = datetime.datetime.now()
            attendance_object_check.total_questions = ExamMeta.objects.filter(event_id = data['participant_pk'],participant_pk = data['event_id'])[0].no_of_questions
            visited_questions   = 0
            answered_questions  = 0
            reviewed_questions  = 0
            correct_answers     = 0
            wrong_answers       = 0
            
            
            student_responses = ExamResponse.objects.filter(event_id=data['event_id'],participant_pk = data['participant_pk'],student_username=request.user.username,qp_set_id=attendance_object_check.qp_set)

            if student_responses.count() == 0:
                return Response({'api_status':False,'message' : 'No responses recorded'})
            
            for resp_obj in student_responses:
                visited_questions += 1
                
                if resp_obj.selected_choice_id:
                    answered_questions += 1
                
                    if resp_obj.selected_choice_id == resp_obj.question_result:
                        correct_answers += 1
                    else:
                        wrong_answers += 1
                
                if resp_obj.review:
                    reviewed_questions += 1
                
            # Check if parameters are above thresholds(total questions)

            if visited_questions > attendance_object_check.total_questions:
                visited_questions = attendance_object_check.total_questions
            elif visited_questions < 0:
                visited_questions = 0

            if answered_questions > visited_questions:
                answered_questions = visited_questions
            elif answered_questions < 0:
                answered_questions = 0

            if reviewed_questions > visited_questions:
                reviewed_questions = visited_questions
            elif reviewed_questions < 0:
                reviewed_questions = 0

            if correct_answers > answered_questions:
                correct_answers = answered_questions 
            elif correct_answers < 0:
                correct_answers = 0

            if wrong_answers + correct_answers > answered_questions:
                wrong_answers = answered_questions - correct_answers
            elif wrong_answers < 0:
                wrong_answers = 0
                
            attendance_object_check.visited_questions   = visited_questions
            attendance_object_check.answered_questions  = answered_questions
            attendance_object_check.reviewed_questions  = reviewed_questions
            attendance_object_check.correct_answers     = correct_answers
            attendance_object_check.wrong_answers       = wrong_answers
            
            attendance_object_check.save()

            # Adding data for filebeat
            #student_end_log.info(json.dumps({'school_id':request.user.profile.school_id,'event_id':data['event_id'],'emisusername':request.user.username,'end_time':str(attendance_object_check.end_time)}))
            student_log.info(json.dumps({'school_id':request.user.profile.school_id,'event_id':data['event_id'],'emisusername':request.user.username,'end_time':str(attendance_object_check.end_time)},default=str))

            print(json.dumps({'school_id':request.user.profile.school_id,'event_id':data['event_id'],'emisusername':request.user.username,'end_time':str(attendance_object_check.end_time)},default=str))

            return Response({'api_status':True,'message' : 'Exam submitted'})
        else:
            return Response({'api_status':True,'message': 'No attendance record available'})


class SchoolExamSummary(APIView):
    '''
    Class to consolidate responses of a candidate upon completion

    input parameter
    `````````````````

    {
        "event_id":123,
        #"user":13, #13,16
        "student_username": 123456
        "qp_set_id":15
    }

    
    '''

    if AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated

    def post(self,request,*args, **kwargs):
        try:
            # school_id = 30488 # Fetch from the API
            school_id = request.user.profile.school_id
            data = JSONParser().parse(request)

            filter_dict = {}
            filter_dict['event_id'] = data['event_id']
            filter_dict['student_username'] = data['student_username']
            filter_dict['qp_set_id'] = data['qp_set_id']

            file_name = f"cons_data/{data['event_id']}_{school_id}.json"
            
            
            print('Filtered values :',filter_dict)
            obj = ExamResponse.objects.filter(**filter_dict)

            if len(obj) == 0:
                return Response({'api_status':False,"message":"No repsonse given by user for exam is available"})

            if not os.path.exists(file_name) or os.stat(file_name).st_size == 0:
                consolidated_data = {}
                consolidated_data = {
                    'event_id':data['event_id'],
                    'school_id':school_id,
                    'details':[]
                }

                with open(file_name, 'w') as outfile:  
                    json.dump(consolidated_data, outfile,default=str)

            with open(file_name,'r') as input_file:
                consolidated_data = json.load(input_file)

            candidate_consolidated = {}
            candidate_consolidated['student_username'] = data['student_username']
            candidate_consolidated['qp_set_id'] = data['qp_set_id']
            candidate_consolidated['start_time'] = None
            candidate_consolidated['end_time'] = None

            responses = []
            for obj_instance in obj:
                responses.append({
                    'question_id':obj_instance.question_id,
                    'selected_choice_id':obj_instance.selected_choice_id,
                    'correct_choice_id':obj_instance.question_result,
                    'mark':obj_instance.mark,
                    'created_on':str(obj_instance.created_on)
                })
            candidate_consolidated['responses'] = responses
            consolidated_data['details'].append(candidate_consolidated)

            with open(file_name, 'w') as outfile:  
                json.dump(consolidated_data, outfile,default=str)
            print(consolidated_data)

            # todo json= 1 to be checked
            consolidated_data['api_status'] = True
            return Response(consolidated_data)
        except Exception as e:
            print(f'Exception raised while creating a candidate question meta data object throught API : {e}')


def get_answers(username,participant_pk,qid,qp_set_id,event_id):
    try:
        # print('&&&& Fetching answers for ',username,qid,qp_set_id,event_id)
        filter_fields = {
            'student_username':username,
            'participant_pk':participant_pk,
            'question_id':qid,
            'qp_set_id':qp_set_id,
            'event_id':event_id
        }
        obj = get_object_or_404(ExamResponse,**filter_fields)

        ans = "" if obj.selected_choice_id == None else obj.selected_choice_id
        return obj.review, ans
    except Exception as e:
        # print(e)
        return "",""

class GenerateQuestionPaper(APIView):
    '''
    class to generate question paper per candidate

    Input parameters
    ````````````````

    {
        id : 123,
        participant_pk <- participant_pk
    }


    '''

    if AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated

    def post(self,request,*args, **kwargs):

        try:

            # check if entry already exists and not completed

            #print('******',request.data)
            # request_data = JSONParser().parse(request)
            request_data = request.data

            # print('-------------request-data-------------',request_data)

            request_data['event_id'] = request_data['id']

            # print('---------------',request_data)

            try:
                # print('request_data',request_data)
                participant_category = participants.objects.filter(schedule_id = request_data['id'],id = request_data['participant_pk'])[0].participant_category
            except Exception as e:
                participant_category = None
                print('Exception in fetching participant category',e)
            
            print('Participant_category type :',participant_category)

            try:
                if participant_category != 'STUDENT':
                    qpset_list = participants.objects.filter(schedule_id = request_data['id'],id = request_data['participant_pk'])[0].event_allocationid
                
                else :
                    
                    # Fetching question paper for student type
                    cn = connection()

                    if cn == None:
                        data = {}
                        data['api_status'] = False
                        data['message'] = 'School server Not reachable'
                        return Response(data)
                    
                    mycursor = cn.cursor()

                    query = f"SELECT emis_user_id FROM emisuser_student WHERE emis_username = {request.user.username} "

                    mycursor.execute(query)
                    emis_user_id_response = mycursor.fetchall()
                    emis_user_id = emis_user_id_response[0][0]

                    cn.close()

                    # print('QPset query inputs',request_data['id'],emis_user_id)
                    qpset_list = participants.objects.filter(schedule_id = request_data['id'],participant_id = emis_user_id, id = request_data['participant_pk'])[0].event_allocationid



            except Exception as e:
                qpset_list = None
                # print('Error in fetching participant id :',str(e))
                errorlog.error(json.dumps({'school_id':request.user.profile.school_id,'action':'Fetch emis_username for Generate_QP','event_id':request_data['event_id'],'datetime':str(datetime.datetime.now()),'exception':str(e)},default=str))

            # print(f'QP set list ---------',qpset_list)
        
            event_attendance_check = EventAttendance.objects.filter(event_id = request_data['event_id'] ,participant_pk = request_data['participant_pk'],student_username = request.user.username)

            
            # print('Event attendance check',event_attendance_check)
        
            question_meta_object = ExamMeta.objects.filter(**{"event_id" : request_data['participant_pk'],"participant_pk" : request_data['event_id']})


            # print('Event quetion meta object',question_meta_object)
            
            if len(question_meta_object) > 0:
                question_meta_object = question_meta_object[0] # get the first instance
                # print('question_meta_object Content',question_meta_object)
            else:
                return Response({'api_status':False,'message':'No question set for this student'})


            #Add an entry in the event_attenance_check
            if len(event_attendance_check) == 0:
                
                # print('---remaining---time',question_meta_object.duration_mins)

                event_attendance_obj = EventAttendance.objects.create(
                    event_id = request_data['event_id'],
                    participant_pk = request_data['participant_pk'],
                    student_username =request.user.username,
                    # qp_set = random.choice(eval(question_meta_object.qp_set_list)),
                    qp_set = random.choice(eval(qpset_list)),
                    remaining_time = int(question_meta_object.duration_mins) * 60,  # return duration in seconds
                    start_time = datetime.datetime.now()
                )
                event_attendance_obj.save()
                
                # Adding data for filebeat
                #student_start_log.info(json.dumps({'school_id':request.user.profile.school_id,'event_id':request_data['event_id'],'emisusername':request.user.username,'start_time':str(event_attendance_obj.start_time)}))
                student_log.info(json.dumps({'school_id':request.user.profile.school_id,'event_id':request_data['event_id'],'emisusername':request.user.username,'start_time':str(event_attendance_obj.start_time)},default=str))

            else:
                event_attendance_obj = event_attendance_check[0]
            

            qpset_filter = {
                'event_id': request_data['event_id'],
                'qp_set_id': event_attendance_obj.qp_set
            }

            exam_filter = {
                "event_id": request_data['participant_pk'],
                "participant_pk" : request_data['event_id']
            }
            
            #Save Json File Into Schhool Local Server
            #file_name = str(request_data['event_id']) + '_' + str(event_attendance_obj.qp_set)
            json_path = "{0}_{1}_{2}.json".format(request_data['event_id'] , request_data['participant_pk'],event_attendance_obj.qp_set)
            
            FOLDER = os.path.join(MEDIA_ROOT,'questions_json')

            if not os.path.exists(FOLDER):
                os.mkdir(FOLDER)
            exam_meta_object_edit = ExamMeta.objects.filter(**exam_filter)
            #MEDIA_PATH ="/".join(MEDIA_ROOT.split('/')[:-1]) + '/' + FOLDER
            json_file_path =  os.path.join(FOLDER, json_path)

            # print('QP json file existance status',os.path.exists(json_file_path))

            if os.path.exists(json_file_path) and os.path.getsize(json_file_path) > 0:
                with open(json_file_path, 'r') as f:
                    question_paper_data = json.load(f)
            
                print('----------------------------------------------------------------')
                print('Event ID and QP SET ID already exists in local school database..',json_file_path)
                        
                print('----------------------------------------------------------------')

                for answers in question_paper_data['ans']:
                    answers['review'], answers['ans'] = get_answers(request.user.username,request_data['participant_pk'],answers['qid'],event_attendance_obj.qp_set,request_data['event_id'])
                question_paper_data['user'] = request.user.username
                question_paper_data['qp_set_id'] = event_attendance_obj.qp_set
                question_paper_data['exam_duration'] = event_attendance_obj.remaining_time # Fetch seconds
                question_paper_data['end_alert_seconds'] = question_paper_data['end_alert_time'] * 60 # Convert to seconds

                question_paper_data['api_status'] = True

                infolog.info(json.dumps({'school_id':request.user.profile.school_id,'username':request.user.username,'action':'Generate_QP','event_id':request_data['event_id'],'datetime':str(datetime.datetime.now())},default=str))

                return Response(question_paper_data)

            else:
                exam_meta_data = []
                for exam_data in exam_meta_object_edit:
                    tmp_exam_dict = model_to_dict(exam_data)
                    try:
                        
                        #  switching event_id and participant_pk
                        temp_event_id = tmp_exam_dict['participant_pk']
                        temp_participant_pk = tmp_exam_dict['event_id']
                        
                        tmp_exam_dict['event_id'] = temp_event_id
                        tmp_exam_dict['participant_pk'] = temp_participant_pk
                        
                        del tmp_exam_dict['event_startdate']
                        del tmp_exam_dict['event_enddate']
                        del tmp_exam_dict['qp_set_list']
                    except:
                        pass
                    
                    tmp_exam_dict['qp_set_id'] = event_attendance_obj.qp_set
                    tmp_exam_dict['exam_duration'] = event_attendance_obj.remaining_time # Fetch seconds
                    tmp_exam_dict['end_alert_seconds'] = tmp_exam_dict['end_alert_time'] * 60 # Convert to seconds
                    exam_meta_data.append(tmp_exam_dict)

                    print('------exam_meta---------',exam_meta_data)
            
                qpset_filter = {
                #'event_id': request_data['event_id'],
                
                'event_id': request_data['participant_pk'],
                'qp_set_id': event_attendance_obj.qp_set
                }
        
                # print('--------------------------')
                qp_sets_object_edit = QpSet.objects.filter(**qpset_filter)
                qp_set_data = []  
                # print('--------------------------')
                for qp_data in qp_sets_object_edit:
                    print(qp_data)
                    qp_set_data.append(model_to_dict(qp_data))
            
                qid_list = eval(qp_set_data[0]['qid_list'])

                # print('---------start----qp_base---------',qid_list)

                qp_base64_list = []
                qp_base64_list_object_edit = Question.objects.filter(qid__in=qid_list)
                for qp_data in qp_base64_list_object_edit:
                    qp_base64_list.append(model_to_dict(qp_data))

                # print('-------qp_base--------')

                # for t in qp_base64_list:
                #     print('_+_+_+_+_',t['qid'])

                choice_base64_list = []
                for qid in qid_list:
                    filter = {
                        "qid": int(qid)
                    }

                    choice_base64_list_object_edit = Choice.objects.filter(**filter)
                    print('=-=-=-=', choice_base64_list_object_edit)
                    choice_base64_list_object = []
                    for ch_data in choice_base64_list_object_edit:
                        tmp_dict_data = model_to_dict(ch_data)
                        # del tmp_dict_data['qid']
                        choice_base64_list_object.append(tmp_dict_data)
                    choice_base64_list.append(choice_base64_list_object)

                # print('choice appended list',choice_base64_list)
                # print('-----------choice----------')

                questions_data_list =[]
                for qp_img in qp_base64_list:
                    for ch_img in choice_base64_list:
                        tmp_ch_dict = {}
                        print(qp_img['qid'],'****',ch_img)
                        if len(ch_img) == 0:
                            continue
                        if qp_img['qid'] == str(ch_img[0]['qid']):
                            tmp_ch_dict['q_choices'] = ch_img
                            qp_img.update(tmp_ch_dict)
                
                    questions_data_list.append(qp_img)

                print('-------questions-------------------')

                get_ans_api = []
                for q_id in qid_list:
                    tmp = {}
                    tmp['qid'] = q_id
                    tmp['review'], tmp['ans'] = get_answers(request.user.username,request_data['participant_pk'],q_id,event_attendance_obj.qp_set,request_data['event_id'])

                    get_ans_api.append(tmp)

                configure_qp_data = exam_meta_data[0]
                configure_qp_data['qp_set_id'] = event_attendance_obj.qp_set
                configure_qp_data['q_ids'] = qid_list
                configure_qp_data['questions'] = questions_data_list
                configure_qp_data['ans'] = get_ans_api
                

                # print('------------configure_qp_data------------')
                # print(configure_qp_data)

                # for c in configure_qp_data:
                #     print(c,configure_qp_data[c])


                #if not os.path.exists(MEDIA_PATH):
                #    os.makedirs(MEDIA_PATH)
                with open(json_file_path , 'w') as f :
                    json.dump(configure_qp_data, f,default=str)
                configure_qp_data['user'] = request.user.username
                configure_qp_data['api_status'] = True

                infolog.info(json.dumps({'school_id':request.user.profile.school_id,'username':request.user.username,'action':'Generate_QP','event_id':request_data['event_id'],'datetime':str(datetime.datetime.now())},default=str))


                return Response(configure_qp_data)
        except Exception as e:
            print('1147=-=-', e)
            errorlog.error(json.dumps({'school_id':request.user.profile.school_id,'action':'Generate_QP','event_id':request_data['event_id'],'datetime':str(datetime.datetime.now())},default=str))

            return Response({'api_status':False,'message':'Unable to fetch question paper','exception':str(e)})

def get_school_token():
    '''
    Function to return school_token
    If not available return string 'first_request'
    '''

    try:
        misc_obj = MiscInfo.objects.all().first()
        if misc_obj:
            return str(misc_obj.school_token)
        else:
            return 'first_request'
    except Exception as e:
        print('Exception in getting school token :',e)
        return 'first_request'

       
class LoadEvent(APIView):
    '''
    
    Class to fetch the event data from central  server

    Input parameter
    ```````````````

    {
        "school_id" : 30488
    }

    '''

    # if AUTH_ENABLE:
    #     permission_classes = (IsAuthenticated,) # Allow only if authenticated

    def post(self,request,*args, **kwargs):
        try :
            
            cn = connection()

            if cn == None:
                data = {}
                data['api_status'] = False
                data['message'] = 'School server Not reachable'
                return Response(data)
            
            mycursor = cn.cursor()

            query = f"SELECT {AUTH_FIELDS['school']['school_id']} FROM {AUTH_FIELDS['school']['auth_table']} LIMIT 1"
            mycursor.execute(query)
            school_id_response = mycursor.fetchall()

            if len(school_id_response) == 0:
                return Response({'api_status':False,'message':'Registeration data not loaded yet'})

            print('School id :',school_id_response[0][0])

            
            # school_id = 30488
            req_url = f"{CENTRAL_SERVER_IP}/scheduler/get-events"
       
            school_id = school_id_response[0][0]
            payload = {
                "school_id" : school_id,
                "school_token":get_school_token()
            }

            print('-------payload------',payload)


            #get_events_response = requests.request("POST", req_url, data=payload)
            # get_events_response = requests.request("POST", req_url, data=payload, verify=CERT_FILE, stream = True)

            session = requests.Session()
            session.mount(CENTRAL_SERVER_IP, central_server_adapter)
            try:
                get_events_response = session.post(req_url,data = payload,verify=CERT_FILE,stream=True)
            
            except ConnectionError as ce:
                print('Request error',ce)
                return Response({'api_status':False,'message':'Error 101 - Kindly check your internet connection'})

            # print('get_event____',get_events_response)

            # try:
            #     get_events_response_json = get_events_response.json()
            # except Exception as e:
            #     print('Exception in get events response ',e)

            # print('Get Events Response JSON',get_events_response_json)

            # print('```````````````',get_events_response_json['api_status'])

            # if get_events_response_json['api_status'] == False:
            #     return Response(get_events_response_json)

            # print('1--------------')

            # Check if school has no events

            if get_events_response.headers.get('content-type') == 'application/json':
                if 'md5sum' in get_events_response.json():
                    if get_events_response.json()['md5sum'] == 'None':
                        if MiscInfo.objects.all().count() == 0:
                            MiscInfo.objects.create(event_dt = datetime.datetime.now())
                        else :
                            misc_obj = MiscInfo.objects.all().first()
                            misc_obj.event_dt = datetime.datetime.now()
                            misc_obj.save()
                        return Response({'api_status':True,'message':'No Events allocated for this school yet','school_token':get_school_token()})

            print('Content Disposition',get_events_response.headers.get('Content-Disposition'))
            if get_events_response.headers.get('Content-Disposition') == None:
                return Response({'api_status':True,'message':'No Events allocated to this school','school_token':get_school_token()})


            res_md5sum = get_events_response.headers.get('md5sum')
            res_fname = get_events_response.headers.get('Content-Disposition').split('=')[1]
            request_type = get_events_response.headers.get('process_str')

            event_id_list = get_events_response.headers.get('event_id_list')
            if type(event_id_list) != list:
                event_id_list = eval(event_id_list)

            participants_pk_list = get_events_response.headers.get('participants_pk_list')
            if type(participants_pk_list) != list:
                participants_pk_list = eval(participants_pk_list)


            print(res_fname, res_md5sum)
            load_event_base = os.path.join(MEDIA_ROOT, 'eventdata')
            file_path = os.path.join(load_event_base, res_fname.strip())
            #eventpath = file_path.split(res_fname)[0]
            eventpath = os.path.join(file_path.split(res_fname)[0],'tn_school_event')

            print(file_path, '-=--=--', eventpath)

            if not os.path.exists(eventpath):
                os.makedirs(eventpath)
            # regpath = os.path.join(file_path.split(res_fname)[0],'eventdata')
            print('status code :',get_events_response.status_code)


            #filed = requests.request('GET',CMSPATH%courses[1],verify=False, stream = True )

            with open(file_path,'wb') as fle:
                for chunk in get_events_response.iter_content(chunk_size=8192):
                    if chunk:
                        #print('------abc--------')
                        fle.write(chunk)
            get_events_response.close()

            print('status code :',get_events_response.status_code == 200)

            if get_events_response.status_code != 200:
                return Response({'api_status':False,'message':'Unable to load event data','error':'Status not equal to 200'})

            with open(file_path,"rb") as f:
                bytes_file = f.read() # read file as bytes_file
                readable_hash = hashlib.md5(bytes_file).hexdigest();
                print('~~~~~~~~~~~~~',readable_hash)
            print(res_md5sum)

            if readable_hash != res_md5sum:
                return Response({'api_status':False,'message':'Unable to load event data','error':'mismatch in md5checksum'})
            else:
                print('md5checksum correct')

            # try:
            #     with open(file_path,'wb') as f:
            #         f.write(get_events_response.content)
            # except Exception as e:
            #     print('Exception in storing events zip file :',e)

            with py7zr.SevenZipFile(file_path, mode='r') as z:
                z.extractall(path=eventpath)
            


            base_sqlite_path = DATABASES['default']['NAME']
            print('DB name :',base_sqlite_path)

            eventcsvpath = eventpath #os.path.join(eventpath,'tn_school_event')

                        #Drop table
            # for file in os.listdir(eventcsvpath):
            #     if file.endswith(".csv"):
            #         csv_full_path = os.path.join(eventcsvpath,file)
            #         table_name = os.path.basename(csv_full_path).split('.')[0]
            #         with sqlite3.connect(base_sqlite_path) as conn:
            #             c = conn.cursor()
            #             c.executescript(f"DROP TABLE IF EXISTS {table_name}")
            #         conn.commit()
            # print('Dropped old tables')

            # # Load schema
            # for file in os.listdir(eventcsvpath):
            #     if file.endswith(".sql"):
            #         schema_path = os.path.join(eventcsvpath, file)
            #         # load schema
            #         with sqlite3.connect(base_sqlite_path) as conn:
            #             c = conn.cursor()
            #             with open(schema_path,'r') as file:
            #                 content = file.read()
            #             c.executescript(content)
            #         conn.commit()
            # print('Loaded the schema')

            # Load data
            for file in os.listdir(eventcsvpath):
                if file.endswith(".csv"):
                    csv_full_path = os.path.join(eventcsvpath,file)
                    table_name = os.path.basename(csv_full_path).split('.')[0]
                    #if os.stat(csv_full_path).st_size != 0:
                    try:
                        df = pd.read_csv(csv_full_path)
                        with sqlite3.connect(base_sqlite_path) as conn:
                            c = conn.cursor()
                            df.to_sql(table_name,conn,if_exists='replace')
                            print('Data inserted successfully for :',table_name)
                            conn.commit()
                    except Exception as e:
                        print(f"Exception : {e}")
            print('Loaded the csv file')

            print('Deleting all the file in ',eventpath)
            os.system(f"rm -rf {eventpath}")

            # send ack to central server

            ack_url = f"{CENTRAL_SERVER_IP}/exammgt/acknowledgement-update"

            ack_payload = json.dumps({
                "school_id" : school_id_response[0][0],
                "request_type":request_type,
                "zip_hash":res_md5sum,
                "school_token":get_school_token(),
                "event_id_list":event_id_list,
                "participants_pk_list" : participants_pk_list
            },default=str)

            print('@@@@@ ack_payload',ack_payload)

            # requests.request("POST", ack_url, data=ack_payload,verify=CERT_FILE)
            
            session = requests.Session()
            session.mount(CENTRAL_SERVER_IP, central_server_adapter)

            try:
                get_events_response = session.post(ack_url,data = ack_payload,verify=CERT_FILE)
            
            except ConnectionError as ce:
                print('Request error',ce)

            # Deleting the residual files

            shutil.rmtree(load_event_base,ignore_errors=False,onerror=None)

            if MiscInfo.objects.all().count() == 0:
                MiscInfo.objects.create(event_dt = datetime.datetime.now())
            else :
                misc_obj = MiscInfo.objects.all().first()
                misc_obj.event_dt = datetime.datetime.now()
                misc_obj.save()


            api_log.info(json.dumps({'school_id':school_id_response[0][0],'action':'Load_event','datetime':str(datetime.datetime.now())},default=str))

            return Response({'api_status':True,'message':'Event data loaded','school_token':get_school_token()})
        except Exception as e:
            print(f'Exception raised while loading event data : {e}')

            api_errorlog.error(json.dumps({'school_id':school_id_response[0][0],'action':'Load_event','exception':str(e),'datetime':str(datetime.datetime.now())},default=str))

            return Response({'api_status':False,'message':'unable to fetch events','exception':f'Exception raised while loading event data : {e}','school_token':get_school_token()})

class LoadReg(APIView):

    '''
    class to load the registerations data
    '''
    def post(self,request,*args, **kwargs):
        try :

            # Extration of 7zip file

            req_url = f"{CENTRAL_SERVER_IP}/exammgt/registeration-data"

            print('Load registeration url',req_url)

            if get_school_token() == 'first_request':
                renewal_status = False
            else:
                renewal_status = True

            if renewal_status == False:
                payload = json.dumps({
                    "udise_code" : request.data['udise'],
                    "name":request.data['name'],
                    "mobile_no":request.data['mobileno'],
                    "school_token":get_school_token(),
                    "renewal":renewal_status

                },default=str)
            else:
                
                # Allow only HM to update credentials 
                if request.user.profile.usertype not in ['hm','superadmin_user','school']:
                    return Response ({'api_status':False,'message':'Only HM/school is authorized for update credentials'})

                payload = json.dumps({
                    "udise_code" : request.user.profile.udise_code,
                    "school_token":get_school_token(),
                    "renewal":renewal_status
                },default=str)
                
            # get_events_response = requests.request("POST", reqUrl, data=payload)

            session = requests.Session()
            session.mount(CENTRAL_SERVER_IP, central_server_adapter)

            try:
                get_events_response = session.post(req_url,data = payload,verify=CERT_FILE,stream=True)
            
            except ConnectionError as ce:
                print('Request error',ce)
                return Response({'api_status':False,'message':'Error 101 - Kindly check your internet connection'})

            # get_events_response = requests.request("POST", req_url, data=payload, verify=CERT_FILE, stream = True)

            if get_events_response.headers.get('content-type') == 'application/json':
                return Response(get_events_response.json())

            res_fname = get_events_response.headers.get('Content-Disposition').split('=')[1]
            res_md5sum = get_events_response.headers.get('md5sum')
            request_type = get_events_response.headers.get('process_str')
            school_token = get_events_response.headers.get('school_token')
            school_id = get_events_response.headers.get('school_id')
            
            print('Fetched Credential_s school id',school_id)

            print(res_fname, res_md5sum)

            # os.system()

            load_reg_base = os.path.join(MEDIA_ROOT, 'regdata')

            file_path = os.path.join(load_reg_base, res_fname.strip())
            #file_path = os.path.join(MEDIA_ROOT, 'regdata', "regdata.7z")

            print(file_path, '-=--=--', file_path.split(res_fname)[0])
            # check the path exists to check
            # if os.path.exists(file_path.split(res_fname)[0]):
            #     os.mkdir(file_path.split(res_fname)[0])

            
            if not os.path.exists(file_path.split(res_fname)[0]):
                os.makedirs(file_path.split(res_fname)[0])

            print('status code :',get_events_response.status_code)
            # try:
            #     with open(file_path,'wb') as f:
            #         f.write(get_events_response.content)
            # except Exception as e:
            #     print('Exception in storing registeration zip file :',e)

            with open(file_path,'wb') as fle:
                for chunk in get_events_response.iter_content(chunk_size=8192):
                    if chunk:
                        #print('------abc--------')
                        fle.write(chunk)
            get_events_response.close()

            print('status code :',get_events_response.status_code == 200)

            if get_events_response.status_code != 200:
                return Response({'api_status':False,'message':'Unable to load event data','error':'Status not equal to 200'})

            with open(file_path,"rb") as f:
                bytes_file = f.read() # read file as bytes_file
                readable_hash = hashlib.md5(bytes_file).hexdigest();
                print('~~~~~~~~~~~~~',readable_hash)
            print(res_md5sum)

            if readable_hash != res_md5sum:
                return Response({'api_status':False,'message':'Unable to load event data','error':'mismatch in md5checksum'})
            else:
                print('md5checksum correct')

            print('~~~~~~~~~~~~')

            # events_response_data = get_events_response.json()

            regpath = os.path.join(file_path.split(res_fname)[0],'tn_registeration_data')

            #regpath=file_path.split(res_fname)[0]

            # print('--- regpath',regpath)
            # if os.path.isdir(regpath):
            #     for f in os.listdir(regpath):
            #         os.remove(os.path.join(regpath, f))
            
            with py7zr.SevenZipFile(file_path, mode='r') as z:
                z.extractall(path=regpath)
            


            print('DB name :',DATABASES['default']['NAME'])

            base_sqlite_path = DATABASES['default']['NAME']

            print('---------')

            print('List of file',os.listdir(regpath))

            #regcsvpath = os.path.join(regpath,'tn_registeration_data')
            regcsvpath = regpath

            # #Drop table
            # for file in os.listdir(regcsvpath):
            #     if file.endswith(".csv"):
            #         csv_full_path = os.path.join(regcsvpath,file)
            #         table_name = os.path.basename(csv_full_path).split('.')[0]
            #         with sqlite3.connect(base_sqlite_path) as conn:
                    
            #             c1 = conn.cursor()
            #             c1.executescript(f"DROP TABLE IF EXISTS {table_name}")
            #             conn.commit()
            # c1.close()
            # print('Dropped old tables')

            # # Load schema
            # for file in os.listdir(regcsvpath):
            #     if file.endswith(".sql"):
            #         schema_path = os.path.join(regcsvpath, file)
            #         # load schema
            #         with sqlite3.connect(base_sqlite_path) as conn:
            #             c2 = conn.cursor()
            #             with open(schema_path,'r') as file:
            #                 content = file.read()
            #             c2.executescript(content)
            #             conn.commit()
            # c2.close()
            # print('Loaded the schema')

            # # Load data
            # for file in os.listdir(regcsvpath):
            #     if file.endswith(".csv"):
            #         csv_full_path = os.path.join(regcsvpath,file)
            #         table_name = os.path.basename(csv_full_path).split('.')[0]
            #         df = pd.read_csv(csv_full_path)
            #         with sqlite3.connect(base_sqlite_path) as conn:
            #             c3 = conn.cursor()
            #             df.to_sql(table_name,conn,if_exists='replace')
            #             print('Data inserted successfully for ;',table_name)
            #             conn.commit()
            # c3.close()
            # print('Loaded the csv file')
            with transaction.atomic():
                conn = sqlite3.connect(base_sqlite_path)
                con = conn.cursor()
                for file in os.listdir(regcsvpath):
                    if file.endswith(".csv"):
                        csv_full_path = os.path.join(regcsvpath,file)
                        table_name = os.path.basename(csv_full_path).split('.')[0]
                        
                        con.execute(f"DROP TABLE IF EXISTS {table_name}")
                        conn.commit()

                    elif file.endswith(".sql"):
                        schema_path = os.path.join(regcsvpath, file)
                        with open(schema_path,'r') as file:
                            content = file.read()

                        con.execute(content)
                        conn.commit()


                # Load data
                for file in os.listdir(regcsvpath): 
                    if file.endswith(".csv"):
                        csv_full_path = os.path.join(regcsvpath,file)
                        table_name = os.path.basename(csv_full_path).split('.')[0]
                        df = pd.read_csv(csv_full_path)
                
                        df.to_sql(table_name,conn,if_exists='replace', index=False)
                        conn.commit()
            
                print('Loaded the csv file')

                conn.close()

            cn = connection()

            if cn == None:
                data = {}
                data['api_status'] = False
                data['message'] = 'School server Not reachable'
                return Response(data)
            
            mycursor = cn.cursor()

            query = f"SELECT {AUTH_FIELDS['school']['school_id']} FROM {AUTH_FIELDS['school']['auth_table']} LIMIT 1"
            mycursor.execute(query)
            school_id_response = mycursor.fetchall()

            if len(school_id_response) == 0:
                return Response({'api_status':False,'message':'Registeration data not loaded yet'})


            print('-----print---token-----',get_school_token(),'-------------')

            

            # Delete residual files
            shutil.rmtree(load_reg_base,ignore_errors=False,onerror=None)

            # Create groups
            group_names = ['student', 'teacher', 'hm', 'department', 'superadmin_user', 'school']

            for gname in group_names:
                try:
                    obj,created = Group.objects.get_or_create(name=gname)
                    print(f'Created Group : {gname}')

                    if obj is None or created==False:
                       print(f'Error while creating group: {gname} - {obj}- {created}')
                
                except Exception as e:
                    print(f'Exception in creating groups :{gname} -> {e}')



            # try:
            #     if not Group.objects.filter(name='student').exists():
            #         Group.objects.create(name='student')
            #     if not Group.objects.filter(name='teacher').exists():
            #         Group.objects.create(name='teacher')
            #     if not Group.objects.filter(name='hm').exists():
            #         Group.objects.create(name='hm')
            #     if not Group.objects.filter(name='department').exists():
            #         Group.objects.create(name='department')
            #     if not Group.objects.filter(name='superadmin_user').exists():
            #         Group.objects.create(name='superadmin_user')
            #     if not Group.objects.filter(name='school').exists():
            #         Group.objects.create(name='school')

            #     print('^^^Created Groups^^^^')
            # except Exception as e:
            #     print('Exception in creating groups :',e)

            if MiscInfo.objects.all().count() == 0:
                MiscInfo.objects.create(reg_dt = datetime.datetime.now(),school_token=school_token)
            else :
                misc_obj = MiscInfo.objects.all().first()
                misc_obj.reg_dt = datetime.datetime.now()
                misc_obj.school_token = school_token
                misc_obj.save()


            # Deleting old logins
            try:
                User.objects.all().delete()
            except Exception as  e:
                print('Exception in deleting old user\'s entry')

            # Creation of superuser
            print('create superuser')
            suser = User.objects.create_superuser(username=SUPER_USERNAME,password=SUPER_PASSWORD)
            suser.save()

            profile_instance = Profile.objects.create(user=suser)

            auth_fields = AUTH_FIELDS

            cn = connection()

            if cn == None:
                data = {}
                data['api_status'] = False
                data['message'] = 'School server Not reachable'
                return Response(data)
            

            mycursor = cn.cursor()

            query = f"SELECT {auth_fields['school']['school_id']}, {auth_fields['school']['district_id']}, {auth_fields['school']['block_id']}, {auth_fields['school']['udise_code']} FROM {auth_fields['school']['auth_table']} LIMIT 1"
            print('Fetch school details query :',query)
            mycursor.execute(query)
            school_detail_response = mycursor.fetchall()
    
            profile_instance.priority       = AUTH_FIELDS['superadmin_user']['superadmin_user_priority']
            profile_instance.name_text      = SUPER_USERNAME
            profile_instance.usertype       = 'superadmin_user'
            profile_instance.udise_code     = school_detail_response[0][3]
            profile_instance.district_id    = school_detail_response[0][1]
            profile_instance.block_id       = school_detail_response[0][2]
            profile_instance.school_id      = school_detail_response[0][0]

            profile_instance.save()

            my_group = Group.objects.get(name='superadmin_user') 
            my_group.user_set.add(suser)

            # send ack to central server

            ack_url = f"{CENTRAL_SERVER_IP}/exammgt/acknowledgement-update"

            ack_payload = json.dumps({
                "school_id" : school_id_response[0][0],
                "request_type":request_type,
                "zip_hash":res_md5sum,
                "school_token":get_school_token()
            },default=str)

            session = requests.Session()
            session.mount(CENTRAL_SERVER_IP, central_server_adapter)

            try:
                load_reg_ack = session.post(ack_url,data = ack_payload,verify=CERT_FILE)
            
            except Exception as e:
                print('Error in sending ack',str(e))
                api_errorlog.error(json.dumps({'school_id':school_id_response[0][0],'action':'registration_ack','datetime':str(datetime.datetime.now()),'exception':str(e)},default=str))

            # Logging the school_id, action and datetime to the api_log.info file.
            if renewal_status:
                api_log.info(json.dumps({'school_id':school_id_response[0][0],'username':request.user.username,'action':'Load_registeration_renewal','datetime':str(datetime.datetime.now())},default=str))
            else:
                api_log.info(json.dumps({'school_id':school_id_response[0][0],'action':'Load_registeration','datetime':str(datetime.datetime.now())},default=str))


            return Response({'api_status':True,'message':'Registeration data loaded'})
        except Exception as e:
            print(f'Exception raised while load registeration data throught API : {e}')

            if renewal_status:
                api_errorlog.error(json.dumps({'school_id':school_id_response[0][0],'username':request.user.username,'action':'Load_registeration_renewal','datetime':str(datetime.datetime.now()),'exception':str(e)},default=str))
            else:
                api_errorlog.error(json.dumps({'school_id':school_id_response[0][0],'action':'Load_registeration','datetime':str(datetime.datetime.now()),'exception':str(e)},default=str))


            return Response({'api_status':False,'message':'Error in Registeration','exception':f'Exception raised while load registeration data throught API : {e}'})

class InitialReg(APIView):
    '''
    Class to fetch the school information 
    
    '''
    def post(self,request,*args, **kwargs):
        try:
            data = JSONParser().parse(request)
            #data = {'udise_code':33150901903}

            if 'udise_code' not in data:
                return Response({'api_status':False,'message':'udise_code not provided'})
            
            req_url = f"{CENTRAL_SERVER_IP}/exammgt/udise-info"

            payload = json.dumps({"udise_code": data['udise_code']},default=str)
            
            session = requests.Session()
            session.mount(CENTRAL_SERVER_IP, central_server_adapter)

            try:
                get_udise_response = session.post(req_url,data = payload,verify=CERT_FILE)
            
                if get_udise_response.status_code != 200:
                    return Response({'api_status':False,'message':'Central server not reachable'})
            except Exception as e:
                return Response({'api_status':False,'message':'Error in fetching data from Central server','exception':str(e)})
            udise_response_json = get_udise_response.json()

            api_log.info(json.dumps({'udise_code':data['udise_code'],'action':'School_initial_info','datetime':str(datetime.datetime.now())},default=str))
            
            return Response(udise_response_json)
        
        except Exception as e:

            print('Exception caused during Initial Registeration :',e)
            
            api_errorlog.error(json.dumps({'udise_code':data['udise_code'],'action':'School_initial_info','datetime':str(datetime.datetime.now()),'exception':str(e)},default=str))
            
            return Response({'api_status':False,'message':'Exception caused during Initial Registeration'})

def load_question_choice_data(qpdownload_list):
    for img_data in qpdownload_list['questions']:
        question = {}
        choice = {}
        questions_filter  = {
                            "qid" : img_data['qid']
                    }
        questions_object_edit = Question.objects.filter(**questions_filter)
        if len(questions_object_edit) == 0:
            question['qid'] = img_data['qid']
            question['qimage'] = img_data['qimage']
            question['no_of_choices'] = img_data['no_of_choices']
            question['correct_choice'] = img_data['correct_choice']

            serialized_questions = QuestionsSerializer(data=question,many=False)
            if serialized_questions.is_valid():
                serialized_questions.save()
                for ch_image_data in img_data['q_choices']:
                    
                    if Choice.objects.filter(cid = ch_image_data['cid']).exists():
                        print(f"Choice ID {ch_image_data['cid']} already exists")
                        continue


                    choice['qid'] = img_data['qid']
                    choice['cid'] = ch_image_data['cid']
                    choice['cimage'] = ch_image_data['cimage']
                    
                    serialized_choice= ChoicesSerializer(data=choice,many=False)
                    if serialized_choice.is_valid():
                            serialized_choice.save()
                            
                    else:
                        print(f'Error in serialization of choices : {serialized_choice.errors}')
                        return Response({"api_status":False,"message":"Incorrect data in serializing choices","error":serialized_choice.errors})
            else:
                print(f'Error in serialization of questions : {serialized_questions.errors}')
                return Response({"api_status":False,"message":"Incorrect data in serializing questions","error":serialized_questions.errors})
        else:
            print('\n')
            print('-----------------------------------------------------------')
            print('Question ID is already present into school local database....')
            
            print('-----------------------------------------------------------')


class MetaData(APIView):

    '''
    
    API class request qp from the central server
    
    '''


    if AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated

    def post(self,request,*args, **kwargs):
        try :

            with transaction.atomic():
            
                cn = connection()

                if cn == None:
                    data = {}
                    data['api_status'] = False
                    data['message'] = 'School server Not reachable'
                    return Response(data)
                
                mycursor = cn.cursor()


                query = f"SELECT {AUTH_FIELDS['school']['school_id']} FROM {AUTH_FIELDS['school']['auth_table']} LIMIT 1"
                mycursor.execute(query)
                school_id_response = mycursor.fetchall()

                if len(school_id_response) == 0:
                    return Response({'api_status':False,'message':'Registeration data not loaded yet'})

                # request_data = JSONParser().parse(request)
                request_data = request.data


                participant_pk = request_data['participant_pk']
                '''
                if "participant_pk" in request_data:
                    participant_pk = request_data['participant_pk']
                else:
                    participant_pk = None
                '''


                #reg_data = JSONParser().parse(request)

                #print(request_data)

                #print('-------------------------')

                
                if scheduling.objects.filter(schedule_id=request_data['event_id']).exists() == False:
                    return Response({'api_status':False,'message':'Event Not allocated for this school'})

                
                scheduling_queryset = scheduling.objects.get(schedule_id=request_data['event_id'])


                try:
                    participant_category = participants.objects.filter(schedule_id = request_data['event_id'], id = participant_pk)[0].participant_category
                    #participant_pk = participants.objects.filter(schedule_id = request_data['event_id'])[0].id
                except:
                    participant_category = None

                if participant_category == 'STUDENT':
                    participant_id = None
                else:
                    participant_id = participants.objects.get(schedule_id = request_data['event_id'], id = participant_pk).participant_id


                #qpdownload-from-s3bucket
                req_url = f"{CENTRAL_SERVER_IP}/paper/qpdownload"
                s3_req_url = f"{CENTRAL_SERVER_IP}/paper/qpdownload-from-s3bucket"
                payload = json.dumps({
                    'event_id':request_data['event_id'],
                    'school_id':school_id_response[0][0],
                    'participant_id' : participant_id,
                    'participant_pk' : participant_pk,
                    'school_token':get_school_token()
                },default=str)

            
                print('Request to the central server to download',str(payload))

                json_base_path =  os.path.join(MEDIA_ROOT, 'examdata')
                load_meta_base = os.path.join(MEDIA_ROOT, 'examdata')
                if not os.path.exists(json_base_path):
                    os.mkdir(json_base_path)

                zip_base_path = os.path.join(json_base_path, f"{request_data['event_id']}_{school_id_response[0][0]}_{participant_pk}_qpdownload_json")
                
                timestr = time.strftime("%Y_%m_%d_%H_%M_%S")
                actualfile = f'{zip_base_path}_{timestr}.7z'

                # get_meta_response = requests.request("POST", req_url, data=payload, verify=CERT_FILE, stream = True)

                session = requests.Session()
                session.mount(CENTRAL_SERVER_IP, central_server_adapter)

    
                try:
                    get_meta_response = session.post(s3_req_url,data = payload,verify=CERT_FILE,stream=True)
                    
                except ConnectionError as ce:
                    print('Request error',ce)

       
                if get_meta_response.json()['api_status'] == True:
                    hashvalue = get_meta_response.json()['hashvalue']
                    reference_url = get_meta_response.json()['reference_url']
                    request_type = get_meta_response.json()['process_str']
                    res_md5sum = hashvalue

                    #file_response = requests.get(f"{S3BUCKET_REF_URL}/{reference_url}")

                    file_response = requests.get(f"{reference_url}")
                    md5sum_value =  hashlib.md5(file_response.content).hexdigest()
                    
                    SOURCE_URL =  get_meta_response.json()['process_url']
                    if md5sum_value == hashvalue:
                        print('md5checksum correct')

                        # with open(actualfile, 'wb') as f:
                        #     f.write(file_response.content)

                        with open(actualfile,'wb') as fle:
                            for chunk in file_response.iter_content(chunk_size=8192):
                                if chunk:
                                    fle.write(chunk)
                        get_meta_response.close()

                    else:
                        print('md5checksum incorrect')

            
                elif get_meta_response.json()['api_status'] == False:
                    try:
                        get_meta_response = session.post(req_url,data = payload,verify=CERT_FILE,stream=True)
                        
                    except ConnectionError as ce:
                        print('Request error',ce)

                    SOURCE_URL =  get_meta_response.headers.get('process_url')
                
    

                if SOURCE_URL != 'S3Bucket':
                    print(f"source url : {req_url}")
 
                    if get_meta_response.headers.get('content-type') == 'application/json':
                        get_meta_response_json = get_meta_response.json()
                        if get_meta_response_json['api_status'] == False:
                            return Response({'api_status':False,'message':'Question paper not available in central server'})

                    if get_meta_response.headers.get('Content-Disposition') == None:
                        return Response({'api_status':True,'message':'No Meta allocated to this school','school_token':get_school_token()})

                    if get_meta_response.status_code != 200:
                        return Response({'api_status':False,'message':'Unable to load exam data','error':'Status not equal to 200'})
                    
                    res_fname = get_meta_response.headers.get('Content-Disposition').split('=')[1]
                    res_md5sum = get_meta_response.headers.get('md5sum')
                    request_type = get_meta_response.headers.get('process_str')

                    print(res_fname, res_md5sum)

                    # Delete residual files
                    file_path = os.path.join(load_meta_base, res_fname.strip())
                    questionpath = os.path.join(file_path.split(res_fname)[0],f"{request_data['event_id']}_{school_id_response[0][0]}_qpdownload_json")

                    if not os.path.exists(questionpath):
                        os.makedirs(questionpath)

                    with open(file_path,'wb') as fle:
                        for chunk in get_meta_response.iter_content(chunk_size=8192):
                            if chunk:
                                #print('------abc--------')
                                fle.write(chunk)
                    get_meta_response.close()

                    with open(file_path,"rb") as f:
                        bytes_file = f.read() # read file as bytes_file
                        readable_hash = hashlib.md5(bytes_file).hexdigest();
                        #print('~~~~~~~~~~~~~',readable_hash)
                    #print(res_md5sum)

                    if readable_hash != res_md5sum:
                        return Response({'api_status':False,'message':'Unable to load exam data','error':'mismatch in md5checksum'})
                    else:
                        print('md5checksum correct')


                else:
                    print(f"source url : {s3_req_url}")

                    file_path = actualfile
                    questionpath = zip_base_path

    

                with py7zr.SevenZipFile(file_path, mode='r') as z:
                    z.extractall(path=questionpath)
                

                base_sqlite_path = DATABASES['default']['NAME']
                print('DB name :',base_sqlite_path)
                json_file_path = questionpath #os.path.join(questionpath,f"{request_data['event_id']}_{school_id_response[0][0]}_qpdownload_json")

                # print('question path',questionpath)
                # print('json file path',json_file_path)
                for file in os.listdir(json_file_path):
                    if file.startswith('meta'):
                        # print('File :',file)
                        print('full path :',os.path.join(json_file_path,file))
                        with open(os.path.join(json_file_path,file), 'r') as f:
                            meta_data = json.load(f)
                # print(meta_data)

                event_meta_data = {}
                # event_meta_data['event_id'] = meta_data['event_id']
                # event_meta_data['participant_pk'] = meta_data['participant_pk']
                event_meta_data['event_id'] = meta_data['participant_pk']
                event_meta_data['participant_pk'] = meta_data['event_id']
                event_meta_data['subject'] = meta_data['subject']
                event_meta_data['no_of_questions'] = meta_data['no_of_questions']
                event_meta_data['duration_mins'] = meta_data['duration_mins']
                
                event_meta_data['qtype'] = meta_data["qtype"]
                event_meta_data['total_marks'] = meta_data['total_marks']
                event_meta_data['no_of_batches'] = meta_data['no_of_batches']
                event_meta_data['qshuffle'] = meta_data['qshuffle']
                event_meta_data['show_submit_at_last_question'] = meta_data['show_submit_at_last_question']
                event_meta_data['show_summary'] = meta_data['show_summary']
                event_meta_data['show_result'] = meta_data['show_result']
                event_meta_data['end_alert_time'] = meta_data['end_alert_time']
                event_meta_data['show_instruction'] = meta_data['show_instruction']
                if len(meta_data['school_qp_sets']) == 0:
                    return Response({"api_status":False,"message":"Question id not available in qp set"})
                else:
                    event_meta_data['qp_set_list'] = str(meta_data['school_qp_sets'])
                # event_meta_data['qp_set_list'] = str(meta_data['school_qp_sets'])
                # print('~~~~~~~~~~~~~~~~~~~')
                # print(event_meta_data)

                iit_qp_set_list = []
                iit_question_id_list = []
                for meta in meta_data['qp_set_list']:
                    iit_qp_set_list.append(meta['qp_set_id'])
                    qp_list = meta['question_id_list']
                    iit_question_id_list.append(qp_list)

                # event_meta_data['qp_set_list'] = str(iit_qp_set_list) #we need string for store into database
                # print('--------',event_meta_data)

                #print('-----------event---meta-----data-----',event_meta_data)

            
                qp_set_data = []
                for qp_set, q_id in zip(iit_qp_set_list, iit_question_id_list):
                    tmp_dict_data = {}
                    tmp_dict_data['qp_set_id'] = qp_set
                    tmp_dict_data['q_ids'] = q_id
                    qp_set_data.append(tmp_dict_data)
                
                event_meta_data['qp_set_data'] = qp_set_data

                # Push the exam_meta_object_edit
                exam_meta_filter  = {
                    "event_id" : request_data['event_id'],
                    "participant_pk" : participant_pk
                
                    }
                
                event_meta_data['event_title'] = scheduling_queryset.event_title
                event_meta_data['class_std'] = scheduling_queryset.class_std
                event_meta_data['class_section'] = scheduling_queryset.class_section
                event_meta_data['event_startdate'] = scheduling_queryset.event_startdate
                event_meta_data['event_enddate'] = scheduling_queryset.event_enddate
                event_meta_data['class_subject'] = scheduling_queryset.class_subject


                for qp_data in event_meta_data['qp_set_data']:
                        tmp_qp_sets_data = {}
                        tmp_qp_sets_data['event_id'] = event_meta_data['event_id']
                        tmp_qp_sets_data['qp_set_id'] = qp_data['qp_set_id']
                        tmp_qp_sets_data['qid_list'] = str(qp_data['q_ids'])
                        
                    
                        qp_sets_filter  = {
                                        "qp_set_id" : qp_data['qp_set_id'],
                                        "event_id" : request_data['participant_pk']
                                    }
                        
                        qp_set_object_edit = QpSet.objects.filter(**qp_sets_filter)
                        if len(qp_set_object_edit) == 0:
                            serialized_qp_sets = QpSetsSerializer(data=tmp_qp_sets_data,many=False)
                            if serialized_qp_sets.is_valid():
                                serialized_qp_sets.save()
                                
                            else:
                                print(f'Error in serialization of QP Sets : {serialized_qp_sets.errors}')
                                return Response({"api_status":False,"message":"Incorrect data in serializing QP Sets","error":serialized_qp_sets.errors})
                        else:
                            print('\n')
                            print('-----------------------------------------------------------')
                            print('QP SET ID is already present into school local database....')
                            
                            print('-----------------------------------------------------------')

                #Read the question .json -> Qpset, Question and Choices
                for file in os.listdir(json_file_path):
                    if file.startswith('qpdownload'):
                        # print('File :',file)
                        #print('full path :',os.path.join(json_file_path,file))
                        with open(os.path.join(json_file_path,file), 'r+', encoding="utf-8") as f:
                            qpdownload_list = json.load(f)

                        #print(qpdownload_list)
                        try:
                            load_question_choice_data(qpdownload_list)
                        except Exception as e:
                            return Response({'api_status':False,'message':'Error reading json meta data...!','exception':str(e)})


                ack_url = f"{CENTRAL_SERVER_IP}/exammgt/acknowledgement-update"

                ack_payload = json.dumps({
                    "school_id" : school_id_response[0][0],
                    "request_type":request_type,
                    "zip_hash":res_md5sum,
                    "school_token":get_school_token(),
                    "participant_pk" : participant_pk,
                    "event_id_list":[request_data['event_id']]
                },default=str)

                # requests.request("POST", ack_url, data=ack_payload, verify=CERT_FILE) 
                session = requests.Session()
                session.mount(CENTRAL_SERVER_IP, central_server_adapter)

                try:
                    get_events_response = session.post(ack_url,data = ack_payload,verify=CERT_FILE)
                
                except ConnectionError as ce:
                    print('Request error',ce)
        
                os.system('rm -rf ' + json_file_path)

                # Delete residual files

                shutil.rmtree(load_meta_base,ignore_errors=False,onerror=None)

                #print('-----------event---meta-----data-----final',event_meta_data)

                exam_meta_object_edit = ExamMeta.objects.filter(**exam_meta_filter)
                if len(exam_meta_object_edit) == 0:
                    serialized_exam_meta = ExamMetaSerializer(data=event_meta_data,many=False)
                    if serialized_exam_meta.is_valid():
                        serialized_exam_meta.save()
                        
                    else:
                        print(f'Error in serialization of Exam meta data : {serialized_exam_meta.errors}')
                        return Response({"api_status":False,"message":"Incorrect data in serializing Exam Meta data","error":serialized_exam_meta.errors})

                else:
                    print('\n')
                    print('-----------------------------------------------------------')
                    print('Event ID is already present into school local database....')
                    
                    print('-----------------------------------------------------------')

                api_log.info(json.dumps({'school_id':school_id_response[0][0],'action':'Load_meta_data','datetime':str(datetime.datetime.now())},default=str))


                return Response({'api_status':True,'message':'Question paper loaded successfully'})
         
        except Exception as e:
            print(f'Exception raised while creating a meta data object throught API : {e}')

            api_errorlog.error(json.dumps({'school_id':school_id_response[0][0],'action':'Load_meta_data','datetime':str(datetime.datetime.now()),'exception':str(e)},default=str))


            return Response({"api_status":False,"message":"Error in fetching meta data","exception": f'{e}'})

        #     return Response({'api_status':True})
        # except Exception as e:
        #     return Response({'api_status':False,'exception':e})

class SchoolDetails(APIView):
    '''
    Class to fetch the school details from the db.students_school_child_count
    '''

    def post(self,request,*args, **kwargs):
        try:
            cn = connection()

            if cn == None:
                data = {}
                data['api_status'] = False
                data['message'] = 'School server Not reachable'
                return Response(data)
            
            field_names = ['udise_code','school_id','school_name','school_type','district_id','district_name','block_id','block_name']


            mycursor = cn.cursor()

            query = f"SELECT {','.join([str(elem) for elem in field_names])} FROM {DB_STUDENTS_SCHOOL_CHILD_COUNT} LIMIT 1;"
            print('query :',query)
            mycursor.execute(query)
            school_detail_response = mycursor.fetchall()
            print('school details :',school_detail_response[0])
            return Response({
                'udise_code':school_detail_response[0][0],
                'school_id':school_detail_response[0][1],
                'school_name':school_detail_response[0][2],
                'school_type':school_detail_response[0][3],
                'district_id':school_detail_response[0][4],
                'district_name':school_detail_response[0][5],
                'block_id':school_detail_response[0][6],
                'block_name':school_detail_response[0][7],
                'api_status':True,
                'current_date_time':str(datetime.datetime.now())
            })

        except Exception as e:
            print('No school details :',e)
            return Response({'api_status':False,'message':'No school details','current_date_time':str(datetime.datetime.now())})

class VersionNumber(APIView):
    
    '''
        GET api call to fetch the version number
    '''

    def get(self, request, *args, **kwargs):
        try:
            
            version_file_path = os.path.join(BASE_DIR,'version.txt')
            with open(version_file_path) as f:
                # version_value = f.readlines()
                version_value = [line.strip() for line in f.readlines()][0]
            
            help_link = None

            session = requests.Session()
            session.mount(CENTRAL_SERVER_IP, central_server_adapter)

            try:
                req_url = f"{CENTRAL_SERVER_IP}/scheduler/help-link"
                help_link_response = session.post(req_url,verify=CERT_FILE)

                help_link = help_link_response.json()['data']
            except:
                pass

            try:
                school_hostname = os.uname()[1]
            except Exception as e:
                school_hostname = None
                print('Exception caused while geting hostname :',e)
            
            try:
                cn = connection()

                if cn == None:
                    data = {}
                    data['api_status'] = False
                    data['message'] = 'School server Not reachable'
                    return Response(data)
                
            
                mycursor = cn.cursor()
                query = f"SELECT udise_code FROM {DB_STUDENTS_SCHOOL_CHILD_COUNT} LIMIT 1;"
                mycursor.execute(query)
                school_detail_response = mycursor.fetchall()
                #print('school details :',school_detail_response[0])
                udise_code = school_detail_response[0][0]

            except Exception as e:
                udise_code = None
                print('Exception caused while geting udise_code :',e)



            return Response({'api_status':True,'version':version_value, 'hostname' : school_hostname, 'udise_code':udise_code,'help_link':help_link})
        except Exception as e:
            return Response({'api_status':False,'message':'Error in fetching version number and ','exception':str(e)})



class ConsSummary(APIView):
    '''
    Class to fetch display all candidates details and exam result for the particular event

    input parameter
    ```````````````

    event_id <- schedule_id or event_id

    participant_pk <- primary key of participant table
    
    '''

    def post(self,request,*args, **kwargs):
        try:
            cn = connection()

            if cn == None:
                data = {}
                data['api_status'] = False
                data['message'] = 'School server Not reachable'
                return Response(data)
            
            mycursor = cn.cursor()

            request_data = request.data
            print('request data :',request_data)

            scheduling_queryset = scheduling.objects.filter(schedule_id=request_data['event_id'])

            if len(scheduling_queryset) == 0:
                return Response({'api_status':False,'message':f"Schedule for event_id: {request_data['event_id']} not found !"})
            scheduling_obj = scheduling_queryset[0]

            students_query = f" SELECT l.{AUTH_FIELDS['student']['username_field']}, r.{AUTH_FIELDS['student']['name_field_master']}, r.{AUTH_FIELDS['student']['student_class']}, r.{AUTH_FIELDS['student']['section_field_master']} FROM {AUTH_FIELDS['student']['auth_table']} l LEFT JOIN {AUTH_FIELDS['student']['master_table']} r ON l.{AUTH_FIELDS['student']['school_field_foreign']} = r.{AUTH_FIELDS['student']['school_field_foreign_ref']} WHERE r.{AUTH_FIELDS['student']['student_class']} = {scheduling_obj.class_std}"
            if scheduling_obj.class_section != None:
                students_query = f"{students_query} AND r.{AUTH_FIELDS['student']['section_field_master']} = '{scheduling_obj.class_section}'"
            
            if scheduling_obj.class_group != None:
                # students_query = f"{students_query} AND r.group_code_id = {scheduling_obj.class_group.split('-')[0]}"

                if isinstance(eval(scheduling_obj.class_group), list):
                    group_list = [i.split('-')[0] for i in eval(scheduling_obj.class_group)]
                    if len(group_list) == 1:
                        group_values = f"({group_list[0]})"
                    else:
                        group_values = tuple(group_list)
                    students_query = f"{students_query} AND r.group_code_id IN {group_values}"

            
            if 'participant_pk' in request.data:
                par_qs = participants.objects.filter(id = request_data['participant_pk'])
                if len(par_qs) != 0:
                    par_obj = par_qs[0]
                    if par_obj.section != None:
                        students_query = f"{students_query} AND r.{AUTH_FIELDS['student']['section_field_master']} = '{par_obj.section}'"
            print('Student list query',students_query)
            # # Raw query (working)
            # students_query = f" SELECT l.emis_username, r.name, r.class_studying_id, r.class_section FROM emisuser_student l LEFT JOIN students_child_detail r ON l.emis_user_id = r.id WHERE r.class_studying_id = {scheduling_obj.class_std}"
            # if scheduling_obj.class_section != None:
            #     students_query = f"{students_query} AND r.class_section = '{scheduling_obj.class_section}'"
            


            # students_query = f"  SELECT emis_username,  student_name, class_studying_id, class_section FROM emisuser_student WHERE class_studying_id = {scheduling_obj.class_std} "
            # if scheduling_obj.class_section != None:
            #     students_query = f"{students_query} AND class_section = '{scheduling_obj.class_section}'"
            #students_query = f"SELECT {emisuser_student}.{auth_fields['student']['username_field']},{emisuser_student}.student_name,{emisuser_student}.class_studying_id,{emisuser_student}.class_section FROM {emisuser_student} INNER JOIN {students_child_detail} ON {emisuser_student}.emis_user_id = {students_child_detail}.id WHERE {students_child_detail}.{auth_fields['student']['student_class']} = {scheduling_obj.class_std}"
                #students_query = f"{students_query} AND {students_child_detail}.{auth_fields['student']['section_field_master']} = '{scheduling_obj.class_section}'"
            # inner_query = f"SELECT {auth_fields['student']['school_field_foreign_ref']} FROM {auth_fields['student']['master_table']} WHERE {auth_fields['student']['student_class']} = {scheduling_obj.class_std}"
            # if scheduling_obj.class_section != None:
            #     inner_query = f"{inner_query} AND {auth_fields['student']['section_field_master']} = '{scheduling_obj.class_section}'"
            # students_query = f"SELECT {auth_fields['student']['username_field']},student_name FROM {auth_fields['student']['auth_table']} WHERE {auth_fields['student']['school_field_foreign']} IN ({inner_query}) ;"

            
            
            print('students_query :',students_query)

            mycursor.execute(students_query)
            students_emis_username = mycursor.fetchall()


            # loop through each student's attendance entry if available
            consolidated_summary = []
            for student_emis in students_emis_username:
                individual_summary = {}
                individual_summary['event_id'] = request_data['event_id']
                individual_summary['emis_username'] = student_emis[0]
                individual_summary['name'] = student_emis[1]
                individual_summary['class_std'] = student_emis[2]
                individual_summary['class_section'] = student_emis[3]
                
                
                if 'participant_pk' in request.data:
                    
                    individual_summary.update(get_summary(event_id=request_data['event_id'],participant_pk = request_data['participant_pk'],student_username = individual_summary['emis_username'] ))
                else:
                    individual_summary.update(get_summary(event_id=request_data['event_id'],participant_pk = None, student_username = individual_summary['emis_username'] ))

                # print(individual_summary)
                consolidated_summary.append(individual_summary)

            print('Total number of students',len(students_emis_username))

            # return Response({'api_status':True,'data':consolidated_summary})
            return Response({'api_status':True,'data':sorted(consolidated_summary, key = lambda x: x['name'])})
        except Exception as e:
            print('Exception caused while fetching consolidated summary :',e)
            return Response({'api_status':False,'message':'Unable to fetch consolidated summary','exception':str(e)})


class GetUserDetail(APIView):

    '''

    Class to fetch the details store in Django's builtin User model and One-to-One linked Profile model

    Sample Output
    ``````````````
        "user"          : "xxxx",
        "username"      : "xxxx",
        "group"         : "xxxx",
        "usertype"      : "xxxx",
        "udise_code"    : "xxxx"

    '''

    if AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated

    def post(self,request):
        data = {}
        data['user'] = str(request.user)
        print(str(request.user) == 'AnonymousUser')
        if str(request.user) != 'AnonymousUser':
            try:
                data['username']    = request.user.username
                data['groups']      = request.user.groups.values_list('name', flat=True)[0]
                data['name_text']   = request.user.profile.name_text
                data['student_class']   = request.user.profile.student_class
                data['usertype']    = request.user.profile.usertype
                data['priority']    = request.user.profile.priority
                data['udise_code']  = request.user.profile.udise_code
                data['district_id'] = request.user.profile.district_id
                data['block_id']    = request.user.profile.block_id
                data['school_id']   = request.user.profile.school_id
            except Exception as e:
                return Response({'api_status':False,'message':'Error in fetching user details','exception':str(e)})
        return Response({"api_status":True,"content":data})


class MetaUpload(APIView):
    '''
    API class to manually upload the Meta Data

    Input parameter
    ```````````````

    event_id -> ID of the event
    archive -> Compressed 7Zip file

    
    '''
    if AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated
    def post(self, request, *args,**kwargs):
        
        try:
            event_id = request.data['event_id']

            if scheduling.objects.filter(schedule_id=event_id).exists() == False:
                return Response({'api_status':False,'message':'Event Not allocated for this school'})

            
            scheduling_queryset = scheduling.objects.get(schedule_id=event_id)

            participant_pk = participants.objects.filter(schedule_id=event_id).values()[0].get("id")

            print("participant_pk", participant_pk)

            file_obj = request.data['archive']
            file_name = file_obj.name

            file_path = os.path.join(MEDIA_ROOT,'examdata')

            if not os.path.exists(file_path):
                os.makedirs(file_path)
            
            zip_file = os.path.join(file_path,file_name)
            print('----------zipfilepath-------',zip_file)
            with open(zip_file,'wb') as fle:
                for chunk in file_obj.chunks():
                    if chunk:
                        fle.write(chunk)

            meta_path = os.path.join(file_path,event_id)

            if not os.path.exists(meta_path):
                os.makedirs(meta_path)

            with py7zr.SevenZipFile(zip_file, mode='r') as z:
                    z.extractall(path=meta_path)


            print('------Uploading Meta Data File-------',file_obj)

            json_file_path = meta_path

            meta_data = None

            for file in os.listdir(json_file_path):
                    if file.startswith('meta'):
                        # print('File :',file)
                        print('full path :',os.path.join(json_file_path,file))
                        with open(os.path.join(json_file_path,file), 'r+', encoding="utf-8") as f:
                            meta_data = json.load(f)
            print(meta_data)

            if meta_data == None:
                return Response({'api_status':False,'message':'Incorrect Mapping File'})

            print(f"--------{meta_data['event_id']}---------{event_id}")
            if meta_data['event_id'] != event_id:
                return Response({'api_status':False,'message':'Incorrect Mapping File'})

            event_meta_data = {}
            event_meta_data['event_id'] =participant_pk
            event_meta_data['participant_pk'] = meta_data['event_id']
            event_meta_data['subject'] = meta_data['subject']
            event_meta_data['no_of_questions'] = meta_data['no_of_questions']
            event_meta_data['duration_mins'] = meta_data['duration_mins']
            
            event_meta_data['qtype'] = meta_data["qtype"]
            event_meta_data['total_marks'] = meta_data['total_marks']
            event_meta_data['no_of_batches'] = meta_data['no_of_batches']
            event_meta_data['qshuffle'] = meta_data['qshuffle']
            event_meta_data['show_submit_at_last_question'] = meta_data['show_submit_at_last_question']
            event_meta_data['show_summary'] = meta_data['show_summary']
            event_meta_data['show_result'] = meta_data['show_result']
            event_meta_data['end_alert_time'] = meta_data['end_alert_time']
            event_meta_data['show_instruction'] = meta_data['show_instruction']
            if len(meta_data['school_qp_sets']) == 0:
                return Response({"api_status":False,"message":"Question id not available in qp set"})
            else:
                event_meta_data['qp_set_list'] = str(meta_data['school_qp_sets'])
            # event_meta_data['qp_set_list'] = str(meta_data['school_qp_sets'])
            print('~~~~~~~~~~~~~~~~~~~')
            print(event_meta_data)

            iit_qp_set_list = []
            iit_question_id_list = []
            for meta in meta_data['qp_set_list']:
                iit_qp_set_list.append(meta['qp_set_id'])
                qp_list = meta['question_id_list']
                iit_question_id_list.append(qp_list)

            # event_meta_data['qp_set_list'] = str(iit_qp_set_list) #we need string for store into database
            # print('--------',event_meta_data)
            
            qp_set_data = []
            for qp_set, q_id in zip(iit_qp_set_list, iit_question_id_list):
                tmp_dict_data = {}
                tmp_dict_data['qp_set_id'] = qp_set
                tmp_dict_data['q_ids'] = q_id
                qp_set_data.append(tmp_dict_data)
            
            event_meta_data['qp_set_data'] = qp_set_data

            # Push the exam_meta_object_edit
            exam_meta_filter  = {
                "event_id" : event_id
                
                }
            
            event_meta_data['event_title'] = scheduling_queryset.event_title
            event_meta_data['class_std'] = scheduling_queryset.class_std
            event_meta_data['class_section'] = scheduling_queryset.class_section
            event_meta_data['event_startdate'] = scheduling_queryset.event_startdate
            event_meta_data['event_enddate'] = scheduling_queryset.event_enddate
            event_meta_data['class_subject'] = scheduling_queryset.class_subject


            exam_meta_object_edit = ExamMeta.objects.filter(**exam_meta_filter)
            if len(exam_meta_object_edit) == 0:
                serialized_exam_meta = ExamMetaSerializer(data=event_meta_data,many=False)
                if serialized_exam_meta.is_valid():
                    serialized_exam_meta.save()
                    
                else:
                    print(f'Error in serialization of Exam meta data : {serialized_exam_meta.errors}')
                    return Response({"api_status":False,"message":"Incorrect data in serializing Exam Meta data","error":serialized_exam_meta.errors})

            else:
                print('\n')
                print('-----------------------------------------------------------')
                print('Event ID is already present into school local database....')
                
                print('-----------------------------------------------------------')


            for qp_data in event_meta_data['qp_set_data']:
                    tmp_qp_sets_data = {}
                    tmp_qp_sets_data['event_id'] = event_meta_data['event_id']
                    tmp_qp_sets_data['qp_set_id'] = qp_data['qp_set_id']
                    tmp_qp_sets_data['qid_list'] = str(qp_data['q_ids'])
                    
                
                    qp_sets_filter  = {
                                    "qp_set_id" : qp_data['qp_set_id'],
                                    "event_id" : participant_pk
                                }
                    
                    qp_set_object_edit = QpSet.objects.filter(**qp_sets_filter)
                    if len(qp_set_object_edit) == 0:
                        serialized_qp_sets = QpSetsSerializer(data=tmp_qp_sets_data,many=False)
                        if serialized_qp_sets.is_valid():
                            serialized_qp_sets.save()
                            
                        else:
                            print(f'Error in serialization of QP Sets : {serialized_qp_sets.errors}')
                            return Response({"api_status":False,"message":"Incorrect data in serializing QP Sets","error":serialized_qp_sets.errors})
                    else:
                        print('\n')
                        print('-----------------------------------------------------------')
                        print('QP SET ID is already present into school local database....')
                        
                        print('-----------------------------------------------------------')

            #Read the question .json -> Qpset, Question and Choices
            for file in os.listdir(json_file_path):
                if file.startswith('qpdownload'):
                    # print('File :',file)
                    print('full path :',os.path.join(json_file_path,file))
                    with open(os.path.join(json_file_path,file), 'r+', encoding="utf-8") as f:
                        qpdownload_list = json.load(f)

                    #print(qpdownload_list)
                    try:
                        load_question_choice_data(qpdownload_list)
                    except Exception as e:
                        return Response({'api_status':False,'message':'Error reading qpdownload json data...!','exception':str(e)})

            # Delete residual file
            shutil.rmtree(file_path,ignore_errors=False,onerror=None)
            

            # return Response({'api_status':True,'dir':dir(file_obj),'name':file_obj.name,'type':file_obj.content_type})


            infolog.info(json.dumps({'school_id':request.user.profile.school_id,'username':request.user.username,'action':'Meta_Upload','event_id':event_id,'datetime':str(datetime.datetime.now())},default=str))


            return Response({'api_status':True,'message':'Meta data uploaded successfully'})
        
        except Exception as e:
            
            errorlog.error(json.dumps({'school_id':request.user.profile.school_id,'username':request.user.username,'action':'Meta_Upload','event_id':event_id,'datetime':str(datetime.datetime.now()),'exception':str(e)},default=str))


            return Response({'api_status':False,'message':'Unable to upload the meta data','exception':str(e)})


class ResetDB(APIView):
    '''
    API class to deregister DB

    Drop the students_school_child_count table

    '''

    def post(self,request,*args,**kwargs):
        try :
            
            cn = connection()

            if cn == None:
                data = {}
                data['api_status'] = False
                data['message'] = 'School server Not reachable'
                return Response(data)
            
            mycursor = cn.cursor()

            query = f"SELECT {AUTH_FIELDS['school']['school_id']} FROM {AUTH_FIELDS['school']['auth_table']} LIMIT 1"
            mycursor.execute(query)
            school_id_response = mycursor.fetchall()

            if len(school_id_response) == 0:
                return Response({'api_status':False,'message':'Registeration data not loaded yet'})


            print('-----print---token-----',get_school_token(),'-------------')

            print('-----print--school-id',school_id_response[0][0])

            # API to delete entry from central server

            dereg_url = f"{CENTRAL_SERVER_IP}/exammgt/de-registeration"

            dereg_payload = json.dumps({
                "school_id" : school_id_response[0][0],
                "school_token":get_school_token()
            },default=str)

            req_response = requests.request("POST", dereg_url, data=dereg_payload, verify=CERT_FILE) 

            print('---req---response---',req_response.json())

            if req_response.json()['api_status'] == False:
                return Response(req_response.json())


            query = f"DROP TABLE {DB_STUDENTS_SCHOOL_CHILD_COUNT};"

            mycursor.execute(query)

            cn.close()

            MiscInfo.objects.all().delete()
            scheduling.objects.all().delete()
            participants.objects.all().delete()
            event.objects.all().delete()

            User.objects.all().delete()

            api_log.info(json.dumps({'school_id':school_id_response[0][0],'action':'Reset_DB','datetime':str(datetime.datetime.now())},default=str))


            return Response({'api_status':True,'messge':'De-Registeration successful'})
        
        except Exception as e:

            api_errorlog.error(json.dumps({'school_id':school_id_response[0][0],'action':'Reset_DB','datetime':str(datetime.datetime.now()),'exception':str(e),'exception':str(e)},default=str))

            return Response({'api_status':False,'message':'Unable to De-Register','exception':str(e)})


class ListCleanerID(APIView):
    '''
    API class to list old event IDs which can be deleted -> For Events which are old and ExamMeta.sync_done = 1

    Conditions being checked
    `````````````````````````
    1. No ExamMeta object with sync_done = 0 => An Exam is actively running or Meta data is loaded for the upcoming exam
    2. Check if the event_id is older than the residual delete days (set from RESIDUAL_DELETE_DAYS)

    sync_done -> status
    ```````````````````
    0 -> Default
    1 -> Exam completed
    2 -> Cleanup completed

    '''
    def post(self,request,*args,**kwargs):
        
        try:

            if ExamMeta.objects.filter(sync_done = 0).count() > 0:
                return Response({'api_status':False,'message':'Some exams not completed yet'})

            # Filter only the ExamMeta objects which have sync_done = True
            list_meta_obj = ExamMeta.objects.filter(sync_done = 1)

            # list_events_clean
            data_events = []
            for meta_obj in list_meta_obj:
                if scheduling.objects.filter(schedule_id=meta_obj.event_id).exists():
                    sch_obj = scheduling.objects.get(schedule_id=meta_obj.event_id)
                    
                    # Append only if scheduler endtime is greater than the current date with residual days
                    if sch_obj.event_enddate < (datetime.datetime.now()-datetime.timedelta(days=RESIDUAL_DELETE_DAYS)).date():
                        data_events.append({
                            'event_id':         meta_obj.event_id,
                            'event_title':      sch_obj.event_title,
                            'class_std':        sch_obj.class_std,
                            'class_section':    sch_obj.class_section,
                            'class_subject':    sch_obj.class_subject,
                            'event_startdate':  sch_obj.event_startdate,
                            'event_enddate':    sch_obj.event_enddate
                            })

            if len(data_events) == 0:
                return Response({'api_status':False,'message':'No events to delete'})

            return Response({'api_status':True,'data':data_events})
        
        except Exception as e:
            return Response({'api_status':False,'message':'Error in fetching list of IDs for cleaner','exception':f'{e}'})

class MasterCleaner(APIView):
    '''
    API class to delete files and data from DB based on EventID

    InputParameter
    ``````````````

    event_id : Event id which needs to be deleted

    Files
    `````
    1. Delete files in questions_json
    2. Delete files in cons_data

    DB Tables
    `````````
    1. EventAttendance (Commented)
    2. ExamResponse
    3. ExamMeta (Commented)
    4. QpSet
    5. Question
    6. Choice

    '''
    def post(self,request,*args,**kwargs):

        # Check condition for delete



        try:

            event_id = request.data['event_id']

            cn = connection()

            if cn == None:
                data = {}
                data['api_status'] = False
                data['message'] = 'School server Not reachable'
                return Response(data)
            
            mycursor = cn.cursor()

            query = f"SELECT {AUTH_FIELDS['school']['school_id']} FROM {AUTH_FIELDS['school']['auth_table']} LIMIT 1"
            mycursor.execute(query)
            school_id_response = mycursor.fetchall()

            # Check if event_id is available or not
            if ExamMeta.objects.filter(event_id=event_id).count() == 0:
                return Response({'api_status':False,'message':f"Event_id : {event_id} not available !!"})
            
            metaObj = ExamMeta.objects.get(event_id=event_id)

            # Delete from EventAttendance Table
            # try:
            #     EventAttendance.objects.filter(event_id=event_id).delete()
            # except Exception as e:
            #     return Response({'api_status':False,'message':"Error in deleting data in EventAttendance Table",'exception':str(e)})
            
            # Delete from ExamResponse Table
            try:
                ExamResponse.objects.filter(event_id=event_id).delete()
            except Exception as e:
                return Response({'api_status':False,'message':'Error in deleting data in ExamResponse Table','exception':str(e)})

            # Delete from ExamMeta Table
            # try:
            #     ExamMeta.objects.filter(event_id=event_id).delete()
            # except Exception as e:
            #     return Response({'api_status':False,'message':'Error in deleting data in ExamMeta Table','exception':str(e)})


            # Delete from QpSet Table
            try:
                qid_list = []
                qp_objects = QpSet.objects.filter(event_id=event_id)
                for qp_obj in qp_objects:
                    print('****',eval(qp_obj.qid_list))
                    for q_element in eval(qp_obj.qid_list):
                        if q_element not in qid_list:
                            qid_list.append(q_element)
                qp_objects.delete()

            except Exception as e:
                return Response({'api_status':False,'message':'Error in deleting data in QpSet Table','exception':str(e)})

            print('-------',qid_list,'---------')

            # Delete from Question Table
            try:
                Question.objects.filter(qid__in=qid_list).delete()
            
            except Exception as e:
                return Response({'api_status':False,'message':'Error in deleting data in Question Table','exception':str(e)})

            # Delete from Choice Table
            try:
                Choice.objects.filter(qid__in=qid_list).delete()
            
            except Exception as e:
                return Response({'api_status':False,'message':'Error in deleting data in Choice Table','exception':str(e)})
            
            # Deletion of files

            # Delete the eventID's questions_json files
            questions_folder = os.path.join(MEDIA_ROOT,'questions_json')

            try:
                if os.path.exists(questions_folder):
                    for fname in os.listdir(questions_folder):
                        if fname.startswith(f"{event_id}_"):
                            os.remove(os.path.join(questions_folder, fname))
            except Exception as e:
                return Response({'api_status':False,'message':'Error in deleting files in questions_json folder'})

            # Delete the eventID's cons_data
            cons_data_folder = os.path.join(MEDIA_ROOT,'cons_data',f'{event_id}')
            try:
                if os.path.exists(cons_data_folder):
                    shutil.rmtree(cons_data_folder,ignore_errors=False,onerror=None)
            except Exception as e:
                return Response({'api_status':False,'message':'Error in deleting files in cons_data folder'})

            metaObj.sync_done = 2
            metaObj.save()

            infolog.info(json.dumps({'school_id':school_id_response[0][0],'action':'Clean_ID','event_id':event_id,'datetime':str(datetime.datetime.now()),'exception':str(e)},default=str))


            return Response({'api_status':True,'message':f"Clean-up completed for event_id : {event_id}"})

        except Exception as e:

            errorlog.info(json.dumps({'school_id':school_id_response[0][0],'action':'Clean_ID','event_id':event_id,'datetime':str(datetime.datetime.now()),'exception':str(e),'exception':str(e)},default=str))

            return Response({'api_status':False,'message':f'Error in cleaning up event_id : {event_id}','exception':f'{e}'})


class ExamComplete(APIView):
    
    '''
    API class to mark an exam as completed


    Input Parameter
    ````````````````

    event_id -> ID which needs to be marked as completed

    sync_done -> status
    0 -> Default
    1 -> Exam completed
    2 -> Cleanup completed

    '''

    def post(self,request,*args,**kwargs):

        try:
            event_id = request.data['event_id']

            cn = connection()

            if cn == None:
                data = {}
                data['api_status'] = False
                data['message'] = 'School server Not reachable'
                return Response(data)
            
            mycursor = cn.cursor()

            query = f"SELECT {AUTH_FIELDS['school']['school_id']} FROM {AUTH_FIELDS['school']['auth_table']} LIMIT 1"
            mycursor.execute(query)
            school_id_response = mycursor.fetchall()

            if ExamMeta.objects.filter(event_id=event_id).exists() == False:
                return Response({'api_status':False,'message':f'Meta data not available for the given event_id :{event_id}'})

            print('-----------------------')

            meta_obj = ExamMeta.objects.get(event_id=event_id)
            meta_obj.sync_done = 1
            meta_obj.save()

            infolog.info(json.dumps({'school_id':school_id_response[0][0],'action':'Exam_Complete','event_id':event_id,'datetime':str(datetime.datetime.now()),'exception':str(e)},default=str))


            return Response({'api_status':True,'message':'Exam marked as completed'})

        except Exception as e:
            
            errorlog.error(json.dumps({'school_id':school_id_response[0][0],'action':'Exam_Complete','event_id':event_id,'datetime':str(datetime.datetime.now()),'exception':str(e)},default=str))


            return Response({'api_status':False,'message':'Error in marking exam as completed','exception':str(e)})


class DispMisc(APIView):
    '''
    Display misc info like ,
    
    reg_dt   -> Last sync datetime of Get-Registeration
    event_dt -> Last sync datetime of Get-Events
    
    '''

    def post(self,request,*args,**kwargs):

        try:
            misc_obj = MiscInfo.objects.all().first()

            return Response({'api_status':True,
            'data':{
                'reg_dt': misc_obj.reg_dt.strftime("%Y-%m-%d %-H:%-M") if misc_obj.reg_dt else None,
                'event_dt':misc_obj.event_dt.strftime("%Y-%m-%d %-H:%-M")  if misc_obj.event_dt else None,
                'resp_dt':misc_obj.resp_dt.strftime("%Y-%m-%d %-H:%-M") if misc_obj.resp_dt else None
                }})

        except Exception as e:
            return Response({'api_status':False,'message':'Error in fetching misc data','exception':str(e)})


class ToComplete(APIView):

    '''

    API class to list the events which can be marked as completed

    '''

    def post(self,request,*args,**kwargs):
        
        try:
            exam_objs = ExamMeta.objects.filter(sync_done = 0,event_enddate__lt = datetime.datetime.now())

            data_meta = []
            for meta_obj in exam_objs:
                data_meta.append({
                    'event_id':         meta_obj.event_id,
                    'event_title':      meta_obj.event_title,
                    'class_std':        meta_obj.class_std,
                    'class_section':    meta_obj.class_section,
                    'class_subject':    meta_obj.class_subject,
                    'event_startdate':  meta_obj.event_startdate,
                    'event_enddate':    meta_obj.event_enddate

                })
            
            if len(data_meta) == 0:
                return Response({'api_status':True,'message':'No Events available to mark as complete'})

            return Response({'api_status':True,'data':data_meta})
        
        except Exception as e:
            return Response({'api_status':False,'message':'Error in listing event to mark as complete','exception':str(e)})

def ipfetch(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    else:
        return request.META.get('REMOTE_ADDR')


class SendResponse(APIView):

    '''
    API class to send json files if available

    Send event based responses
    
    '''

    def post(self,request,*args,**kwargs):
        try:

            if request.user.profile.usertype not in ['hm','superadmin_user','school']:
                return Response ({'api_status':False,'message':'Only HM is authorized for JSON generation'})
        
            data = JSONParser().parse(request)
            #data['event_id'] = data ['id']

            folder_dir = os.path.join(MEDIA_ROOT,'cons_data',f"{data['event_id']}")

            if os.path.isdir(folder_dir) == False:
                return Response ({'api_status':False,'message':'No response available to send'})

            
            timestr = time.strftime("%Y%m%d%H%M%S")

            actualfile = os.path.join(MEDIA_ROOT,'cons_data',f"{data['event_id']}_{request.user.profile.school_id}_{timestr}.7z")

            with py7zr.SevenZipFile(actualfile, 'w') as archive:
                archive.writeall(folder_dir, '')


            send_response_url = f"{CENTRAL_SERVER_IP}/exammgt/load-responses"

            # Fetch school name
            cn = connection()
            mycursor = cn.cursor()
            query = f"SELECT school_name FROM {DB_STUDENTS_SCHOOL_CHILD_COUNT} LIMIT 1;"
            mycursor.execute(query)
            school_detail_response = mycursor.fetchall()

            print('school name _+_+_+_+_+',school_detail_response[0][0])

            calmd5sum = subprocess.Popen(["md5sum", actualfile], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            zip_hash = calmd5sum.communicate()[0].decode("utf-8").split(" ")[0]

            print('----------file---send------------',actualfile)


            # with open(actualfile,'rb') as f:  # redundant
            #     print('-----------type of f---------',type(f))
                
            #     f.seek(0)
            #     with open(os.path.join(MEDIA_ROOT,'cons_data',f"{data['event_id']}_{request.user.profile.school_id}_{timestr}_test.7z"), "wb") as file1:
            #         print(dir(f))
            #         shutil.copyfileobj(f, file1, length=1024)
            #         # file1.write(f.read())


            #with open(actualfile, 'rb') as f:
                #print('----file-------content-----',f)





            fileobj = open(actualfile, 'rb')
            sent_request = requests.post(send_response_url, data={
                'event_id':data['event_id'],
                # 'archive':  fileobj,
                'md5sum':zip_hash,
                'school_token':get_school_token(),
                'school_id':request.user.profile.school_id,
                'process_str':'RESPONSE_DATA',
                'ipaddress': ipfetch(request),
                'school_name': school_detail_response[0][0],
                'file_name': os.path.basename(actualfile)
                },files = {'archive': (actualfile, fileobj, 'application/x-7z-compressed')})


            if sent_request.status_code != 200:
                return Response({'api_status':False,'message':'Unable to send response files to Central Server','error':'Status not equal to 200','Error content':sent_request.reason,'status_code':sent_request.status_code})

            sent_request_response = sent_request.json()

            #print('SendResponse\'s response json :',sent_request_response)

            if sent_request_response['api_status']:
                print('Deleting the 7zip file :',actualfile)
                os.remove(actualfile)
                print('Deleting folder :',folder_dir)
                shutil.rmtree(folder_dir,ignore_errors=False,onerror=None)

            # import io
            
            # print('_+_+_+_',sent_request_response['data'])
            # test1 = sent_request_response['data']
            # test = io.BytesIO(test1)
            # print('test type',type(test))

            # test.seek(0)
            # with open(os.path.join(MEDIA_ROOT,'cons_data',f"{data['event_id']}_{request.user.profile.school_id}_{timestr}_test111111111.7z"), "wb") as file1:
               
            #     #shutil.copyfileobj(test, file1, length=1024)
            #     file1.write(f.read())

            api_log.info(json.dumps({'school_id':request.user.profile.school_id,'username':request.user.username,'action':'Send_response','event_id':data['event_id'],'datetime':str(datetime.datetime.now())},default=str))

            return Response(sent_request_response)

        except Exception as e:

            api_errorlog.error(json.dumps({'school_id':request.user.profile.school_id,'username':request.user.username,'action':'Send_response','event_id':data['event_id'],'datetime':str(datetime.datetime.now()), 'exception':str(e)},default=str))

            return Response({'api_status':False,'message':'Error in sending response to the central server','exception':str(e)})


class SendResponses(APIView):
    '''
    
    API class to send JSON response files if available
    
    '''

    def post(self,request,*args,**kwargs):

        try:
            if request.user.profile.usertype not in ['hm','superadmin_user','school']:
                return Response ({'api_status':False,'message':'Only HM is authorized for JSON generation'})

            print('-----------------')
            json_dir = os.path.join(MEDIA_ROOT,'cons_data')

            if os.path.isdir(json_dir) == False:
                return Response ({'api_status':False,'message':'No response file available to send'})

            json_file_list = os.listdir(json_dir)

            if len(json_file_list) == 0:
                return Response ({'api_status':False,'message':'No response file available to send'})

            compress_dir = os.path.join(MEDIA_ROOT,'cons_zip')
            os.makedirs(compress_dir, exist_ok=True)

            timestr = time.strftime("%Y%m%d%H%M%S")
            
            
            zip_file_name = os.path.join(compress_dir,f"{request.user.profile.school_id}_{timestr}.7z")

            with py7zr.SevenZipFile(zip_file_name, 'w') as archive:
                archive.writeall(json_dir, '')

            print('zipped content :',json_file_list)

            ids = set()
            for i in json_file_list:
                ids.add(i.split('_')[0])

            ids_list = str(sorted(ids))

            print('unique IDs :',ids)

            send_response_url = f"{CENTRAL_SERVER_IP}/exammgt/load-responses"

            # Fetch school name
            cn = connection()
            mycursor = cn.cursor()
            query = f"SELECT school_name FROM {DB_STUDENTS_SCHOOL_CHILD_COUNT} LIMIT 1;"
            mycursor.execute(query)
            school_detail_response = mycursor.fetchall()

            calmd5sum = subprocess.Popen(["md5sum", zip_file_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            zip_hash = calmd5sum.communicate()[0].decode("utf-8").split(" ")[0]

            fileobj = open(zip_file_name, 'rb')
            sent_request = requests.post(send_response_url, data={
                'event_id':ids_list,
                # 'archive':  fileobj,
                'md5sum':zip_hash,
                'school_token':get_school_token(),
                'school_id':request.user.profile.school_id,
                'process_str':'RESPONSE_DATA',
                'ipaddress': ipfetch(request),
                'school_name': school_detail_response[0][0],
                'file_name': os.path.basename(zip_file_name)
                },files = {'archive': (zip_file_name, fileobj, 'application/x-7z-compressed')})

            sent_request_response = sent_request.json()


            if sent_request.status_code != 200:
                os.remove(zip_file_name)
                return Response({'api_status':False,'message':'Unable to send response files to Central Server','error':'Status not equal to 200','Error content':sent_request.reason,'status_code':sent_request.status_code})


            # print('------------------------')
            # print('Deleting ...',zip_file_name)
            os.remove(zip_file_name)
            if sent_request_response['api_status']:
                for i in json_file_list:
                    # print('deleting...',os.path.join(json_dir,i))
                    os.remove(os.path.join(json_dir,i))   

                # print(json.dumps({'school_id':request.user.profile.school_id,'username':request.user.username,'action':'Send_response','event_id':ids_list,'datetime':str(datetime.datetime.now())},default=str))

                if MiscInfo.objects.all().count() == 0:
                    MiscInfo.objects.create(resp_dt = datetime.datetime.now())
                else :
                    misc_obj = MiscInfo.objects.all().first()
                    misc_obj.resp_dt = datetime.datetime.now()
                    misc_obj.save()

                api_log.info(json.dumps({'school_id':request.user.profile.school_id,'username':request.user.username,'action':'Send_response','event_id':ids_list,'datetime':str(datetime.datetime.now())},default=str))

                # sent_request_response = sent_request.json()
                # print('sent_request_response ',sent_request_response)

                sent_request_response['message'] = f"Responses sent to the central server for event ids {ids}"

                return Response(sent_request_response)

            else:
                return Response({'api_status':False,'message':'Unable to send files to central server'})


        except Exception as e:
            
            try: # Delete the zip file if possible
                os.remove(zip_file_name)
            except:
                pass

            api_errorlog.error(json.dumps({'school_id':request.user.profile.school_id,'username':request.user.username,'action':'Send_response','event_id':ids_list,'datetime':str(datetime.datetime.now()), 'exception':str(e)},default=str))

            return Response({'api_status':False,'message':'Error in sending response to the central server','exception':str(e)})

class GenSendResponses(APIView):
    '''
        API query to Generete the json files of all the new students and send to the central server
    '''

    def post(self,request,*args, **kwargs):

        folder_dir = os.path.join(MEDIA_ROOT,'cons_data')
        os.makedirs(folder_dir, exist_ok=True)
        
        try:
            print('Initiate Send response ',request.user.profile.usertype )
            if request.user.profile.usertype in ['student']:
                return Response ({'api_status':False,'message':'Student not authorized'})

            with transaction.atomic(): # Atomic Transcation
                sch_par_list = []
                
                if scheduling.objects.all().count() == 0 :
                    return Response ({'api_status':True,'message':'No events available in the school server'})
                
                for par_obj in participants.objects.all():
                    
                    details_object = []
                    try:
                        sch_obj = scheduling.objects.get(schedule_id = par_obj.schedule_id)
                    except Exception as e:
                        print('Exception in fetching schedule for participant_s scheduleid : ',e)
                        continue
                    event_attendances = EventAttendance.objects.filter(event_id = sch_obj.schedule_id, participant_pk = par_obj.id,json_created = False).exclude(end_time = None)
                    
                    print(f"{len(event_attendances)} records found in the scheduleid {sch_obj.schedule_id} - participant_pk {par_obj.id}")
                    
                    if len(event_attendances) == 0:
                        continue
                    
                    sch_par_list.append([sch_obj.schedule_id, par_obj.id])
                    
                    file_name = os.path.join(folder_dir,f"{sch_obj.schedule_id}_{par_obj.id}_{request.user.profile.school_id}_{request.user.profile.udise_code}_{str(datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S'))}.json")
                    
                    consolidated_data = {
                        'event_id':sch_obj.schedule_id,
                        'participant_pk' : par_obj.id,
                        'school_id':request.user.profile.school_id,
                        'udise_code':request.user.profile.udise_code,
                        'details':[]
                        }
                    
                    #  Loop through each attendance entry
                    
                    for event_attendance_obj in event_attendances:
                        details_dict = {
                            'student_username': event_attendance_obj.student_username,
                            'qp_set_id': event_attendance_obj.qp_set,
                            'start_time': str(event_attendance_obj.start_time),
                            'end_time': str(event_attendance_obj.end_time),
                            'total_questions':str(event_attendance_obj.total_questions),
                            'visited_questions':str(event_attendance_obj.visited_questions),
                            'answered_questions':str(event_attendance_obj.answered_questions),
                            'reviewed_questions':str(event_attendance_obj.reviewed_questions),
                            'correct_answers':str(event_attendance_obj.correct_answers),
                            'wrong_answers':str(event_attendance_obj.wrong_answers),
                        }
                        
                        obj = ExamResponse.objects.filter(event_id = sch_obj.schedule_id, participant_pk = par_obj.id, student_username = event_attendance_obj.student_username,qp_set_id = event_attendance_obj.qp_set)
                        
                        responses = []
                        
                        for obj_instance in obj:
                            responses.append({
                                'question_id':obj_instance.question_id,
                                'selected_choice_id':obj_instance.selected_choice_id,
                                'correct_choice_id':obj_instance.question_result,
                                'marked_review':obj_instance.review,
                                'created_on':str(obj_instance.created_on)
                            })
                        details_dict['responses'] = responses
                        details_object.append(details_dict)
                        
                    consolidated_data['details'] = details_object
                    
                    print('Creating Json file :',file_name)
                    
                    with open(file_name, 'w') as outfile:  
                        json.dump(consolidated_data, outfile)
                    
                    
                    # Mark json_created in the attendance entry
                    for event_attendance_obj in event_attendances:
                        event_attendance_obj.json_created = True
                        event_attendance_obj.save()
                    
                print('Schedule - Participant list :',sch_par_list)
                
                json_file_list = os.listdir(folder_dir)
                
                if len(json_file_list) == 0:
                    if MiscInfo.objects.all().count() == 0:
                        MiscInfo.objects.create(resp_dt = datetime.datetime.now())
                    else :
                        misc_obj = MiscInfo.objects.all().first()
                        misc_obj.resp_dt = datetime.datetime.now()
                        misc_obj.save()
                    return Response ({'api_status':True,'message':'No response file available to send'})
                
                compress_dir = os.path.join(MEDIA_ROOT,'cons_zip')
                os.makedirs(compress_dir, exist_ok=True)
                
                timestr = time.strftime("%Y%m%d%H%M%S")
                
                zip_file_name = os.path.join(compress_dir,f"{request.user.profile.school_id}_{timestr}.7z")
                
                with py7zr.SevenZipFile(zip_file_name, 'w') as archive:
                    archive.writeall(folder_dir, '')
                
                print('zipped content :',json_file_list)
                
                send_response_url = f"{CENTRAL_SERVER_IP}/exammgt/load-responses"
                
                # Fetch school name
                cn = connection()
                mycursor = cn.cursor()
                query = f"SELECT school_name FROM {DB_STUDENTS_SCHOOL_CHILD_COUNT} LIMIT 1;"
                mycursor.execute(query)
                school_detail_response = mycursor.fetchall()
                
                calmd5sum = subprocess.Popen(["md5sum", zip_file_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                zip_hash = calmd5sum.communicate()[0].decode("utf-8").split(" ")[0]
                
                fileobj = open(zip_file_name, 'rb')
                
                sent_request = requests.post(send_response_url, data={
                    'sch_par_list':str(sch_par_list),
                    # 'archive':  fileobj,
                    'md5sum':zip_hash,
                    'school_token':get_school_token(),
                    'school_id':request.user.profile.school_id,
                    'process_str':'RESPONSE_DATA',
                    'ipaddress': ipfetch(request),
                    'school_name': school_detail_response[0][0],
                    'file_name': os.path.basename(zip_file_name)
                    },files = {'archive': (zip_file_name, fileobj, 'application/x-7z-compressed')})
                sent_request_response = sent_request.json()


                if sent_request.status_code != 200:
                    os.remove(zip_file_name)
                    return Response({'api_status':False,'message':'Unable to send response files to Central Server','error':'Status not equal to 200','Error content':sent_request.reason,'status_code':sent_request.status_code})

                os.remove(zip_file_name)
                if sent_request_response['api_status']:
                    for i in json_file_list:
                        # print('deleting...',os.path.join(json_dir,i))
                        os.remove(os.path.join(folder_dir,i))   

                if MiscInfo.objects.all().count() == 0:
                    MiscInfo.objects.create(resp_dt = datetime.datetime.now())
                else :
                    misc_obj = MiscInfo.objects.all().first()
                    misc_obj.resp_dt = datetime.datetime.now()
                    misc_obj.save()


                infolog.info(json.dumps({'school_id':request.user.profile.school_id,'username':request.user.username,'action':'Generate_JSON_send_Response','sch_par_list':str(sch_par_list),'datetime':str(datetime.datetime.now())},default=str))


                return Response({'api_status':True,'message':f"JSON file generated and sent successfully"})
                                
        except Exception as e:

            errorlog.error(json.dumps({'school_id':request.user.profile.school_id,'username':request.user.username,'action':'Generate_JSON_send_Response','sch_par_list':str(sch_par_list),'datetime':str(datetime.datetime.now()),'exception':str(e)},default=str))
            
            try:
                shutil.rmtree(folder_dir)
            except Exception as e:
                print(f'Unable to delete folder {folder_dir} :',e)
            

            return Response({'api_status':False,'message':'Error in generating JSON and sending response files','exception':str(e)})

class GenSendResponsesOld(APIView):

    '''
        API query to Generete the json files of all the new students and send to the central server
    '''

    def post(self,request,*args, **kwargs):

        folder_dir = os.path.join(MEDIA_ROOT,'cons_data')
        os.makedirs(folder_dir, exist_ok=True)
        
        try:
            
            if request.user.profile.usertype in ['student']:
                return Response ({'api_status':False,'message':'Student not authorized'})

            with transaction.atomic(): # Atomic Transcation
                scheduling_list = list(scheduling.objects.all().values_list('schedule_id', flat=True))

                print('Scheduling list ==> ',scheduling_list)

                sch_json_id = [] # list of scheduling  ids for which json file is prepared

                details_object = []

                for sch_id in scheduling_list:
                    event_attendances = EventAttendance.objects.filter(event_id = sch_id,json_created = False).exclude(end_time = None)

                    print(f"{len(event_attendances)} records found in the scheduleid {sch_id}")

                    if len(event_attendances) == 0:
                        continue

                    sch_json_id.append(sch_id)

                    file_name = os.path.join(folder_dir,f"{sch_id}_{request.user.profile.school_id}_{request.user.profile.udise_code}_{str(datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S'))}.json")
                    
                    consolidated_data = {
                        'event_id':sch_id,
                        'school_id':request.user.profile.school_id,
                        'udise_code':request.user.profile.udise_code,
                        'details':[]
                        }

                    # Loop throught each attdendance entry

                    

                    for event_attendance_obj in event_attendances:
                        details_dict = {
                            'student_username': event_attendance_obj.student_username,
                            'qp_set_id': event_attendance_obj.qp_set,
                            'start_time': str(event_attendance_obj.start_time),
                            'end_time': str(event_attendance_obj.end_time),
                            'total_questions':str(event_attendance_obj.total_questions),
                            'visited_questions':str(event_attendance_obj.visited_questions),
                            'answered_questions':str(event_attendance_obj.answered_questions),
                            'reviewed_questions':str(event_attendance_obj.reviewed_questions),
                            'correct_answers':str(event_attendance_obj.correct_answers),
                            'wrong_answers':str(event_attendance_obj.wrong_answers),
                        }

                        obj = ExamResponse.objects.filter(event_id = sch_id,student_username = event_attendance_obj.student_username,qp_set_id = event_attendance_obj.qp_set)
                        
                        responses = []

                        for obj_instance in obj:
                            responses.append({
                                'question_id':obj_instance.question_id,
                                'selected_choice_id':obj_instance.selected_choice_id,
                                'correct_choice_id':obj_instance.question_result,
                                'marked_review':obj_instance.review,
                                'created_on':str(obj_instance.created_on)
                            })
                        
                        details_dict['responses'] = responses
                        details_object.append(details_dict)

                    consolidated_data['details'] = details_object

                    # print('Consolidate data',consolidated_data)

                    # print('json dumps',json.dumps(consolidated_data))

                    with open(file_name, 'w') as outfile:  
                        json.dump(consolidated_data, outfile)

                    # Mark json_created in the attendance entry

                    for event_attendance_obj in event_attendances:
                        event_attendance_obj.json_created = True
                        event_attendance_obj.save()

                json_file_list = os.listdir(folder_dir)

                if len(json_file_list) == 0:
                    if MiscInfo.objects.all().count() == 0:
                        MiscInfo.objects.create(resp_dt = datetime.datetime.now())
                    else :
                        misc_obj = MiscInfo.objects.all().first()
                        misc_obj.resp_dt = datetime.datetime.now()
                        misc_obj.save()
                    return Response ({'api_status':True,'message':'No response file available to send'})
                
                compress_dir = os.path.join(MEDIA_ROOT,'cons_zip')
                os.makedirs(compress_dir, exist_ok=True)

                timestr = time.strftime("%Y%m%d%H%M%S")
                
                
                zip_file_name = os.path.join(compress_dir,f"{request.user.profile.school_id}_{timestr}.7z")

                with py7zr.SevenZipFile(zip_file_name, 'w') as archive:
                    archive.writeall(folder_dir, '')

                print('zipped content :',json_file_list)

                ids = set()
                for i in json_file_list:
                    ids.add(i.split('_')[0])

                ids_list = str(sorted(ids))

                print('unique IDs :',ids_list)

                send_response_url = f"{CENTRAL_SERVER_IP}/exammgt/load-responses"

                # Fetch school name
                cn = connection()
                mycursor = cn.cursor()
                query = f"SELECT school_name FROM {DB_STUDENTS_SCHOOL_CHILD_COUNT} LIMIT 1;"
                mycursor.execute(query)
                school_detail_response = mycursor.fetchall()

                calmd5sum = subprocess.Popen(["md5sum", zip_file_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                zip_hash = calmd5sum.communicate()[0].decode("utf-8").split(" ")[0]

                fileobj = open(zip_file_name, 'rb')
                sent_request = requests.post(send_response_url, data={
                    'event_id':ids_list,
                    # 'archive':  fileobj,
                    'md5sum':zip_hash,
                    'school_token':get_school_token(),
                    'school_id':request.user.profile.school_id,
                    'process_str':'RESPONSE_DATA',
                    'ipaddress': ipfetch(request),
                    'school_name': school_detail_response[0][0],
                    'file_name': os.path.basename(zip_file_name)
                    },files = {'archive': (zip_file_name, fileobj, 'application/x-7z-compressed')})

                sent_request_response = sent_request.json()


                if sent_request.status_code != 200:
                    os.remove(zip_file_name)
                    return Response({'api_status':False,'message':'Unable to send response files to Central Server','error':'Status not equal to 200','Error content':sent_request.reason,'status_code':sent_request.status_code})

                os.remove(zip_file_name)
                if sent_request_response['api_status']:
                    for i in json_file_list:
                        # print('deleting...',os.path.join(json_dir,i))
                        os.remove(os.path.join(folder_dir,i))   

                if MiscInfo.objects.all().count() == 0:
                    MiscInfo.objects.create(resp_dt = datetime.datetime.now())
                else :
                    misc_obj = MiscInfo.objects.all().first()
                    misc_obj.resp_dt = datetime.datetime.now()
                    misc_obj.save()


                infolog.info(json.dumps({'school_id':request.user.profile.school_id,'username':request.user.username,'action':'Generate_JSON_send_Response','event_ids':str(sch_json_id),'datetime':str(datetime.datetime.now())},default=str))


                return Response({'api_status':True,'message':f"JSON file generated and sent successfully"})

        
        except Exception as e:

            errorlog.error(json.dumps({'school_id':request.user.profile.school_id,'username':request.user.username,'action':'Generate_JSON_send_Response','event_id':str(sch_json_id),'datetime':str(datetime.datetime.now()),'exception':str(e)},default=str))
            

            return Response({'api_status':False,'message':'Error in generating JSON and sending response files','exception':str(e)})


class AutoUpdateStatus(APIView):
    '''
    API class for triggering auto update of fetch events and send responses
    '''

    def get(self, request, *args, **kwargs):
        
        AUTO_RESPONSE_TIME = 4 # Hours
        
        try:
            if request.user.profile.usertype in ['student']:
                return Response ({'api_status':False,'message':'Student not authorized for auto update'})

            misc_obj = MiscInfo.objects.all().first()
            print('Event sync time',misc_obj.event_dt,type(misc_obj.event_dt))
            print('Response sync time',misc_obj.resp_dt,type(misc_obj.resp_dt))

            return Response({
                'api_status':True,
                'event':misc_obj.event_dt.date() != datetime.datetime.now().date() if misc_obj.event_dt else True,
                # 'response':misc_obj.resp_dt.date() != datetime.datetime.now().date() if misc_obj.resp_dt else True
                'response':( datetime.datetime.now() - misc_obj.resp_dt ).total_seconds() // 3600 >= AUTO_RESPONSE_TIME if misc_obj.resp_dt else True
                
                })

        except Exception as e:
            return Response({'api_status':False,'exception':str(e)})    


class MetaAuto(APIView):
    '''
    API class to trigger auto qp download
    '''

    def post(self, request,*args, **kwargs):
        try:
            return Response({'api_status':True})

            # #print('token',request.auth)
            # # print(requests.post(endpoint, data=data, headers=headers).json())

            # # scheduleList = scheduling.objects.all()

            # meta_event_ids = list(ExamMeta.objects.all().values_list('participant_pk',flat=True))

            # #print('meta_event_ids',meta_event_ids)

            # # sch_list = scheduling.objects.all().exclude(schedule_id__in=meta_event_ids)

            # sch_list = participants.objects.all().exclude(id__in=meta_event_ids)
            # # print('QP not downloaded for ',sch_list)
            
            # headers = {
            #     "Authorization": f"Bearer {request.auth}",
            #     'Content-Type': 'application/json'}

            # for sch in sch_list:
            #     print('-------------')
            #     print('URL name',request.resolver_match.view_name)

            #     # req_url = f"{CENTRAL_SERVER_IP}/paper/qpdownload"
            #     req_url = f'http://{get_current_site(request).domain}/exammgt/meta_data'
            #     payload = json.dumps({
            #         'event_id':sch.schedule_id,
            #         'participant_pk' : sch.id
            #     },default=str)

            #     print('Request to the central server to download qp for ',str(sch.schedule_id),str(payload))

            #     session = requests.Session()
            #     session.mount(CENTRAL_SERVER_IP, central_server_adapter)

            #     try:
            #         get_meta_response = session.post(req_url,headers=headers,data = payload)

            #         print('auto meta response ',get_meta_response.text,sch.schedule_id)
            #     except Exception as e:
            #         print('Exception in fetching the qp for eventid ',sch.schedule_id,str(e))


            # return Response({'api_status':True})
        except Exception as e:
            return Response({'api_status':False,'message':'unable to trigger auto qp download','exception':str(e)})


class QpKey(APIView):
    '''
    API class to get the qp key answers

    input parameters

    {
    "event_id":376,
    "participant_pk":138721,
    "qpset": "V0685490101"
    }

    '''

    if AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated

    def post(self,request,*args, **kwargs):
        try:
            request_data = request.data

            event_id = request_data['event_id']
            participant_pk = request_data['participant_pk']

            current_date = datetime.datetime.now().date()



            try:
                par_obj = participants.objects.filter(schedule_id = event_id, id = participant_pk)
                if par_obj.count() == 0:
                    return Response({'api_status':False,'message':'Error in obtaining participant object'})

                qpset_list = eval(par_obj[0].event_allocationid)

                try:
                    sch_obj=scheduling.objects.filter(schedule_id=event_id)[0]
                    if current_date <=sch_obj.event_enddate:
                        return Response({'api_status':False,'message':'Event Not Completed Yet , Key will available only after Event is completed'})
                        
                except Exception as e:
                    return Response({'api_status':False,'message':'Error in obtaining schedule_date object','exception':str(e)})

                try:
                    if (request_data['qpset'] == None) or (request_data['qpset'] == ""):
                        qpset = qpset_list[0]

                    qpset = request_data['qpset']

                except:
                    qpset = qpset_list[0]

                question_meta_object_query = ExamMeta.objects.filter(
                    event_id = participant_pk,
                    participant_pk = event_id
                )

                if question_meta_object_query.count() > 0:
                    question_meta_object = question_meta_object_query[0]
                else:
                    return Response({'api_status':False,'message':'No question meta data found'})

                tmp_exam_dict = model_to_dict(question_meta_object)
                
                #  flip event_id and participant_pk
                tmp_event_id = tmp_exam_dict['participant_pk']
                tmp_participant_pk = tmp_exam_dict['event_id']
                tmp_exam_dict['event_id'] = tmp_event_id
                tmp_exam_dict['participant_pk'] = tmp_participant_pk
                tmp_exam_dict['qp_set_list'] = eval(tmp_exam_dict['qp_set_list'] )

                # print('selected qp',qpset)
                # print('Temp_exam_dict',tmp_exam_dict)


                qp_sets_object_edit = QpSet.objects.filter(
                    event_id = participant_pk,
                    qp_set_id = qpset
                )
                # print('qp set object ',qp_sets_object_edit)

                if qp_sets_object_edit.count() == 0:
                    return Response({'api_status':False,'message':'qpset object empty'})

                qp_set_data = model_to_dict(qp_sets_object_edit[0])
                qid_list = eval(qp_set_data['qid_list'])


                qp_base64_list = []
                qp_base64_list_object_edit = Question.objects.filter(qid__in=qid_list)
                for qp_data in qp_base64_list_object_edit:
                    qp_base64_list.append(model_to_dict(qp_data))

                choice_base64_list = []
                for qid in qid_list:
                    cfilter = {
                        "qid": int(qid)
                    }

                    choice_base64_list_object_edit = Choice.objects.filter(**cfilter)
                    # print('=-=-=-=', choice_base64_list_object_edit)
                    choice_base64_list_object = []
                    for ch_data in choice_base64_list_object_edit:
                        tmp_dict_data = model_to_dict(ch_data)
                        # del tmp_dict_data['qid']
                        choice_base64_list_object.append(tmp_dict_data)
                    choice_base64_list.append(choice_base64_list_object)

                questions_data_list =[]
                for qp_img in qp_base64_list:
                    for ch_img in choice_base64_list:
                        tmp_ch_dict = {}
                        # print(qp_img['qid'],'****',ch_img)
                        if len(ch_img) == 0:
                            continue
                        if qp_img['qid'] == str(ch_img[0]['qid']):
                            tmp_ch_dict['q_choices'] = ch_img
                            qp_img.update(tmp_ch_dict)
                
                    questions_data_list.append(qp_img)
                
                # sort questions

                # sorted_questions = []
                # try:
                #     for qid in qid_list:
                #         for qes in questions_data_list:
                #             if qes['qid'] in qid:
                #                 sorted_questions.append(qes)
                # except Exception as e:
                #     return Response({'api_status':False,'message':'Error in sorting questions','exception':e})

                questions_data_list.sort(key=lambda x:qid_list.index(x['qid']))

                # language

                try:
                    medium=scheduling.objects.filter(schedule_id=event_id)[0]
                    lang = medium.class_medium
                    lang_desc = MEDIUM[int(lang)]
                except Exception as e:
                    print('Exception in getting lang_desc',e)
                    lang_desc = 'NA'

                configure_qp_data = tmp_exam_dict
                configure_qp_data['qp_set_id'] = qpset
                configure_qp_data['q_ids'] = qid_list
                configure_qp_data['questions'] = questions_data_list
                configure_qp_data['lang_desc'] = lang_desc
                configure_qp_data['api_status'] = True

                # print('configure qp data',configure_qp_data)

                return Response(configure_qp_data)
            except Exception as e:
                return Response({'api_status':False,'message':'Error in fetching qpset list for qpkey','exception':e})

        except Exception as e:
            return Response({'api_status':False,'message':'Error in QP answer key','exception':str(e)})