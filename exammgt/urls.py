from django.urls import path

from . import localserver as ls
from .views import db_auth, MyTokenObtainPairView, GetUserDetail, InitialReg, LoadReg, LoadEvent, MetaData, SchoolDetails, GetMyEvents, GenerateQuestionPaper, ExamResponse, UpdateRemtime, ExamSubmit, summary,SummaryAll, SchoolExamSummary, ConsSummary
from .views_adv import GenerateJSON

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    path('regstatus',                       ls.ServerRegistrationStatus.as_view(),  name='server-reg-status'),
    
    path('db_auth',                         db_auth.as_view(),                      name='db_auth'),
    path('token',                           MyTokenObtainPairView.as_view(),        name='token-obtain-pair'),
    path('token/refresh',                   TokenRefreshView.as_view(),             name='token_refresh'),
    path('token/verify',                    TokenVerifyView.as_view(),              name='token_verify'),
    path('get-user-detail',                 GetUserDetail.as_view(),                name='GetUserDetail'),

    path('initial-reg',                     InitialReg.as_view(),                   name='initial-reg'),
    path('load-reg',                        LoadReg.as_view(),                      name='event_list'), 
    path('load_events',                     LoadEvent.as_view(),                    name='event_list'), 
    path('meta_data',                       MetaData.as_view(),                     name='meta_data'),
    path('school-details',                  SchoolDetails.as_view(),                name='school-details'),

    path('get-my-events',                   GetMyEvents.as_view(),                  name='get-my-events'),
    path('qpdownload',                      GenerateQuestionPaper.as_view(),        name='qpdownload'),
    path('exam_response',                   ExamResponse.as_view(),                 name='exam_response'),
    path('update-remtime',                  UpdateRemtime.as_view(),                name='update-remtime'),
    path('exam-submit',                     ExamSubmit.as_view(),                   name='exam-submit'),
    path('summary',                         summary.as_view(),                      name='exam_summary'),
    path('event_summary',                   SummaryAll.as_view(),                   name='SummaryAll'),
    
    path('school_exam_summary',             SchoolExamSummary.as_view(),            name='school_exam_summary'),
    path('cons-summary',                    ConsSummary.as_view(),                  name='cons-summary'),
    path('gen-json',                        GenerateJSON.as_view(),                 name='gen-json'),

    ]