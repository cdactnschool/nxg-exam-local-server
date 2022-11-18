from rest_framework import serializers
from .models import EventAttendance, ExamMeta, QpSet, Question, Choice
from scheduler.models import scheduling, event, participants
from . import views
import math

from tnschoollocalserver.tn_variables import AUTH_FIELDS, MEDIUM


import datetime
#from .views import connection
#from sqlalchemy import create_engine

def fetch_attendance_object(user_detail,event_id):

    '''
    Function to fetch EventAttendance object for given username and event_id


    Returns the first entry from the filter if available 
    Else return None

    '''

    #print('======',user_detail.profile.name_text,event_id)
    attendance_obj_query = EventAttendance.objects.filter(event_id=event_id,student_username=user_detail.username)
    if len(attendance_obj_query) == 0:
        print('<---No attendance Entry found--->')
        return None
    else:
        print('<---Attendance Entry found--->')
        return attendance_obj_query[0]

class ExamEventsScheduleSerializer(serializers.ModelSerializer):
    
    '''

    Seralizer class to serialize the events_schedules

    Addiditonal field
    `````````````````

    exam_status -> For Student login - Display the status of the event schedule; For Teacher login return None
    
    '''

    
    exam_status             = serializers.SerializerMethodField('get_exam_status')
    event_status            = serializers.SerializerMethodField('get_event_status')
    event_completion_status = serializers.SerializerMethodField('get_event_completion_status')
    exam_correct             = serializers.SerializerMethodField('get_exam_correct')
    meta_status             = serializers.SerializerMethodField('get_meta_status')
    total_candidates        = serializers.SerializerMethodField('get_total_candidates')
    duration_mins           = serializers.SerializerMethodField('get_duration_minutes')
    json_count              = serializers.SerializerMethodField('get_json_count')
    user_type               = serializers.SerializerMethodField('get_user_type')
    json_available          = serializers.SerializerMethodField('get_json_available')
    lang_desc               = serializers.SerializerMethodField('get_lang_desc')

    def create(self, validated_data):
        return scheduling.objects.create(**validated_data)

    class Meta:
        model = scheduling
        fields = '__all__'
    
    def get_exam_status(self,obj):

        '''
        Return if Exam is started/not completed/Completed

        0 -> Exam not Started
        1 -> Exam not Completed
        2 -> Exam Completed

        '''

        user_detail = self.context.get("user")
        
        # For teacher / HM
        
        if user_detail.profile.usertype in ['teacher','hm','superadmin_user']:
            return None
        
        #return str(user_detail.profile.name_text)+str(obj.event_completion_status)
        #print('<------->',obj.event_startdate)
        #print('<------->',obj.schedule_id)
        attendance_obj = fetch_attendance_object(self.context.get('user'),obj.schedule_id)

        
        if attendance_obj == None:
            return 0
        
        if attendance_obj.end_time == None:
            return 1
        
        if attendance_obj.end_time != None:
            return 2

        return None

    def get_event_status(self,obj):
        '''
        Return if Event is live/old/upcoming

        0 -> Live
        1 -> Upcoming
        2 -> Old

        '''

        if obj.event_startdate <= datetime.datetime.now().date() <= obj.event_enddate:
            return 0
        elif obj.event_startdate > datetime.datetime.now().date():
            return 1
        elif obj.event_enddate < datetime.datetime.now().date():
            return 2
        
        return None
    

    def get_event_completion_status(self,obj):
        '''
        
        Return the count of candidates who have completed the exams for teacher / HM

        '''
        user_detail = self.context.get("user")

        if user_detail.profile.usertype == 'student':
            return None

        attendance_list = EventAttendance.objects.filter(event_id=obj.schedule_id).exclude(end_time=None)

        return len(attendance_list)

    
    def get_exam_correct(self,obj):
        '''
        Return the total number of correct answers of the candidate

        Return marks from the attendance_object
        Return '-' if Exam is not submitted
        Return 'A' if not attempted

        '''

        user_detail = self.context.get("user")

        if user_detail.profile.usertype in ['teacher','hm','superadmin_user']:
            return None
        

        meta_status_query = ExamMeta.objects.filter(event_id = obj.schedule_id)
        if len(meta_status_query):
            meta_status_object = meta_status_query[0]
        else:
            return '-'


        attendance_obj = fetch_attendance_object(self.context.get('user'),obj.schedule_id)

        if attendance_obj == None: # return zero if there are not 
            return f"A/{meta_status_object.no_of_questions}"
        
        if attendance_obj.end_time == None:
            return f"-/{meta_status_object.no_of_questions}"

        return f"{attendance_obj.correct_answers}/{meta_status_object.no_of_questions}"
    
    def get_meta_status(self,obj):
        '''
        Check if meta data is set for the event

        0 -> Meta data not set
        1 -> Meta data set

        '''
        meta_status_query = ExamMeta.objects.filter(event_id = obj.schedule_id)

        if len(meta_status_query) == 0:
            return 0
        else:
            return 1
    
    def get_total_candidates(self,obj):
        '''
        Fetch the total number of candidates
        '''
        user_detail = self.context.get("user")

        if user_detail.profile.usertype == 'student':
            return None
        try:
            cn = views.connection()
            mycursor = cn.cursor()

            query = f" SELECT COUNT(l.{AUTH_FIELDS['student']['username_field']}) FROM {AUTH_FIELDS['student']['auth_table']} l LEFT JOIN {AUTH_FIELDS['student']['master_table']} r ON l.{AUTH_FIELDS['student']['school_field_foreign']} = r.{AUTH_FIELDS['student']['school_field_foreign_ref']} WHERE r.{AUTH_FIELDS['student']['student_class']} = {obj.class_std}"
            if obj.class_section != None:
                query = f"{query} AND r.{AUTH_FIELDS['student']['section_field_master']} = '{obj.class_section}'"
            
            if obj.class_group != None:
                query = f"{query} AND r.group_code_id = {obj.class_group.split('-')[0]}"


            # query = f"SELECT COUNT(*) FROM emisuser_student WHERE class_studying_id = {obj.class_std}"
            # if obj.class_section != None:
            #     obj = f"{obj} AND class_section = '{obj.class_section}' ;"
            # else:
            #     obj = f"{obj} ;"
            mycursor.execute(query)
            student_count_result = mycursor.fetchall()
            return student_count_result[0][0]
            
        except Exception as e:
            print('Exception occured in getting total candidates count :',e)
            return None

    def get_duration_minutes(self,obj):
        '''
        Fetch the exam duration from the ExamMeta table
        '''
        user_detail = self.context.get("user")
        
        if user_detail.profile.usertype != 'student':
            return 'NA'

        try:
            attendance_obj = fetch_attendance_object(self.context.get('user'),obj.schedule_id)

            if attendance_obj:
                return math.ceil(attendance_obj.remaining_time/60) # Return remaining time in Minutes

            meta_duration_query = ExamMeta.objects.filter(event_id = obj.schedule_id)

            if len(meta_duration_query) == 0:
                return '-'
            else:
                meta_duration_entry = meta_duration_query[0]
                # print('`````````````')
                # print(meta_duration_query.__dict__)
                # print('duration_mins' in meta_duration_query)
                
                return meta_duration_entry.duration_mins # Return remaining time in Minutes
        except Exception as e:
            print('Exception in getting remaining time ',e)
            return 'NA'

    def get_json_count(self,obj):
        '''
        Return the count of attendance model where json is created
        '''
        if self.context.get('user').profile.usertype == 'hm':
            return EventAttendance.objects.filter(event_id=obj.schedule_id,json_created=True).count()
        else:
            return None
    
    def get_json_available(self,obj):
        '''
        Return the count of attendance model where json can be created
        '''
        if self.context.get('user').profile.usertype == 'hm':
            return EventAttendance.objects.filter(event_id=obj.schedule_id,json_created=False).count()
        else:
            return None


    def get_user_type(self,obj):
        return self.context.get('user').profile.usertype
    
    def get_lang_desc(self,obj):
        '''
        Return description of language
        '''
        try:
            # print(f'{obj.schedule_id} class_medium {MEDIUM[obj.class_medium]}')
            return MEDIUM[obj.class_medium]
        except:
            return None


class ExamEventSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        return event.objects.create(**validated_data)

    username = serializers.SerializerMethodField('getusername')

    class Meta:
        model = event
        fields = '__all__'

    def getusername(self,obj):
        return obj.user.username

class ExamParticipantsSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        return participants.objects.create(**validated_data)

    username = serializers.SerializerMethodField('getusername')

    class Meta:
        model = participants
        fields = '__all__'

    def getusername(self,obj):
        return obj.user.username

class ExamSchedulingSerializer(serializers.ModelSerializer):

    def create(self, validated_data):
        return scheduling.objects.create(**validated_data)

    class Meta:
        model = scheduling
        fields = '__all__'


class ExamMetaSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        return ExamMeta.objects.create(**validated_data)

    username = serializers.SerializerMethodField('getusername')

    class Meta:
        model = ExamMeta
        fields = '__all__'

class QpSetsSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        return QpSet.objects.create(**validated_data)
    
    username = serializers.SerializerMethodField('getusername')

    class Meta:
        model = QpSet
        fields = '__all__'


    def getusername(self,obj):
        return obj.user.username

class QuestionsSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        print('question data :',validated_data.get('qid'))
        question_object,created = Question.objects.get_or_create(**validated_data)
        print('question data created ',created)
        return  question_object
    
    username = serializers.SerializerMethodField('getusername')

    class Meta:
        model = Question
        fields = '__all__'


    def getusername(self,obj):
        return obj.user.username


class ChoicesSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        # return Choice.objects.create(**validated_data)

        print('choices data :',validated_data)

        choice_object,created =  Choice.objects.get_or_create(**validated_data)
        print('Choice data created ',created)
        
        return choice_object
    
    username = serializers.SerializerMethodField('getusername')

    class Meta:
        model = Choice
        fields = '__all__'

    def getusername(self,obj):
        return obj.user.username