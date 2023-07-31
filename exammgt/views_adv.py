from .models import EventAttendance, ExamResponse

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser

from tnschoollocalserver.tn_variables import AUTH_ENABLE, MEDIA_ROOT

import os
import json
import datetime

import logging
infolog     = logging.getLogger('infolog')
errorlog    = logging.getLogger('errorlog')


class GenerateJSON(APIView):

    '''
    Generate the JSON file


    Input parameters
    ````````````````

    id : event/schedule_id
    

    # Note: Remove json_created=False to generate JSON file irrespective of JSON created or note
    
    '''

    if AUTH_ENABLE:
        permission_classes = (IsAuthenticated,) # Allow only if authenticated

    def post(self,request,*args, **kwargs):

        try:
        
            if request.user.profile.usertype not in ['hm','superadmin_user','school']:
                return Response ({'api_status':False,'message':'Only HM is authorized for JSON generation'})
            
            data = JSONParser().parse(request)
            data['event_id'] = data ['id']

            # Fetch events where json_created is False and end_time is none
            event_attendances = EventAttendance.objects.filter(event_id = data['event_id'],json_created=False).exclude(end_time=None)

            if len(event_attendances) == 0:
                return Response ({'api_status':False,'icon':'info','message':'Atleast one new candidate has to completed the exam'})
            
            # folder_dir = os.path.join(MEDIA_ROOT,'cons_data',f"{data['event_id']}")
            folder_dir = os.path.join(MEDIA_ROOT,'cons_data')
            os.makedirs(folder_dir, exist_ok=True)

            print('folder_dir _+_+_+_+_+__+',folder_dir)
            '''
            file_name = os.path.join(folder_dir, f"{data['event_id']}_{request.user.profile.school_id}.json")


            # Create a JSON file if already exist
            if not os.path.exists(file_name) or os.stat(file_name).st_size == 0:
                consolidated_data = {}
                consolidated_data = {
                    'event_id':data['event_id'],
                    'school_id':request.user.profile.school_id,
                    'details':[]
                }
                with open(file_name, 'w') as outfile:  
                    json.dump(consolidated_data, outfile)

            with open(file_name,'r') as input_file:
                consolidated_data = json.load(input_file)
            '''

            file_name = os.path.join(folder_dir,f"{data['event_id']}_{request.user.profile.school_id}_{request.user.profile.udise_code}_{str(datetime.datetime.now().strftime('%d-%m-%Y_%H-%M-%S'))}.json")

            consolidated_data = {
                    'event_id':data['event_id'],
                    'school_id':request.user.profile.school_id,
                    'udise_code':request.user.profile.udise_code,
                    'details':[]
                }

            #Loop through each attendnace entry
            details_object = []
            for event_attendance_obj in event_attendances:
                print(event_attendance_obj)
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

                obj = ExamResponse.objects.filter(event_id = data['event_id'],student_username = event_attendance_obj.student_username,qp_set_id = event_attendance_obj.qp_set)
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


                #consolidated_data.details.append(details_dict)
                details_object.append(details_dict)
            print('*********',details_object)
            consolidated_data['details'] = details_object

            with open(file_name, 'w') as outfile:  
                json.dump(consolidated_data, outfile)

            print('Consolidate data',consolidated_data)


            # Mark Json created attenedance
            for event_attendance_obj in event_attendances:
                event_attendance_obj.json_created = True
                event_attendance_obj.save()

            infolog.info(json.dumps({'school_id':request.user.profile.school_id,'username':request.user.username,'action':'Generate_JSON','event_id':data['event_id'],'datetime':str(datetime.datetime.now())},default=str))


            return Response({'api_status':True,'message':f"JSON file generated successfully for {len(details_object)} students"})

        except Exception as e:

            errorlog.error(json.dumps({'school_id':request.user.profile.school_id,'username':request.user.username,'action':'Generate_JSON','event_id':data['event_id'],'datetime':str(datetime.datetime.now()),'exception':str(e)},default=str))
            

            return Response({'api_status':False,'message':'Error in generating JSON file','exception':str(e)})

