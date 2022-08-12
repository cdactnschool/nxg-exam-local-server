
from crypt import methods
from django.shortcuts import render


from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser
from django.shortcuts import get_object_or_404
from django.forms.models import model_to_dict
import random

from .import models
from . import serializers
from scheduler import models as SchedulerModels

import itertools
from collections import OrderedDict
from scheduler import models as models_scheduler

import datetime
import os
import json
from django.contrib.auth.models import User,Group
from django.urls import reverse


from django.conf import settings
import hashlib
import requests

import pandas as pd
import sqlite3

import logging

logger      = logging.getLogger('monitoringdebug')
accesslog   = logging.getLogger('accesslog')
errorlog    = logging.getLogger('errorlog')
infolog     = logging.getLogger('infolog')
apilog      = logging.getLogger('apilog')

import sqlite3
import py7zr

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    '''
    Customized Token Pair Serialization for generation token along with username and groups field
    '''
    def validate(self, attrs):
        data = super().validate(attrs)
        refresh = self.get_token(self.user)
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)

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
        data['dataStatus']  = True
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
        conn = sqlite3.connect('db.sqlite3')
        return conn
    except Exception as e:
        print('connection error :',e)
        return None

auth_fields = {
    'teacher_hm':{
        'username_len': 8,
        'teacher_priority':18,
        'hm_priority':16,
        'username_field':'emis_username',
        'password_field':'ref',
        'hash_field': 'emis_password',
        'auth_table': settings.DB_EMISUSER_TEACHER,
        'master_table': settings.DB_UDISE_STAFFREG,
        'type_checker_foreign_key':'teacher_id',
        'type_checker_field':'teacher_type',
        'type_checker_value':[26,27,28,29],
        'school_key_ref_master' : 'school_key_id',
        'name_field_master':'teacher_name',
        #'auth_'
    },
    'department':{
        'department_priority':14,
        'username_field':'emis_username',
        'password_field':'ref',
        'hash_field': 'emis_password',
        'auth_table':settings.DB_EMIS_USERLOGIN,
    },
    'student':{
        'username_len':16,
        'student_priority':20,
        'username_field':'emis_username',
        'password_field':'ref',
        'hash_field': 'emis_password',
        'auth_table': settings.DB_EMISUSER_STUDENT,
        'type_field': 'emis_usertype',
        'school_field_foreign' :'emis_user_id',
        'master_table': settings.DB_STUDENTS_CHILD_DETAIL,
        'school_field_foreign_ref' : 'id',
        'school_key_ref_master':'school_id',
        'name_field_master':'name',
        'section_field_master':'class_section',
        'student_class': 'class_studying_id',
    },
    'school':{
        'auth_table':settings.DB_STUDENTS_SCHOOL_CHILD_COUNT,
        'school_id':'school_id',
        'district_id': 'district_id',
        'block_id':'block_id',
        'udise_code':'udise_code',
    }
}

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
        db_user = User.objects.get(username=data['username'])
        if not db_user.check_password(data['password']):
            db_user.set_password(data['password'])
    else:
        db_user = User.objects.create_user(username=data['username'],password = data['password'])
    db_user.save()

    if models.Profile.objects.filter(user=db_user).exists():
        profile_instance = models.Profile.objects.get(user=db_user)
    else:
        profile_instance = models.Profile.objects.create(user=db_user)
    
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
    if db_user.groups.exists():
        for g in db_user.groups.all():
            db_user.groups.remove(g)
    if data['user_type']:
        my_group = Group.objects.get(name=data['user_type']) 
        my_group.user_set.add(db_user)

    x = requests.post(request.build_absolute_uri(reverse('token-obtain-pair')),
    data = {'username':data['username'],'password':data['password']})
    
    res_data = x.json()
    
    #return Response(res_data)
    return res_data

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
        "dataStatus": true,
        "message": "User authenticated"
        }

    '''

    def post(self,request):
        cn = connection()

        if cn == None:
            data = {}
            data['dataStatus'] = False
            data['message'] = 'Server Not reachable'
            data['status'] = status.HTTP_504_GATEWAY_TIMEOUT
            return Response(data)

        

        mycursor = cn.cursor()

        data = JSONParser().parse(request)

        possible_type = ''
        user_detail = {}

        # Teacher /HM
        if str(data['username']).isnumeric() and (len(str(data['username'])) == auth_fields['teacher_hm']['username_len']):
            possible_type = 'teacher_hm'
            #print('Possible user type - ',possible_type)
            query = f"SELECT {auth_fields['teacher_hm']['username_field']}, {auth_fields['teacher_hm']['hash_field']} FROM {auth_fields['teacher_hm']['auth_table']} WHERE {auth_fields['teacher_hm']['username_field']} = {data['username']} AND status = 'Active' LIMIT 1"     

                       
            #print('###########',query)
            mycursor.execute(query)
            auth_detail_response = mycursor.fetchall()
            
            if len(auth_detail_response) == 0:
                return Response({'api_status':False,'message':'No data found'})
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
                    return Response(token_response)

            else:
                return Response({'possible_type':possible_type,'message':'Incorrect Username/password','api_status':False})

        # student


        elif (str(data['username']).isnumeric()) and (len(str(data['username'])) == auth_fields['student']['username_len']):
            possible_type = 'student'

            query = f"SELECT {auth_fields['student']['username_field']},{auth_fields['student']['hash_field']},{auth_fields['student']['school_field_foreign']} FROM {auth_fields['student']['auth_table']} WHERE {auth_fields['student']['username_field']} = {data['username']} AND status = 'Active' LIMIT 1"

            print(query)
            mycursor.execute(query)
            auth_detail_response = mycursor.fetchall()
            
            print('Records matching the username @ student',auth_detail_response)


            if len(auth_detail_response) == 0:
                return Response({'message':'No data found','api_status':False})
            
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
                return Response(token_response)
                #return Response({'possible_type':possible_type,'status':'Correct user'})
            else:
                return Response({'possible_type':possible_type,'message':'Incorrect Username/password','api_status':False})
        
        # No authentication for department user in local
        else:
            return Response({'message':'Incorrect Username/password','api_status':False})
    

class exam_response(APIView):
    
    def post(self,request,*args, **kwargs):
        data = JSONParser().parse(request)

        filter_fields = {
            'user':request.user,
            'question_id':data['qid'],
            'qp_set_id':data['qp_set_id'],
            'event_id':data['event_id']
        }
        try:
            print(request.user.username)
            print(filter_fields)
            object_edit = get_object_or_404(models.exam_response,**filter_fields)
            print('--------------',object_edit)
            object_edit.selected_choice_id = None if data['ans'] == '' else data['ans']
            object_edit.question_result = data['correct_choice']
            object_edit.review = data['review']
            print('Check for mark :',object_edit.selected_choice_id == object_edit.question_result)
            if object_edit.selected_choice_id == object_edit.question_result:
                object_edit.mark = 1
            else:
                object_edit.mark = 0
            object_edit.save()
            
            return Response({'status': True,'message':'updated'})
        except Exception as e:

            print('Exception element :',e)
            try:            
                filter_fields['selected_choice_id'] = None if data['ans'] == '' else data['ans']
                filter_fields['question_result'] = data['correct_choice']
                filter_fields['review'] = data['review']

                # Give 1 mark for correct answer
                print('Check for mark :',filter_fields['selected_choice_id'] == filter_fields['question_result'])
                if filter_fields['selected_choice_id'] == filter_fields['question_result']:
                    filter_fields['mark'] = 1
                else:
                    filter_fields['mark'] = 0

                obj = models.exam_response.objects.create(**filter_fields)
                #print('Exception in exam_response :',e)
                return Response({'status': True,'message': 'new entry'})
            except Exception as e:
                print('Exception in exam_response :',e)
                return Response({'status': False,'message': 'Error in saving'})


def get_summary(event_id,student_id):

    '''
    
    Function to return the summary content

    Return Fields
    `````````````
    total_questions     - Total number of questions
    not_answered        - Total questions not answered (Total number of questions - Number of visited questions)
    answered            - Total number of questions where answered field is not null
    reviewed            - Total number of questions where 'review' button is set as True
    vistedQuestions     - Total number of visited questions (Total number of entries in exam_response table)
    correct_answered    - Total number of questions which are correct (selected_choice_id == question_result)
    wrong_answered      - Total number of question which are incorrectly marked (selected_choice_id != question _result)
    marks               - Fetch from the event_attendance table

    '''

    try:
        event_attendance_query = models.event_attendance.objects.filter(event_id = event_id ,student_id = student_id)
        dict_obj = {}
        dict_obj['total_question'] = 0
        dict_obj['not_answered'] = 0
        dict_obj['answered'] = 0
        dict_obj['reviewed'] = 0
        dict_obj['vistedQuestion'] = 0
        dict_obj['correct_answered'] = 0
        dict_obj['wrong_answered'] = 0
        dict_obj['marks'] = 0

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
            dict_obj['marks']               = event_attendance_object.total_marks
        
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

    '''

    if settings.AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated
    
    def post(self,request,*args, **kwargs):

        try:
        
            data = JSONParser().parse(request)
            #print(data,data['event_id'])
            #print('---------',data['event_id'],request.user.id)
            return Response(get_summary(data['event_id'],request.user.id))

        except Exception as e:
            return Response({'status':False,'message':f'Exception occured {e}'})

class SummaryAll(APIView):
    '''
    class to return list of summaries

    input field
    ````````````

    event_id <- id or schedule_id


    '''
    if settings.AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated
    
    def post(self,request,*args, **kwargs):

        try:
            summary_list = []
            data = JSONParser().parse(request)

            for attendance_object in models.event_attendance.objects.filter(event_id=data['event_id']):
                #print(attendance_object.event_id,attendance_object.student_id.id)
                
                if attendance_object.end_time != None:
                #summary_consolidated
                    summary_consolidated = get_summary(attendance_object.event_id,attendance_object.student_id.id)
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
                    summary_consolidated['marks'] = '-'
                    summary_consolidated['completed'] = 0

                summary_consolidated['username'] = attendance_object.student_username
                summary_consolidated['name'] = attendance_object.student_id.profile.name_text
                summary_consolidated['section'] = attendance_object.student_id.profile.section
                summary_consolidated['class'] = attendance_object.student_id.profile.student_class

                summary_list.append(summary_consolidated)
            
            return Response(summary_list)

        except Exception as e:
            print(e)
            return Response({'status':False,'message':f'Exception occured {e}'})


class get_my_events(APIView):

    '''
    Class to fetch events for the users

    Note: For students, additional filter of class standard is added
    
    '''

    if settings.AUTH_ENABLE: 
        permission_classes = (IsAuthenticated,) # Allow only if authenticated 
    
    def post(self,request,*args, **kwargs): 
        
        try:
            #data = JSONParser().parse(request)

            # Filter based on the window allowed window size
            print('Fetch schedules between',(datetime.datetime.now().date() - datetime.timedelta(days=15)),(datetime.datetime.now().date() + datetime.timedelta(days=15)))
            
            events_queryset = models_scheduler.scheduling.objects.filter(
                event_enddate__gte = (datetime.datetime.now().date() - datetime.timedelta(days=15)),    # Greater than exam end date
                event_startdate__lte = (datetime.datetime.now().date() + datetime.timedelta(days=15))   # Lesser than exam start date
            )

            if request.user.profile.usertype == 'student':  # filter class for students
                events_queryset = events_queryset.filter(class_std=request.user.profile.student_class)
            
            events_serialized = serializers.exam_events_schedule_serializer(events_queryset,many=True,context={'user':request.user})
            return Response(events_serialized.data)

        except Exception as e:
            return Response({'status':'false','message':f'Error in get_my_events class {e}'})

class update_remtime(APIView):
    '''
    
    Store remaining time (Seconds)

    Input fields
    ````````````
    event_id <- id
    student_id <- request.user.id

    rem_time <- remaining time in seconds
    
    '''
    def post(self,request,*args, **kwargs):
        try:
            data = JSONParser().parse(request)
            data['event_id'] = data['id']

            attendance_object_check = models.event_attendance.objects.filter(event_id = data['event_id'] ,student_id = request.user)

            if attendance_object_check:
                attendance_object_check = attendance_object_check[0]
                attendance_object_check.remaining_time = data['rem_time']
                attendance_object_check.save()

                return Response({'message':'Remaining time updated successfully', 'status': True})
            else:
                return Response({'message':'No entry in the table availble for update'})
            #rem_time
        except Exception as e:
            return Response({'message':'No respose available','status':'false','Exception':e})

class exam_submit(APIView):

    '''

    submit the exam
    set end_time in the event_attendance table
    
    '''
    #permission_classes = (IsAuthenticated,) # Allow only if authenticated
    def post(self,request,*args, **kwargs):
        try:
            data = JSONParser().parse(request)
            data['event_id'] = data['id']
        except Exception as e:
            return Response({'message':"event_id 'id' not passed",'status':'false','exception':e})

        attendance_object_check = models.event_attendance.objects.filter(event_id = data['event_id'] ,student_id = request.user.id)

        #print('Attendance object ',len(attendance_object_check))

        # Fetch the total number of question from the meta data

        if len(attendance_object_check) != 0:


            attendance_object_check = attendance_object_check[0]
            attendance_object_check.end_time = datetime.datetime.now()
            attendance_object_check.total_questions = models.ExamMeta.objects.filter(event_id = data['event_id'])[0].no_of_questions
            total_marks         = 0
            visited_questions   = 0
            answered_questions  = 0
            reviewed_questions  = 0
            correct_answers     = 0
            wrong_answers       = 0
            for resp_obj in models.exam_response.objects.filter(event_id=data['event_id'],user=request.user.id):
                visited_questions += 1
                
                if resp_obj.selected_choice_id:
                    answered_questions += 1
                
                if resp_obj.review:
                    reviewed_questions += 1
                
                if resp_obj.selected_choice_id == resp_obj.question_result:
                    correct_answers += 1
                else:
                    wrong_answers += 1

                try:
                    total_marks += float(resp_obj.mark)
                except Exception as e:
                    print(f'Unable to convert: {resp_obj.mark} as float; Exception : {e}')
                
            attendance_object_check.total_marks         = total_marks
            attendance_object_check.visited_questions   = visited_questions
            attendance_object_check.answered_questions  = answered_questions
            attendance_object_check.reviewed_questions  = reviewed_questions
            attendance_object_check.correct_answers     = correct_answers
            attendance_object_check.wrong_answers       = wrong_answers
            
            attendance_object_check.save()

            return Response({'message' : 'Exam submitted','status':'true','total marks':total_marks})
        else:
            return Response({'message': 'No reponse available','status':'false'})


class school_exam_summary(APIView):
    '''
    Class to consolidate responses of a candidate upon completion

    input parameter
    `````````````````

    {
        "event_id":123,
        "user":13, #13,16
        "qp_set_id":15
    }

    
    '''

    if settings.AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated

    def post(self,request,*args, **kwargs):
        try:
            school_id = 30488 # Fetch from the API
            data = JSONParser().parse(request)

            filter_dict = {}
            filter_dict['event_id'] = data['event_id']
            filter_dict['user'] = data['user']
            filter_dict['qp_set_id'] = data['qp_set_id']

            file_name = f"cons_data/{data['event_id']}_{school_id}.json"
            
            
            print('Filtered values :',filter_dict)
            obj = models.exam_response.objects.filter(**filter_dict)

            if len(obj) == 0:
                return Response({"status":"No repsonse given by user for exam is available"})

            if not os.path.exists(file_name) or os.stat(file_name).st_size == 0:
                consolidated_data = {}
                consolidated_data = {
                    'event_id':data['event_id'],
                    'school_id':school_id,
                    'details':[]
                }

                with open(file_name, 'w') as outfile:  
                    json.dump(consolidated_data, outfile)

            with open(file_name,'r') as input_file:
                consolidated_data = json.load(input_file)

            candidate_consolidated = {}
            candidate_consolidated['student_username'] = data['user']
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
                json.dump(consolidated_data, outfile)
            print(consolidated_data)

            # todo json= 1 to be checked

            return Response(consolidated_data)
        except Exception as e:
            print(f'Exception raised while creating a candidate question meta data object throught API : {e}')


def get_answers(username,qid,qp_set_id,event_id):
    try:
        filter_fields = {
            'user':username,
            'question_id':qid,
            'qp_set_id':qp_set_id,
            'event_id':event_id
        }
        obj = get_object_or_404(models.exam_response,**filter_fields)

        ans = "" if obj.selected_choice_id == None else obj.selected_choice_id
        return obj.review, ans
    except:
        return "",""

class GenerateQuestionPaper(APIView):
    '''
    class to generate question paper per candidate

    Input parameters
    ````````````````

    {
        event_id : 123,

    }


    '''

    if settings.AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated

    def post(self,request,*args, **kwargs):

        # check if entry already exists and not completed

        #print('******',request.data)
        request_data = JSONParser().parse(request)

        request_data['event_id'] = request_data['id']

        print('---------------',request_data)

    
        event_attendance_check = models.event_attendance.objects.filter(event_id = request_data['event_id'] ,student_id = request.user.id)

      
        question_meta_object = models.ExamMeta.objects.filter(**{"event_id" : request_data['event_id']})


        if len(question_meta_object) > 0:
            question_meta_object = question_meta_object[0] # get the first instance
            print('question_meta_object Content',question_meta_object)
        else:
            return Response({'message':'No question set for this student','status':'false'})


        #Add an entry in the event_attenance_check
        if len(event_attendance_check) == 0:
            event_attendance_obj = models.event_attendance.objects.create(
                event_id = request_data['event_id'],
                student_id = request.user,
                student_username =request.user.username,
                qp_set = random.choice(eval(question_meta_object.qp_set_list)),
                remaining_time = question_meta_object.duration_mins * 60,  # return duration in seconds
                start_time = datetime.datetime.now()
            )
            event_attendance_obj.save()
        else:
            event_attendance_obj = event_attendance_check[0]
        

        qpset_filter = {
            'event_id': request_data['event_id'],
            'qp_set_id': event_attendance_obj.qp_set
        }

        exam_filter = {
            "event_id": request_data['event_id']
        }

        exam_meta_object_edit = models.ExamMeta.objects.filter(**exam_filter)
        print('------------------',len(exam_meta_object_edit))

        if len(exam_meta_object_edit) == 0:
            return Response({'status': 200, 'message': 'Event is not present.'})
        
        #Save Json File Into Schhool Local Server
        file_name = str(request_data['event_id']) + '_' + str(event_attendance_obj.qp_set)
        json_path =  file_name + '.json'
        FOLDER = 'questions_json'
        if not os.path.exists(FOLDER):
            os.mkdir(FOLDER)

        MEDIA_PATH ="/".join(settings.MEDIA_ROOT.split('/')[:-1]) + '/' + FOLDER
        json_file_path =  os.path.join(MEDIA_PATH, json_path)
     
        if os.path.exists(json_file_path):
            with open(json_file_path, 'r') as f:
                question_paper_data = json.load(f)
           
            print('----------------------------------------------------------------')
            print('Event ID and QP SET ID already exists in local school database..')
                    
            print('----------------------------------------------------------------')

            return Response(question_paper_data)

        else:
            exam_meta_data = []
            for exam_data in exam_meta_object_edit:
                tmp_exam_dict = model_to_dict(exam_data)
                try:
                    del tmp_exam_dict['qp_set_list']
                except KeyError:
                    pass
                
                tmp_exam_dict['qp_set_id'] = event_attendance_obj.qp_set
                tmp_exam_dict['exam_duration'] = event_attendance_obj.remaining_time # Fetch seconds
                tmp_exam_dict['end_alert_seconds'] = tmp_exam_dict['end_alert_time'] * 60 # Convert to seconds
                tmp_exam_dict['user'] = request.user.username
                exam_meta_data.append(tmp_exam_dict)
         
            qpset_filter = {
            'event_id': request_data['event_id'],
            'qp_set_id': event_attendance_obj.qp_set
            }
    
            print('--------------------------')
            qp_sets_object_edit = models.QpSet.objects.filter(**qpset_filter)
            qp_set_data = []  
            print('--------------------------')
            for qp_data in qp_sets_object_edit:
                print(qp_data)
                qp_set_data.append(model_to_dict(qp_data))
        
            qid_list = eval(qp_set_data[0]['qid_list'])
        

            qp_base64_list = []
            qp_base64_list_object_edit = models.Question.objects.filter(qid__in=qid_list)
            for qp_data in qp_base64_list_object_edit:
                qp_base64_list.append(model_to_dict(qp_data))

          

            choice_base64_list = []
            for qid in qid_list:
                filter = {
                    "qid": qid
                }

                choice_base64_list_object_edit = models.Choice.objects.filter(**filter)
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
                    if qp_img['qid'] == ch_img[0]['qid']:
                        tmp_ch_dict['q_choices'] = ch_img
                        qp_img.update(tmp_ch_dict)
            
                questions_data_list.append(qp_img)

            

            get_ans_api = []
            for q_id in qid_list:
                tmp = {}
                tmp['qid'] = q_id
                tmp['review'], tmp['ans'] = get_answers(request.user,q_id,event_attendance_obj.qp_set,request_data['event_id'])

                get_ans_api.append(tmp)

            configure_qp_data = exam_meta_data[0]
            configure_qp_data['qp_set_id'] = event_attendance_obj.qp_set
            configure_qp_data['q_ids'] = qid_list
            configure_qp_data['questions'] = questions_data_list
            configure_qp_data['ans'] = get_ans_api
            
            if not os.path.exists(MEDIA_PATH):
                os.makedirs(MEDIA_PATH)
            with open(json_file_path , 'w') as f :
                json.dump(configure_qp_data, f)

            return Response(configure_qp_data)
   
       
class LoadEvent(APIView):
    '''
    
    Class to fetch the event data from central  server

    Input parameter
    ```````````````

    {
        "school_id" : 30488
    }

    '''

    if settings.AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated

    def post(self,request,*args, **kwargs):
        try :
            
            cn = connection()

            if cn == None:
                data = {}
                data['dataStatus'] = False
                data['message'] = 'Server Not reachable'
                data['status'] = status.HTTP_504_GATEWAY_TIMEOUT
                return Response(data)
            
            mycursor = cn.cursor()

            query = f"SELECT school_id FROM {settings.DB_STUDENTS_SCHOOL_CHILD_COUNT} LIMIT 1"
            mycursor.execute(query)
            school_id_response = mycursor.fetchall()

            if len(school_id_response) == 0:
                return Response({'status':False,'message':'Registeration data not loaded yet'})

            print('School id :',school_id_response[0][0])

            
            # school_id = 30488
            CENTRAL_SERVER_IP = settings.CENTRAL_SERVER_IP
            req_url = f"http://{CENTRAL_SERVER_IP}/scheduler/get_events"
       
            school_id = school_id_response[0][0]
            payload = {
                "username" : 'test',
                "school_id" : school_id
            }

            print('-------payload------',payload)


            #get_events_response = requests.request("POST", req_url, data=payload)
            get_events_response = requests.request("POST", req_url, data=payload, verify=False, stream = True)

            res_fname = get_events_response.headers.get('Content-Disposition').split('=')[1]
            res_md5sum = get_events_response.headers.get('md5sum')
            request_type = get_events_response.headers.get('process_str')


            print(res_fname, res_md5sum)

            file_path = os.path.join(settings.MEDIA_ROOT, 'eventdata', res_fname.strip())
            eventpath = file_path.split(res_fname)[0]

            print(file_path, '-=--=--', eventpath)

            if not os.path.exists(eventpath):
                os.makedirs(eventpath)

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
            


            base_sqlite_path = settings.DATABASES['default']['NAME']
            print('DB name :',base_sqlite_path)

            eventcsvpath = os.path.join(eventpath,'tn_school_event')

                        #Drop table
            for file in os.listdir(eventcsvpath):
                if file.endswith(".csv"):
                    csv_full_path = os.path.join(eventcsvpath,file)
                    table_name = os.path.basename(csv_full_path).split('.')[0]
                    with sqlite3.connect(base_sqlite_path) as conn:
                        c = conn.cursor()
                        c.executescript(f"DROP TABLE IF EXISTS {table_name}")
                    conn.commit()
            print('Dropped old tables')

            # Load schema
            for file in os.listdir(eventcsvpath):
                if file.endswith(".sql"):
                    schema_path = os.path.join(eventcsvpath, file)
                    # load schema
                    with sqlite3.connect(base_sqlite_path) as conn:
                        c = conn.cursor()
                        with open(schema_path,'r') as file:
                            content = file.read()
                        c.executescript(content)
                    conn.commit()
            print('Loaded the schema')

            # Load data
            for file in os.listdir(eventcsvpath):
                if file.endswith(".csv"):
                    csv_full_path = os.path.join(eventcsvpath,file)
                    table_name = os.path.basename(csv_full_path).split('.')[0]
                    df = pd.read_csv(csv_full_path)
                    with sqlite3.connect('db.sqlite3') as conn:
                        c = conn.cursor()
                        df.to_sql(table_name,conn,if_exists='replace')
                        print('Data inserted successfully for :',table_name)
                        conn.commit()
            print('Loaded the csv file')

            print('Deleting all the file in ',eventpath)
            os.system(f"rm -rf {eventpath}")

            # send ack to central server

            ack_url = f"http://{settings.CENTRAL_SERVER_IP}/exammgt/acknowledgement-update"

            ack_payload = json.dumps({
                "school_id" : school_id_response[0][0],
                "request_type":request_type,
                "zip_hash":res_md5sum
            })

            requests.request("POST", ack_url, data=ack_payload)

            return Response({'api_status':True,'message':'Event data loaded'})
        except Exception as e:
            print(f'Exception raised while loading event data : {e}')
            return Response({'api_status':False,'message':f'Exception raised while loading event data : {e}'})

class LoadReg(APIView):

    '''
    class to load the registerations data
    '''
    def post(self,request,*args, **kwargs):
        try :

            # Extration of 7zip file

            CENTRAL_SERVER_IP = settings.CENTRAL_SERVER_IP
            req_url = "http://" + CENTRAL_SERVER_IP + "/exammgt/registeration-data"
       
            udise_code = request.data['udise']
            print(udise_code)
            payload = json.dumps({
                "udise_code" : request.data['udise'],
                "name":request.data['name'],
                "mobile_no":request.data['mobileno']

            })
          
            # get_events_response = requests.request("POST", reqUrl, data=payload)
            get_events_response = requests.request("POST", req_url, data=payload, verify=False, stream = True)


            res_fname = get_events_response.headers.get('Content-Disposition').split('=')[1]
            res_md5sum = get_events_response.headers.get('md5sum')
            request_type = get_events_response.headers.get('process_str')

            print(res_fname, res_md5sum)

            # os.system()


            file_path = os.path.join(settings.MEDIA_ROOT, 'regdata', res_fname.strip())
            #file_path = os.path.join(settings.MEDIA_ROOT, 'regdata', "regdata.7z")

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

            #regpath = os.path.join(file_path.split(res_fname)[0],'tn_registeration_data')

            regpath=file_path.split(res_fname)[0]

            # print('--- regpath',regpath)
            # if os.path.isdir(regpath):
            #     for f in os.listdir(regpath):
            #         os.remove(os.path.join(regpath, f))
            
            with py7zr.SevenZipFile(file_path, mode='r') as z:
                z.extractall(path=regpath)
            


            print('DB name :',settings.DATABASES['default']['NAME'])

            base_sqlite_path = settings.DATABASES['default']['NAME']

            print('---------')

            print('List of file',os.listdir(regpath))

            regcsvpath = os.path.join(regpath,'tn_registeration_data')

            #Drop table
            for file in os.listdir(regcsvpath):
                if file.endswith(".csv"):
                    csv_full_path = os.path.join(regcsvpath,file)
                    table_name = os.path.basename(csv_full_path).split('.')[0]
                    with sqlite3.connect(base_sqlite_path) as conn:
                        c = conn.cursor()
                        c.executescript(f"DROP TABLE IF EXISTS {table_name}")
                    conn.commit()
            print('Dropped old tables')

            # Load schema
            for file in os.listdir(regcsvpath):
                if file.endswith(".sql"):
                    schema_path = os.path.join(regcsvpath, file)
                    # load schema
                    with sqlite3.connect(base_sqlite_path) as conn:
                        c = conn.cursor()
                        with open(schema_path,'r') as file:
                            content = file.read()
                        c.executescript(content)
                    conn.commit()
            print('Loaded the schema')

            # Load data
            for file in os.listdir(regcsvpath):
                if file.endswith(".csv"):
                    csv_full_path = os.path.join(regcsvpath,file)
                    table_name = os.path.basename(csv_full_path).split('.')[0]
                    df = pd.read_csv(csv_full_path)
                    with sqlite3.connect('db.sqlite3') as conn:
                        c = conn.cursor()
                        df.to_sql(table_name,conn,if_exists='replace')
                        print('Data inserted successfully for ;',table_name)
                        conn.commit()
            print('Loaded the csv file')

            cn = connection()

            if cn == None:
                data = {}
                data['dataStatus'] = False
                data['message'] = 'Server Not reachable'
                data['status'] = status.HTTP_504_GATEWAY_TIMEOUT
                return Response(data)
            
            mycursor = cn.cursor()

            query = f"SELECT school_id FROM {settings.DB_STUDENTS_SCHOOL_CHILD_COUNT} LIMIT 1"
            mycursor.execute(query)
            school_id_response = mycursor.fetchall()

            if len(school_id_response) == 0:
                return Response({'reg_status':False,'message':'Registeration data not loaded yet'})

            # send ack to central server

            ack_url = f"http://{settings.CENTRAL_SERVER_IP}/exammgt/acknowledgement-update"

            ack_payload = json.dumps({
                "school_id" : school_id_response[0][0],
                "request_type":request_type,
                "zip_hash":res_md5sum
            })

            requests.request("POST", ack_url, data=ack_payload)

            return Response({'reg_status':True,'message':'Registeration data loaded'})
        except Exception as e:
            print(f'Exception raised while load registeration data throught API : {e}')
            return Response({'reg_status':False,'message':f'Exception raised while load registeration data throught API : {e}'})

class InitialReg(APIView):
    '''
    Class to fetch the school information 
    
    '''
    def post(self,request,*args, **kwargs):
        try:
            data = JSONParser().parse(request)
            #data = {'udise_code':33150901903}

            if 'udise_code' not in data:
                return Response({'status':False,'message':'udise_code not provided','school_name':''})
            
            req_url = f"http://{settings.CENTRAL_SERVER_IP}/exammgt/udise-info"

            payload = json.dumps({"udise_code": data['udise_code']})
            
            try:
                get_udise_response = requests.request("POST",req_url,data = payload)
                if get_udise_response.status_code != 200:
                    return Response({'api_status':False,'message':'Central server not reachable'})
            except Exception as e:
                return Response({'api_status':False,'message':'Central serval not reachable'})

            return Response(get_udise_response.json())
        
        except Exception as e:
            print('Exception caused during Initial Registeration :',e)
            return Response({'api_status':False,'message':'Exception caused during Initial Registeration'})

class MetaData(APIView):
    if settings.AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated

    def post(self,request,*args, **kwargs):
        try :
            
            cn = connection()

            if cn == None:
                data = {}
                data['dataStatus'] = False
                data['message'] = 'Server Not reachable'
                data['status'] = status.HTTP_504_GATEWAY_TIMEOUT
                return Response(data)
            
            mycursor = cn.cursor()

            query = f"SELECT school_id FROM {settings.DB_STUDENTS_SCHOOL_CHILD_COUNT} LIMIT 1"
            mycursor.execute(query)
            school_id_response = mycursor.fetchall()

            if len(school_id_response) == 0:
                return Response({'reg_status':False,'message':'Registeration data not loaded yet'})

            # request_data = JSONParser().parse(request)
            request_data = request.data

            print('-------------------------')

            #request_data['event_id'] = 2349
            req_url = f"http://{settings.CENTRAL_SERVER_IP}/paper/qpdownload"
            payload = json.dumps({
                'event_id':request_data['event_id'],
                'school_id':school_id_response[0][0]
            })

            get_meta_response = requests.request("POST", req_url, data=payload, verify=False, stream = True)

            if get_meta_response.status_code != 200:
                return Response({'api_status':False,'message':'Unable to load exam data','error':'Status not equal to 200'})
            
            res_fname = get_meta_response.headers.get('Content-Disposition').split('=')[1]
            res_md5sum = get_meta_response.headers.get('md5sum')
            request_type = get_meta_response.headers.get('process_str')


            print(res_fname, res_md5sum)

            file_path = os.path.join(settings.MEDIA_ROOT, 'examdata', res_fname.strip())
            questionpath = file_path.split(res_fname)[0]

            print(file_path, '-=--=--', questionpath)

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
                print('~~~~~~~~~~~~~',readable_hash)
            print(res_md5sum)

            if readable_hash != res_md5sum:
                return Response({'api_status':False,'message':'Unable to load exam data','error':'mismatch in md5checksum'})
            else:
                print('md5checksum correct')

            with py7zr.SevenZipFile(file_path, mode='r') as z:
                z.extractall(path=questionpath)
            

            base_sqlite_path = settings.DATABASES['default']['NAME']
            print('DB name :',base_sqlite_path)

            json_file_path = os.path.join(questionpath,'qpdownload_json')

            # request_data = {} 
            
            print('+++++++++++++++++++++++++++++++')
            #exammgt/media/examdata/qpdownload_json/meta_data_1_2022_08_12_14_55_35.json

            print('question path',questionpath)
            print('json file path',json_file_path)
            for file in os.listdir(json_file_path):
                if file.startswith('meta'):
                    print('File :',file)
                    print('full path :',os.path.join(json_file_path,file))
                    with open(os.path.join(json_file_path,file), 'r') as f:
                        meta_data = json.load(f)
            print(meta_data)

            event_meta_data = {}
            event_meta_data['event_id'] = meta_data['event_id']
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

            print('~~~~~~~~~~~~~~~~~~~')
            print(event_meta_data)

            iit_qp_set_list = []
            iit_question_id_list = []
            for meta in meta_data['qp_set_list']:
                iit_qp_set_list.append(meta['qp_set_id'])
                qp_list = meta['question_id_list']
                iit_question_id_list.append(qp_list)
            event_meta_data['qp_set_list'] = str(iit_qp_set_list) #we need string for store into database
            print('--------',event_meta_data)
          
            qp_set_data = []
            for qp_set, q_id in zip(iit_qp_set_list, iit_question_id_list):
                tmp_dict_data = {}
                tmp_dict_data['qp_set_id'] = qp_set
                tmp_dict_data['q_ids'] = q_id
                qp_set_data.append(tmp_dict_data)


            # Push the exam_meta_object_edit
            exam_meta_filter  = {
                "event_id" : request_data['event_id']
             
                }


            print(exam_meta_filter)
            exam_meta_object_edit = models.ExamMeta.objects.filter(**exam_meta_filter)
            if len(exam_meta_object_edit) == 0:
                serialized_exam_meta = serializers.ExamMetaSerializer(data=event_meta_data,many=False)
                if serialized_exam_meta.is_valid():
                    serialized_exam_meta.save()
                    
                else:
                    print(f'Error in serialization of Exam meta data : {serialized_exam_meta.errors}')
                    return Response({"status":status.HTTP_400_BAD_REQUEST,"content":"Incorrect data in serializing Exam Meta data","error":serialized_exam_meta.errors})

            else:
                print('\n')
                print('-----------------------------------------------------------')
                print('Event ID is already present into school local database....')
                
                print('-----------------------------------------------------------')


            # Read the question .json -> Qpset, Question and Choices

            for file in os.listdir(json_file_path):
                if file.startswith('qpdownload'):
                    print('File :',file)
                    print('full path :',os.path.join(json_file_path,file))
                    with open(os.path.join(json_file_path,file), 'r') as f:
                        qpdownload_list = json.load(f)


            #print('qpdownload list -------------',qpdownload_list)


            event_meta_data['qp_set_data'] = qp_set_data
            event_meta_data.update(qpdownload_list)

        # storing of reuse
        #     with open('exammgt/media/get_meta_data_' + str(request_data['event_id']) + '.json', 'w') as file:
        #         json.dump(event_meta_data, file)

        #     ######

            for qp_data in event_meta_data['qp_set_data']:
                tmp_qp_sets_data = {}
                tmp_qp_sets_data['event_id'] = event_meta_data['event_id']
                tmp_qp_sets_data['qp_set_id'] = qp_data['qp_set_id']
                tmp_qp_sets_data['qid_list'] = str(qp_data['q_ids'])
                
            
                qp_sets_filter  = {
                                "qp_set_id" : qp_data['qp_set_id']
                            }
                
                qp_set_object_edit = models.QpSet.objects.filter(**qp_sets_filter)
                if len(qp_set_object_edit) == 0:
                    serialized_qp_sets = serializers.QpSetsSerializer(data=tmp_qp_sets_data,many=False)
                    if serialized_qp_sets.is_valid():
                        serialized_qp_sets.save()
                        
                    else:
                        print(f'Error in serialization of QP Sets : {serialized_qp_sets.errors}')
                        return Response({"status":status.HTTP_400_BAD_REQUEST,"content":"Incorrect data in serializing QP Sets","error":serialized_qp_sets.errors})
                else:
                    print('\n')
                    print('-----------------------------------------------------------')
                    print('QP SET ID is already present into school local database....')
                    
                    print('-----------------------------------------------------------')


          
            for qp in event_meta_data['questions']:
                tmp_questions_data = {}
                tmp_questions_data['qid'] = qp['qid']
                tmp_questions_data['qimage'] = qp['qimage']
                tmp_questions_data['no_of_choices'] = qp['no_of_choices']
                tmp_questions_data['correct_choice'] = qp['correct_choice']
                
                questions_filter  = {
                            "qid" : qp['qid']
                        }

                questions_object_edit = models.Question.objects.filter(**questions_filter)
                if len(questions_object_edit) == 0:
                    serialized_questions = serializers.QuestionsSerializer(data=tmp_questions_data,many=False)
                    if serialized_questions.is_valid():
                        serialized_questions.save()
                        
                    else:
                        print(f'Error in serialization of questions : {serialized_questions.errors}')
                        return Response({"status":status.HTTP_400_BAD_REQUEST,"content":"Incorrect data in serializing questions","error":serialized_questions.errors})
                else:
                    print('\n')
                    print('-----------------------------------------------------------')
                    print('Question ID is already present into school local database....')
                    
                    print('-----------------------------------------------------------')
                    


            
            for ch in event_meta_data['questions']:
                for ch_img in ch['q_choices']:
                    tmp_choice_data = {}
                    tmp_choice_data['qid'] = ch['qid']
                    tmp_choice_data['cid'] = ch_img['cid']
                    tmp_choice_data['cimage'] = ch_img['cimage']

                    choice_filter  = {
                            # "qid" : qp['qid'],
                            "cid" : ch_img['cid']
                        }

                    choice_object_edit = models.Choice.objects.filter(**choice_filter)
                    if len(choice_object_edit) == 0:
                        serialized_choice= serializers.ChoicesSerializer(data=tmp_choice_data,many=False)
                        if serialized_choice.is_valid():
                            serialized_choice.save()
                            
                        else:
                            print(f'Error in serialization of choices : {serialized_choice.errors}')
                            return Response({"status":status.HTTP_400_BAD_REQUEST,"content":"Incorrect data in serializing choices","error":serialized_choice.errors})
                    else:
                        print('\n')
                        print('------------------------------------------------------------------------')
                        print('Question ID and Choice ID is already present into school local database..')
                        
                        print('-------------------------------------------------------------------------')
            
            ack_url = f"http://{settings.CENTRAL_SERVER_IP}/exammgt/acknowledgement-update"

            ack_payload = json.dumps({
                "school_id" : school_id_response[0][0],
                "request_type":request_type,
                "zip_hash":res_md5sum
            })

            requests.request("POST", ack_url, data=ack_payload) 
            event_meta_data['api_status'] = True
            return Response(event_meta_data)

        except Exception as e:
            print(f'Exception raised while creating a meta data object throught API : {e}')
            return Response({"status":False,"message": f'{e}'})

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
                data['dataStatus'] = False
                data['message'] = 'Server Not reachable'
                data['status'] = status.HTTP_504_GATEWAY_TIMEOUT
                return Response(data)
            
            field_names = ['udise_code','school_id','school_name','school_type','district_id','district_name','block_id','block_name']


            mycursor = cn.cursor()

            query = f"SELECT {','.join([str(elem) for elem in field_names])} FROM {settings.DB_STUDENTS_SCHOOL_CHILD_COUNT} LIMIT 1;"
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
            })

        except Exception as e:
            print('Exception caused while fetching school details :',e)
            return Response({'api_status':False,'message':'Unable to fetch school details','school_name':''})
