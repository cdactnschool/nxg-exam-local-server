from rest_framework import serializers
from . import models
from scheduler import models as models_scheduler

import datetime


def fetch_attendance_object(user_detail,event_id):

    '''
    Function to fetch event_attendance object for given user and event_id


    Returns the first entry from the filter if available 
    Else return None

    '''

    #print('======',user_detail.profile.name_text,event_id)
    attendance_obj_query = models.event_attendance.objects.filter(event_id=event_id,student_id=user_detail.id)
    if len(attendance_obj_query) == 0:
        print('<---No attendance Entry found--->')
        return None
    else:
        print('<---Attendance Entry found--->')
        return attendance_obj_query[0]

class exam_events_schedule_serializer(serializers.ModelSerializer):
    
    '''

    Seralizer class to serialize the events_schedules

    Addiditonal field
    `````````````````

    exam_status -> For Student login - Display the status of the event schedule; For Teacher login return None
    
    '''


    exam_status             = serializers.SerializerMethodField('get_exam_status')
    event_status            = serializers.SerializerMethodField('get_event_status')
    event_completion_status = serializers.SerializerMethodField('get_event_completion_status')
    exam_scores             = serializers.SerializerMethodField('get_exam_scores')

    def create(self, validated_data):
        return models_scheduler.scheduling.objects.create(**validated_data)

    class Meta:
        model = models_scheduler.scheduling
        fields = '__all__'
    
    def get_exam_status(self,obj):

        '''
        Return if Exam is started/not completed/Completed

        0 -> Exam not started
        1 -> Exam not completed
        2 -> Exam completed


        '''

        user_detail = self.context.get("user")
        
        # For teacher / HM
        
        if user_detail.profile.usertype in ['teacher','hm']:
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
            return 1
        elif obj.event_startdate > datetime.datetime.now().date():
            return 2
        elif obj.event_enddate < datetime.datetime.now().date():
            return 3
        
        return None
    

    def get_event_completion_status(self,obj):
        '''
        
        Return the count of candidates who have completed the exams for teacher / HM

        '''
        user_detail = self.context.get("user")

        if user_detail.profile.usertype == 'student':
            return None

        attendance_list = models.event_attendance.objects.filter(event_id=obj.schedule_id).exclude(end_time=None)

        return len(attendance_list)

    
    def get_exam_scores(self,obj):
        '''
        Return the score of the candidate for student

        Return marks from the attendance_object
        Return '-' if Exam is not submitted
        Return 'A' if not attempted

        '''

        user_detail = self.context.get("user")

        if user_detail.profile.usertype in ['teacher','hm']:
            return None
        

        attendance_obj = fetch_attendance_object(self.context.get('user'),obj.schedule_id)

        if attendance_obj == None: # return zero if there are not 
            return 'A'
        
        if attendance_obj.end_time == None:
            return '-'

        return attendance_obj.total_marks

class exam_event_serializer(serializers.ModelSerializer):
    def create(self, validated_data):
        return models_scheduler.event.objects.create(**validated_data)

    username = serializers.SerializerMethodField('getusername')

    class Meta:
        model = models_scheduler.event
        fields = '__all__'

    def getusername(self,obj):
        return obj.user.username

class exam_participants_serializer(serializers.ModelSerializer):
    def create(self, validated_data):
        return models_scheduler.participants.objects.create(**validated_data)

    username = serializers.SerializerMethodField('getusername')

    class Meta:
        model = models_scheduler.participants
        fields = '__all__'

    def getusername(self,obj):
        return obj.user.username

class exam_scheduling_serializer(serializers.ModelSerializer):

    def create(self, validated_data):
        return models_scheduler.scheduling.objects.create(**validated_data)

    class Meta:
        model = models_scheduler.scheduling
        fields = '__all__'

class exam_meta_data_serializer(serializers.ModelSerializer):
    def create(self, validated_data):
        return models.exam_meta_data.objects.create(**validated_data)

    username = serializers.SerializerMethodField('getusername')

    class Meta:
        model = models.exam_meta_data
        fields = '__all__'

class question_meta_serializer(serializers.ModelSerializer):
    def create(self, validated_data):
        return models.question_meta_data.objects.create(**validated_data)
    
    username = serializers.SerializerMethodField('getusername')

    class Meta:
        model = models.question_meta_data
        fields = '__all__'

    def getusername(self,obj):
        return obj.user.username

class question_table_serializer(serializers.ModelSerializer):
    def create(self, validated_data):
        return models.question_table.objects.create(**validated_data)
    
    username = serializers.SerializerMethodField('getusername')

    class Meta:
        model = models.question_table
        fields = '__all__'


    def getusername(self,obj):
        return obj.user.username

class choice_table_serializer(serializers.ModelSerializer):
    def create(self, validated_data):
        return models.choice_table.objects.create(**validated_data)
    
    username = serializers.SerializerMethodField('getusername')

    class Meta:
        model = models.choice_table
        fields = '__all__'

    def getusername(self,obj):
        return obj.user.username

class question_paper_table_serializer(serializers.ModelSerializer):

    def create(self, validated_data):
        return models.question_paper_table.objects.create(**validated_data)

    username = serializers.SerializerMethodField('getusername')

    class Meta:
        model = models.question_paper_table
        fields = '__all__'


    def getusername(self,obj):
        return obj.user.username


