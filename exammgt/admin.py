from django.contrib import admin
from .import models

# Register your models here.

admin.site.register(models.Profile)
admin.site.register(models.Question)
admin.site.register(models.Choice)
admin.site.register(models.QpSet)
admin.site.register(models.ExamMeta)
admin.site.register(models.event_attendance)
admin.site.register(models.exam_response)