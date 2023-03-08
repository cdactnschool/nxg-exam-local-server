from django.urls import path

from . import localserver as ls
from .views import ( MetaUpload, db_auth, MyTokenObtainPairView, GetUserDetail,
                     InitialReg, LoadReg, LoadEvent, MetaData, SchoolDetails,
                     GetMyEvents, GenerateQuestionPaper, CandidateResponse,
                     UpdateRemtime, ExamSubmit, summary,SummaryAll, SchoolExamSummary,
                     ConsSummary, MetaUpload, ResetDB, MasterCleaner, 
                     ListCleanerID, ExamComplete, DispMisc, ToComplete, SendResponse,
                     SendResponses, VersionNumber,LogoutView, GenSendResponses,
                     AutoUpdateStatus, MetaAuto
                     )

                     
from .views_adv import GenerateJSON

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    path('regstatus',                       ls.ServerRegistrationStatus.as_view(),  name='server-reg-status'),


    # Authentication Block

    path('db_auth',                         db_auth.as_view(),                      name='db_auth'),
    path('token',                           MyTokenObtainPairView.as_view(),        name='token-obtain-pair'),
    path('token/refresh',                   TokenRefreshView.as_view(),             name='token_refresh'),
    path('token/verify',                    TokenVerifyView.as_view(),              name='token_verify'),
    path('logout',                          LogoutView.as_view(),                   name='logout'),
    path('get-user-detail',                 GetUserDetail.as_view(),                name='GetUserDetail'),

    path('auto-update-status',              AutoUpdateStatus.as_view(),             name='auto-update-status'),
    path('meta-auto',                       MetaAuto.as_view(),                     name='meta-auto'),

    # Initial Registeration Block

    path('initial-reg',                     InitialReg.as_view(),                   name='initial-reg'),
    path('load-reg',                        LoadReg.as_view(),                      name='event_list'), 
    path('load_events',                     LoadEvent.as_view(),                    name='event_list'), 
    path('meta_data',                       MetaData.as_view(),                     name='meta_data'),
    path('school-details',                  SchoolDetails.as_view(),                name='school-details'),
    path('version-number',                  VersionNumber.as_view(),                name='version-number'),

    # Exam Management Block

    path('get-my-events',                   GetMyEvents.as_view(),                  name='get-my-events'),
    path('qpdownload',                      GenerateQuestionPaper.as_view(),        name='qpdownload'),
    path('exam_response',                   CandidateResponse.as_view(),            name='exam_response'),
    path('update-remtime',                  UpdateRemtime.as_view(),                name='update-remtime'),
    path('exam-submit',                     ExamSubmit.as_view(),                   name='exam-submit'),
    path('summary',                         summary.as_view(),                      name='exam_summary'),
    path('event_summary',                   SummaryAll.as_view(),                   name='SummaryAll'),
    path('meta-upload',                     MetaUpload.as_view(),                   name='qpupload'),

    # Post Exam management Block
    
    path('school_exam_summary',             SchoolExamSummary.as_view(),            name='school_exam_summary'),
    path('cons-summary',                    ConsSummary.as_view(),                  name='cons-summary'),
    path('gen-json',                        GenerateJSON.as_view(),                 name='gen-json'),
    path('send-response',                   SendResponse.as_view(),                 name='send-response'),
    path('send-responses',                  SendResponses.as_view(),                 name='send-response'),

    path('gen-send-responses',              GenSendResponses.as_view(),             name='gen-send-responses'), 

    # Misc block

    # path('de-register',                     ResetDB.as_view(),                      name='reset-db'),
    path('event-cleaner',                   MasterCleaner.as_view(),                name='event-cleaner'),
    path('list-cleaner',                    ListCleanerID.as_view(),                name='list-cleaner'),
    path('to-complete',                     ToComplete.as_view(),                   name='to-complete'),
    path('exam-complete',                   ExamComplete.as_view(),                 name='exam-complete'),
    path('disp-misc',                       DispMisc.as_view(),                     name='disp-misc'),
    
    
    
    ]