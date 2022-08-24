from django.contrib import admin
from .models import Profile, Question, Choice, QpSet, ExamMeta, EventAttendance, ExamResponse

# Register your models here.

admin.site.register(Profile)
admin.site.register(Question)
admin.site.register(Choice)
admin.site.register(QpSet)
admin.site.register(ExamMeta)
admin.site.register(EventAttendance)
admin.site.register(ExamResponse)