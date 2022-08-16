from django.urls import path

from . import views, localserver as ls

from . import views_adv

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    path('regstatus',                       ls.ServerRegistrationStatus.as_view(),      name='server-reg-status'),
    
    path('db_auth',                         views.db_auth.as_view(),                    name='db_auth'),
    path('token',                           views.MyTokenObtainPairView.as_view(),      name='token-obtain-pair'),
    path('token/refresh',                   TokenRefreshView.as_view(),                 name='token_refresh'),
    path('token/verify',                    TokenVerifyView.as_view(),                  name='token_verify'),
    path('get-user-detail',                 views.GetUserDetail.as_view(),              name='GetUserDetail'),

    path('initial-reg',                     views.InitialReg.as_view(),                 name='initial-reg'),
    path('load-reg',                        views.LoadReg.as_view(),                    name='event_list'), 
    path('load_events',                     views.LoadEvent.as_view(),                  name='event_list'), 
    path('meta_data',                       views.MetaData.as_view(),                   name='meta_data'), # Changes
    path('school-details',                  views.SchoolDetails.as_view(),              name='school-details'),

    path('get-my-events',                   views.get_my_events.as_view(),              name='get-my-events'),
    path('qpdownload',                      views.GenerateQuestionPaper.as_view(),      name='qpdownload'), # Changes
    path('exam_response',                   views.exam_response.as_view(),              name='exam_response'),
    path('update-remtime',                  views.update_remtime.as_view(),             name='update-remtime'),
    path('exam-submit',                     views.exam_submit.as_view(),                name='exam-submit'),
    path('summary',                         views.summary.as_view(),                    name='exam_summary'),
    path('event_summary',                   views.SummaryAll.as_view(),                 name='SummaryAll'),
    
    path('school_exam_summary',             views.school_exam_summary.as_view(),        name='school_exam_summary'),

    path('cons-summary',                    views.ConsSummary.as_view(),                name='cons-summary'),
    path('gen-json',                        views_adv.GenerateSentJSON.as_view(),       name='gen-json'),

    ]