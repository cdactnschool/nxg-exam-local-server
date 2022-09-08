
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


from .serializers import ExamEventsScheduleSerializer, QuestionsSerializer, ChoicesSerializer, ExamMetaSerializer, QpSetsSerializer
from .models import Profile, ExamResponse, EventAttendance, ExamMeta, QpSet, Question, Choice, MiscInfo 
from scheduler.models import participants, scheduling, event

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

import shutil


logger      = logging.getLogger('monitoringdebug')
accesslog   = logging.getLogger('accesslog')
errorlog    = logging.getLogger('errorlog')
infolog     = logging.getLogger('infolog')
apilog      = logging.getLogger('apilog')
student_start_log = logging.getLogger('student_start_log')
student_end_log = logging.getLogger('student_end_log')
student_log = logging.getLogger('student_log')

import sqlite3
import py7zr



from django.db.models import Q

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
        conn = sqlite3.connect(settings.DATABASES['default']['NAME'])
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

    auth_fields = settings.AUTH_FIELDS

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

    if Profile.objects.filter(user=db_user).exists():
        profile_instance = Profile.objects.get(user=db_user)
    else:
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
        "api_status": true,
        "message": "User authenticated"
        }

    '''

    def post(self,request):

        try:

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

            auth_fields = settings.AUTH_FIELDS

            # Teacher /HM
            if str(data['username']).isnumeric() and (len(str(data['username'])) == auth_fields['teacher_hm']['username_len']):
                possible_type = 'teacher_hm'
                #print('Possible user type - ',possible_type)
                query = f"SELECT {auth_fields['teacher_hm']['username_field']}, {auth_fields['teacher_hm']['hash_field']} FROM {auth_fields['teacher_hm']['auth_table']} WHERE {auth_fields['teacher_hm']['username_field']} = {data['username']} AND status = 'Active' LIMIT 1"     

                        
                #print('###########',query)
                mycursor.execute(query)
                auth_detail_response = mycursor.fetchall()
                
                if len(auth_detail_response) == 0:
                    return Response({'api_status':False,'message':'Incorrect username'})
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
                    return Response({'api_status':False,'possible_type':possible_type,'message':'Incorrect Username/password'})

            # student


            elif (str(data['username']).isnumeric()) and (len(str(data['username'])) == auth_fields['student']['username_len']):
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
                    return Response(token_response)
                else:
                    return Response({'api_status':False,'possible_type':possible_type,'message':'Incorrect Username/password'})
            
            # No authentication for department user in local
            else:
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
    
    '''
    
    def post(self,request,*args, **kwargs):
        data = JSONParser().parse(request)

        filter_fields = {
            'student_username':request.user.username,
            'question_id':data['qid'],
            'qp_set_id':data['qp_set_id'],
            'event_id':data['event_id']
        }
        try:
            print(request.user.username)
            print(filter_fields)
            object_edit = get_object_or_404(ExamResponse,**filter_fields)
            print('--------------',object_edit)
            object_edit.selected_choice_id = None if data['ans'] == '' else data['ans']
            object_edit.question_result = data['correct_choice']
            object_edit.review = data['review']
            object_edit.save()
            
            return Response({'api_status': True,'message':'updated'})
        except Exception as e:

            print('Exception element :',e)
            try:            
                filter_fields['selected_choice_id'] = None if data['ans'] == '' else data['ans']
                filter_fields['question_result'] = data['correct_choice']
                filter_fields['review'] = data['review']


                obj = ExamResponse.objects.create(**filter_fields)
                #print('Exception in ExamResponse :',e)
                return Response({'api_status': True,'message': 'new entry'})
            except Exception as e:
                print('Exception in ExamResponse :',e)
                return Response({'api_status': False,'message': 'Error in saving response'})


def get_summary(event_id,student_username):

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

    '''

    if settings.AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated
    
    def post(self,request,*args, **kwargs):

        try:
        
            data = JSONParser().parse(request)
            #print(data,data['event_id'])
            #print('---------',data['event_id'],request.user.username)
            return Response(get_summary(data['event_id'],request.user.username))

        except Exception as e:
            return Response({'api_status':False,'message':'Error in generating summary','exception':f'Exception occured in message : {e}'})

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

            for attendance_object in EventAttendance.objects.filter(event_id=data['event_id']):
                #print(attendance_object.event_id,attendance_object.student_username)
                
                if attendance_object.end_time != None:
                #summary_consolidated
                    summary_consolidated = get_summary(attendance_object.event_id,attendance_object.student_username)
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

    if settings.AUTH_ENABLE: 
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

            events_serialized = ExamEventsScheduleSerializer(events_queryset,many=True,context={'user':request.user})

            events_serialized_data = {
                'api_status':True,
                'data':events_serialized.data
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
    
    '''
    def post(self,request,*args, **kwargs):
        try:
            data = JSONParser().parse(request)
            data['event_id'] = data['id']

            attendance_object_check = EventAttendance.objects.filter(event_id = data['event_id'] ,student_username = request.user.username)

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

        attendance_object_check = EventAttendance.objects.filter(event_id = data['event_id'] ,student_username = request.user.username)

        #print('Attendance object ',len(attendance_object_check))

        # Fetch the total number of question from the meta data

        if len(attendance_object_check) != 0:


            attendance_object_check = attendance_object_check[0]
            attendance_object_check.end_time = datetime.datetime.now()
            attendance_object_check.total_questions = ExamMeta.objects.filter(event_id = data['event_id'])[0].no_of_questions
            visited_questions   = 0
            answered_questions  = 0
            reviewed_questions  = 0
            correct_answers     = 0
            wrong_answers       = 0
            for resp_obj in ExamResponse.objects.filter(event_id=data['event_id'],student_username=request.user.username,qp_set_id=attendance_object_check.qp_set):
                visited_questions += 1
                
                if resp_obj.selected_choice_id:
                    answered_questions += 1
                
                    if resp_obj.selected_choice_id == resp_obj.question_result:
                        correct_answers += 1
                    else:
                        wrong_answers += 1
                
                if resp_obj.review:
                    reviewed_questions += 1
                

                
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

    if settings.AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated

    def post(self,request,*args, **kwargs):
        try:
            school_id = 30488 # Fetch from the API
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


def get_answers(username,qid,qp_set_id,event_id):
    try:
        print('&&&& Fetching answers for ',username,qid,qp_set_id,event_id)
        filter_fields = {
            'student_username':username,
            'question_id':qid,
            'qp_set_id':qp_set_id,
            'event_id':event_id
        }
        obj = get_object_or_404(ExamResponse,**filter_fields)

        ans = "" if obj.selected_choice_id == None else obj.selected_choice_id
        return obj.review, ans
    except Exception as e:
        print(e)
        return "",""

class GenerateQuestionPaper(APIView):
    '''
    class to generate question paper per candidate

    Input parameters
    ````````````````

    {
        id : 123,

    }


    '''

    if settings.AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated

    def post(self,request,*args, **kwargs):

        try:

            # check if entry already exists and not completed

            #print('******',request.data)
            # request_data = JSONParser().parse(request)
            request_data = request.data

            print('-------------request-data-------------',request_data)

            request_data['event_id'] = request_data['id']

            print('---------------',request_data)

        
            event_attendance_check = EventAttendance.objects.filter(event_id = request_data['event_id'] ,student_username = request.user.username)

        
            question_meta_object = ExamMeta.objects.filter(**{"event_id" : request_data['event_id']})


            if len(question_meta_object) > 0:
                question_meta_object = question_meta_object[0] # get the first instance
                print('question_meta_object Content',question_meta_object)
            else:
                return Response({'api_status':False,'message':'No question set for this student'})


            #Add an entry in the event_attenance_check
            if len(event_attendance_check) == 0:
                
                print('---remaining---time',question_meta_object.duration_mins)

                event_attendance_obj = EventAttendance.objects.create(
                    event_id = request_data['event_id'],
                    student_username =request.user.username,
                    qp_set = random.choice(eval(question_meta_object.qp_set_list)),
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
                "event_id": request_data['event_id']
            }
            
            #Save Json File Into Schhool Local Server
            #file_name = str(request_data['event_id']) + '_' + str(event_attendance_obj.qp_set)
            json_path = "{0}_{1}.json".format(request_data['event_id'] ,event_attendance_obj.qp_set)
            
            FOLDER = os.path.join(settings.MEDIA_ROOT,'questions_json')

            if not os.path.exists(FOLDER):
                os.mkdir(FOLDER)
            exam_meta_object_edit = ExamMeta.objects.filter(**exam_filter)
            #MEDIA_PATH ="/".join(settings.MEDIA_ROOT.split('/')[:-1]) + '/' + FOLDER
            json_file_path =  os.path.join(FOLDER, json_path)

            print('QP json file existance status',os.path.exists(json_file_path))

            if os.path.exists(json_file_path):
                with open(json_file_path, 'r') as f:
                    question_paper_data = json.load(f)
            
                print('----------------------------------------------------------------')
                print('Event ID and QP SET ID already exists in local school database..',json_file_path)
                        
                print('----------------------------------------------------------------')

                for answers in question_paper_data['ans']:
                    answers['review'], answers['ans'] = get_answers(request.user.username,answers['qid'],event_attendance_obj.qp_set,request_data['event_id'])
                question_paper_data['user'] = request.user.username
                question_paper_data['qp_set_id'] = event_attendance_obj.qp_set
                question_paper_data['exam_duration'] = event_attendance_obj.remaining_time # Fetch seconds
                #question_paper_data['end_alert_seconds'] = question_paper_data['end_alert_time'] * 60 # Convert to seconds

                question_paper_data['api_status'] = True

                return Response(question_paper_data)

            else:
                exam_meta_data = []
                for exam_data in exam_meta_object_edit:
                    tmp_exam_dict = model_to_dict(exam_data)
                    try:
                        del tmp_exam_dict['event_startdate']
                        del tmp_exam_dict['event_enddate']
                        del tmp_exam_dict['qp_set_list']
                    except:
                        pass
                    
                    tmp_exam_dict['qp_set_id'] = event_attendance_obj.qp_set
                    tmp_exam_dict['exam_duration'] = event_attendance_obj.remaining_time # Fetch seconds
                    #tmp_exam_dict['end_alert_seconds'] = tmp_exam_dict['end_alert_time'] * 60 # Convert to seconds
                    exam_meta_data.append(tmp_exam_dict)

                    print('------exam_meta---------',exam_meta_data)
            
                qpset_filter = {
                'event_id': request_data['event_id'],
                'qp_set_id': event_attendance_obj.qp_set
                }
        
                print('--------------------------')
                qp_sets_object_edit = QpSet.objects.filter(**qpset_filter)
                qp_set_data = []  
                print('--------------------------')
                for qp_data in qp_sets_object_edit:
                    print(qp_data)
                    qp_set_data.append(model_to_dict(qp_data))
            
                qid_list = eval(qp_set_data[0]['qid_list'])

                print('---------start----qp_base---------')

                qp_base64_list = []
                qp_base64_list_object_edit = Question.objects.filter(qid__in=qid_list)
                for qp_data in qp_base64_list_object_edit:
                    qp_base64_list.append(model_to_dict(qp_data))

                print('-------qp_base--------')

                choice_base64_list = []
                for qid in qid_list:
                    filter = {
                        "qid": qid
                    }

                    choice_base64_list_object_edit = Choice.objects.filter(**filter)
                    choice_base64_list_object = []
                    for ch_data in choice_base64_list_object_edit:
                        tmp_dict_data = model_to_dict(ch_data)
                        # del tmp_dict_data['qid']
                        choice_base64_list_object.append(tmp_dict_data)

                    choice_base64_list.append(choice_base64_list_object)

                print('-----------choice----------')

                questions_data_list =[]
                for qp_img in qp_base64_list:
                    for ch_img in choice_base64_list:
                        tmp_ch_dict = {}
                        if qp_img['qid'] == ch_img[0]['qid']:
                            tmp_ch_dict['q_choices'] = ch_img
                            qp_img.update(tmp_ch_dict)
                
                    questions_data_list.append(qp_img)

                print('-------questions-------------------')

                get_ans_api = []
                for q_id in qid_list:
                    tmp = {}
                    tmp['qid'] = q_id
                    tmp['review'], tmp['ans'] = get_answers(request.user.username,q_id,event_attendance_obj.qp_set,request_data['event_id'])

                    get_ans_api.append(tmp)

                configure_qp_data = exam_meta_data[0]
                configure_qp_data['qp_set_id'] = event_attendance_obj.qp_set
                configure_qp_data['q_ids'] = qid_list
                configure_qp_data['questions'] = questions_data_list
                configure_qp_data['ans'] = get_ans_api
                

                print('------------configure_qp_data------------')
                print(configure_qp_data)

                for c in configure_qp_data:
                    print(c,configure_qp_data[c])


                #if not os.path.exists(MEDIA_PATH):
                #    os.makedirs(MEDIA_PATH)
                with open(json_file_path , 'w') as f :
                    json.dump(configure_qp_data, f,default=str)
                configure_qp_data['user'] = request.user.username
                configure_qp_data['api_status'] = True
                return Response(configure_qp_data)
        except Exception as e:
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

    # if settings.AUTH_ENABLE:
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

            query = f"SELECT {settings.AUTH_FIELDS['school']['school_id']} FROM {settings.AUTH_FIELDS['school']['auth_table']} LIMIT 1"
            mycursor.execute(query)
            school_id_response = mycursor.fetchall()

            if len(school_id_response) == 0:
                return Response({'api_status':False,'message':'Registeration data not loaded yet'})

            print('School id :',school_id_response[0][0])

            
            # school_id = 30488
            CENTRAL_SERVER_IP = settings.CENTRAL_SERVER_IP
            req_url = f"{CENTRAL_SERVER_IP}/scheduler/get_events"
       
            school_id = school_id_response[0][0]
            payload = {
                "school_id" : school_id,
                "school_token":get_school_token()
            }

            print('-------payload------',payload)


            #get_events_response = requests.request("POST", req_url, data=payload)
            get_events_response = requests.request("POST", req_url, data=payload, verify=settings.CERT_FILE, stream = True)


            # Check if school has no events

            if get_events_response.headers.get('content-type') == 'application/json':
                if 'md5sum' in get_events_response.json():
                    if get_events_response.json()['md5sum'] == 'None':
                        return Response({'api_status':True,'message':'No Events allocated for this school yet','school_token':get_school_token()})


            res_md5sum = get_events_response.headers.get('md5sum')
            res_fname = get_events_response.headers.get('Content-Disposition').split('=')[1]
            request_type = get_events_response.headers.get('process_str')

            event_id_list = get_events_response.headers.get('event_id_list')
            if type(event_id_list) != list:
                event_id_list = eval(event_id_list)



            print(res_fname, res_md5sum)
            load_event_base = os.path.join(settings.MEDIA_ROOT, 'eventdata')
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
            


            base_sqlite_path = settings.DATABASES['default']['NAME']
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

            ack_url = f"{settings.CENTRAL_SERVER_IP}/exammgt/acknowledgement-update"

            ack_payload = json.dumps({
                "school_id" : school_id_response[0][0],
                "request_type":request_type,
                "zip_hash":res_md5sum,
                "school_token":get_school_token(),
                "event_id_list":event_id_list
            },default=str)

            requests.request("POST", ack_url, data=ack_payload,verify=settings.CERT_FILE)

            # Deleting the residual files

            shutil.rmtree(load_event_base,ignore_errors=False,onerror=None)

            if MiscInfo.objects.all().count() == 0:
                MiscInfo.objects.create(event_dt = datetime.datetime.now())
            else :
                misc_obj = MiscInfo.objects.all().first()
                misc_obj.event_dt = datetime.datetime.now()
                misc_obj.save()

            return Response({'api_status':True,'message':'Event data loaded','school_token':get_school_token()})
        except Exception as e:
            print(f'Exception raised while loading event data : {e}')
            return Response({'api_status':False,'message':'unable to fetch events','exception':f'Exception raised while loading event data : {e}','school_token':get_school_token()})

class LoadReg(APIView):

    '''
    class to load the registerations data
    '''
    def post(self,request,*args, **kwargs):
        try :

            # Extration of 7zip file

            CENTRAL_SERVER_IP = settings.CENTRAL_SERVER_IP
            req_url = f"{CENTRAL_SERVER_IP}/exammgt/registeration-data"
       
            udise_code = request.data['udise']
            print(udise_code)

            payload = json.dumps({
                "udise_code" : request.data['udise'],
                "name":request.data['name'],
                "mobile_no":request.data['mobileno'],
                "school_token":get_school_token()

            },default=str)
          
            # get_events_response = requests.request("POST", reqUrl, data=payload)
            get_events_response = requests.request("POST", req_url, data=payload, verify=settings.CERT_FILE, stream = True)

            if get_events_response.headers.get('content-type') == 'application/json':
                return Response(get_events_response.json())

            res_fname = get_events_response.headers.get('Content-Disposition').split('=')[1]
            res_md5sum = get_events_response.headers.get('md5sum')
            request_type = get_events_response.headers.get('process_str')
            school_token = get_events_response.headers.get('school_token')

            print(res_fname, res_md5sum)

            # os.system()

            load_reg_base = os.path.join(settings.MEDIA_ROOT, 'regdata')

            file_path = os.path.join(load_reg_base, res_fname.strip())
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

            regpath = os.path.join(file_path.split(res_fname)[0],'tn_registeration_data')

            #regpath=file_path.split(res_fname)[0]

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

            #regcsvpath = os.path.join(regpath,'tn_registeration_data')
            regcsvpath = regpath

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
                    with sqlite3.connect(base_sqlite_path) as conn:
                        c = conn.cursor()
                        df.to_sql(table_name,conn,if_exists='replace')
                        print('Data inserted successfully for ;',table_name)
                        conn.commit()
            print('Loaded the csv file')

            cn = connection()

            if cn == None:
                data = {}
                data['api_status'] = False
                data['message'] = 'School server Not reachable'
                return Response(data)
            
            mycursor = cn.cursor()

            query = f"SELECT {settings.AUTH_FIELDS['school']['school_id']} FROM {settings.AUTH_FIELDS['school']['auth_table']} LIMIT 1"
            mycursor.execute(query)
            school_id_response = mycursor.fetchall()

            if len(school_id_response) == 0:
                return Response({'api_status':False,'message':'Registeration data not loaded yet'})


            print('-----print---token-----',get_school_token(),'-------------')

            # send ack to central server

            ack_url = f"{settings.CENTRAL_SERVER_IP}/exammgt/acknowledgement-update"

            ack_payload = json.dumps({
                "school_id" : school_id_response[0][0],
                "request_type":request_type,
                "zip_hash":res_md5sum,
                "school_token":get_school_token()
            },default=str)

            requests.request("POST", ack_url, data=ack_payload,verify=settings.CERT_FILE)

            # Delete residual files
            shutil.rmtree(load_reg_base,ignore_errors=False,onerror=None)

            # Create groups
            try:
                Group.objects.create(name='student')
                Group.objects.create(name='teacher')
                Group.objects.create(name='hm')
                Group.objects.create(name='department')
                print('^^^Created Groups^^^^')
            except Exception as e:
                print('Exception in creating groups :',e)

            if MiscInfo.objects.all().count() == 0:
                MiscInfo.objects.create(reg_dt = datetime.datetime.now(),school_token=school_token)
            else :
                misc_obj = MiscInfo.objects.all().first()
                misc_obj.reg_dt = datetime.datetime.now()
                misc_obj.school_token = school_token
                misc_obj.save()

            return Response({'api_status':True,'message':'Registeration data loaded'})
        except Exception as e:
            print(f'Exception raised while load registeration data throught API : {e}')
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
            
            req_url = f"{settings.CENTRAL_SERVER_IP}/exammgt/udise-info"

            payload = json.dumps({"udise_code": data['udise_code']},default=str)
            
            try:
                get_udise_response = requests.request("POST",req_url,data = payload,verify=settings.CERT_FILE)
                if get_udise_response.status_code != 200:
                    return Response({'api_status':False,'message':'Central server not reachable'})
            except Exception as e:
                return Response({'api_status':False,'message':'Error in fetching data from Central server','exception':str(e)})
            udise_response_json = get_udise_response.json()
            return Response(udise_response_json)
        
        except Exception as e:
            print('Exception caused during Initial Registeration :',e)
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
    # if settings.AUTH_ENABLE:
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

            query = f"SELECT {settings.AUTH_FIELDS['school']['school_id']} FROM {settings.AUTH_FIELDS['school']['auth_table']} LIMIT 1"
            mycursor.execute(query)
            school_id_response = mycursor.fetchall()

            if len(school_id_response) == 0:
                return Response({'api_status':False,'message':'Registeration data not loaded yet'})

            # request_data = JSONParser().parse(request)
            request_data = request.data

            print('-------------------------')
            
            if scheduling.objects.filter(schedule_id=request_data['event_id']).exists() == False:
                return Response({'api_status':False,'message':'Event Not allocated for this school'})

            
            scheduling_queryset = scheduling.objects.get(schedule_id=request_data['event_id'])
            

            #request_data['event_id'] = 2349
            req_url = f"{settings.CENTRAL_SERVER_IP}/paper/qpdownload"
            payload = json.dumps({
                'event_id':request_data['event_id'],
                'school_id':school_id_response[0][0],
                'school_token':get_school_token()
            },default=str)

            get_meta_response = requests.request("POST", req_url, data=payload, verify=settings.CERT_FILE, stream = True)
            if get_meta_response.headers.get('content-type') == 'application/json':
                get_meta_response_json = get_meta_response.json()
                if get_meta_response_json['api_status'] == False:
                    return Response({'api_status':False,'message':'Question paper not available in central server'})

            if get_meta_response.status_code != 200:
                return Response({'api_status':False,'message':'Unable to load exam data','error':'Status not equal to 200'})
            
            res_fname = get_meta_response.headers.get('Content-Disposition').split('=')[1]
            res_md5sum = get_meta_response.headers.get('md5sum')
            request_type = get_meta_response.headers.get('process_str')


            print(res_fname, res_md5sum)

            # Delete residual files
            load_meta_base = os.path.join(settings.MEDIA_ROOT, 'examdata')

            file_path = os.path.join(load_meta_base, res_fname.strip())
            questionpath = os.path.join(file_path.split(res_fname)[0],f"{request_data['event_id']}_{school_id_response[0][0]}_qpdownload_json")

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
            json_file_path = questionpath #os.path.join(questionpath,f"{request_data['event_id']}_{school_id_response[0][0]}_qpdownload_json")

            # print('question path',questionpath)
            # print('json file path',json_file_path)
            for file in os.listdir(json_file_path):
                if file.startswith('meta'):
                    # print('File :',file)
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
            event_meta_data['qp_set_list'] = str(meta_data['school_qp_sets'])
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

            print('-----------event---meta-----data-----',event_meta_data)

          
            qp_set_data = []
            for qp_set, q_id in zip(iit_qp_set_list, iit_question_id_list):
                tmp_dict_data = {}
                tmp_dict_data['qp_set_id'] = qp_set
                tmp_dict_data['q_ids'] = q_id
                qp_set_data.append(tmp_dict_data)
            
            event_meta_data['qp_set_data'] = qp_set_data

            # Push the exam_meta_object_edit
            exam_meta_filter  = {
                "event_id" : request_data['event_id']
             
                }
            
            event_meta_data['event_title'] = scheduling_queryset.event_title
            event_meta_data['class_std'] = scheduling_queryset.class_std
            event_meta_data['class_section'] = scheduling_queryset.class_section
            event_meta_data['event_startdate'] = scheduling_queryset.event_startdate
            event_meta_data['event_enddate'] = scheduling_queryset.event_enddate
            event_meta_data['class_subject'] = scheduling_queryset.class_subject


            print('-----------event---meta-----data-----',event_meta_data)

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
                                    "qp_set_id" : qp_data['qp_set_id']
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
                    with open(os.path.join(json_file_path,file), 'r') as f:
                        qpdownload_list = json.load(f)

                    #print(qpdownload_list)
                    try:
                        load_question_choice_data(qpdownload_list)
                    except:
                        return Response({'api_status':False,'message':'Error reading json meta data...!'})


            ack_url = f"{settings.CENTRAL_SERVER_IP}/exammgt/acknowledgement-update"

            ack_payload = json.dumps({
                "school_id" : school_id_response[0][0],
                "request_type":request_type,
                "zip_hash":res_md5sum,
                "school_token":get_school_token(),
                "event_id_list":[request_data['event_id']]
            },default=str)

            requests.request("POST", ack_url, data=ack_payload, verify=settings.CERT_FILE) 
      
            os.system('rm -rf ' + json_file_path)

            # Delete residual files

            shutil.rmtree(load_meta_base,ignore_errors=False,onerror=None)


            return Response({'api_status':True,'message':'Meta data loaded successfully'})
         
        except Exception as e:
            print(f'Exception raised while creating a meta data object throught API : {e}')
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
                'api_status':True
                
            })

        except Exception as e:
            print('No school details :',e)
            return Response({'api_status':False,'message':'No school details'})


class ConsSummary(APIView):
    '''
    Class to fetch display all candidates details and exam result for the particular event

    input parameter
    ```````````````

    event_id <- schedule_id or event_id

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

            students_query = f" SELECT l.{settings.AUTH_FIELDS['student']['username_field']}, r.{settings.AUTH_FIELDS['student']['name_field_master']}, r.{settings.AUTH_FIELDS['student']['student_class']}, r.{settings.AUTH_FIELDS['student']['section_field_master']} FROM {settings.AUTH_FIELDS['student']['auth_table']} l LEFT JOIN {settings.AUTH_FIELDS['student']['master_table']} r ON l.{settings.AUTH_FIELDS['student']['school_field_foreign']} = r.{settings.AUTH_FIELDS['student']['school_field_foreign_ref']} WHERE r.{settings.AUTH_FIELDS['student']['student_class']} = {scheduling_obj.class_std}"
            if scheduling_obj.class_section != None:
                students_query = f"{students_query} AND r.{settings.AUTH_FIELDS['student']['section_field_master']} = '{scheduling_obj.class_section}'"

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

                individual_summary.update(get_summary(event_id=request_data['event_id'],student_username = individual_summary['emis_username'] ))

                print(individual_summary)
                consolidated_summary.append(individual_summary)

            print('Total number of students',len(students_emis_username))

            return Response({'api_status':True,'data':consolidated_summary})
        except Exception as e:
            print('Exception caused while fetching consolidated summary :',e)
            return Response({'api_status':False,'message':'Unable to fetch consolidated summary'})


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

    if settings.AUTH_ENABLE:
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
    # if settings.AUTH_ENABLE:
    #     permission_classes = (IsAuthenticated,) # Allow only if authenticated
    def post(self, request, *args,**kwargs):
        
        try:
            event_id = request.data['event_id']

            if scheduling.objects.filter(schedule_id=event_id).exists() == False:
                return Response({'api_status':False,'message':'Event Not allocated for this school'})

            
            scheduling_queryset = scheduling.objects.get(schedule_id=event_id)

            file_obj = request.data['archive']
            file_name = file_obj.name

            file_path = os.path.join(settings.MEDIA_ROOT,'examdata')

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

            for file in os.listdir(json_file_path):
                    if file.startswith('meta'):
                        # print('File :',file)
                        print('full path :',os.path.join(json_file_path,file))
                        with open(os.path.join(json_file_path,file), 'r') as f:
                            meta_data = json.load(f)
            print(meta_data)

            if meta_data == None:
                return Response({'api_status':False,'message':'Incorrect Mapping File'})

            print(f"--------{meta_data['event_id']}---------{event_id}")
            if meta_data['event_id'] != event_id:
                return Response({'api_status':False,'message':'Incorrect Mapping File'})

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
            event_meta_data['qp_set_list'] = str(meta_data['school_qp_sets'])
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
                                    "qp_set_id" : qp_data['qp_set_id']
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
                    with open(os.path.join(json_file_path,file), 'r') as f:
                        qpdownload_list = json.load(f)

                    #print(qpdownload_list)
                    try:
                        load_question_choice_data(qpdownload_list)
                    except Exception as e:
                        return Response({'api_status':False,'message':'Error reading qpdownload json data...!','exception':str(e)})

            # Delete residual file
            shutil.rmtree(file_path,ignore_errors=False,onerror=None)
            

            # return Response({'api_status':True,'dir':dir(file_obj),'name':file_obj.name,'type':file_obj.content_type})
            return Response({'api_status':True,'message':'Meta data uploaded successfully'})
        except Exception as e:
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

            query = f"SELECT {settings.AUTH_FIELDS['school']['school_id']} FROM {settings.AUTH_FIELDS['school']['auth_table']} LIMIT 1"
            mycursor.execute(query)
            school_id_response = mycursor.fetchall()

            if len(school_id_response) == 0:
                return Response({'api_status':False,'message':'Registeration data not loaded yet'})


            print('-----print---token-----',get_school_token(),'-------------')

            print('-----print--school-id',school_id_response[0][0])

            # API to delete entry from central server

            dereg_url = f"{settings.CENTRAL_SERVER_IP}/exammgt/de-registeration"

            dereg_payload = json.dumps({
                "school_id" : school_id_response[0][0],
                "school_token":get_school_token()
            },default=str)

            req_response = requests.request("POST", dereg_url, data=dereg_payload, verify=settings.CERT_FILE) 

            print('---req---response---',req_response.json())

            if req_response.json()['api_status'] == False:
                return Response(req_response.json())


            query = f"DROP TABLE {settings.DB_STUDENTS_SCHOOL_CHILD_COUNT};"

            mycursor.execute(query)

            cn.close()

            MiscInfo.objects.all().delete()
            scheduling.objects.all().delete()
            participants.objects.all().delete()
            event.objects.all().delete()

            return Response({'api_status':True,'messge':'De-Registeration successful'})
        
        except Exception as e:
            return Response({'api_status':False,'message':'Unable to De-Register','exception':str(e)})


class ListCleanerID(APIView):
    '''
    API class to list old event IDs which can be deleted -> For Events which are old and ExamMeta.sync_done = 1

    Conditions being checked
    `````````````````````````
    1. No ExamMeta object with sync_done = 0 => An Exam is actively running or Meta data is loaded for the upcoming exam
    2. Check if the event_id is older than the residual delete days (set from settings.RESIDUAL_DELETE_DAYS)

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
                    if sch_obj.event_enddate < (datetime.datetime.now()-datetime.timedelta(days=settings.RESIDUAL_DELETE_DAYS)).date():
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
            questions_folder = os.path.join(settings.MEDIA_ROOT,'questions_json')

            try:
                if os.path.exists(questions_folder):
                    for fname in os.listdir(questions_folder):
                        if fname.startswith(f"{event_id}_"):
                            os.remove(os.path.join(questions_folder, fname))
            except Exception as e:
                return Response({'api_status':False,'message':'Error in deleting files in questions_json folder'})

            # Delete the eventID's cons_data
            cons_data_folder = os.path.join(settings.MEDIA_ROOT,'cons_data',f'{event_id}')
            try:
                if os.path.exists(cons_data_folder):
                    shutil.rmtree(cons_data_folder,ignore_errors=False,onerror=None)
            except Exception as e:
                return Response({'api_status':False,'message':'Error in deleting files in cons_data folder'})

            metaObj.sync_done = 2
            metaObj.save()
            return Response({'api_status':True,'message':f"Clean-up completed for event_id : {event_id}"})

        except Exception as e:
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

            if ExamMeta.objects.filter(event_id=event_id).exists() == False:
                return Response({'api_status':False,'message':f'Meta data not available for the given event_id :{event_id}'})

            print('-----------------------')

            meta_obj = ExamMeta.objects.get(event_id=event_id)
            meta_obj.sync_done = 1
            meta_obj.save()

            return Response({'api_status':True,'message':'Exam marked as completed'})

        except Exception as e:
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

            return Response({'api_status':True,'data':{'reg_dt':misc_obj.reg_dt,'event_dt':misc_obj.event_dt}})

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