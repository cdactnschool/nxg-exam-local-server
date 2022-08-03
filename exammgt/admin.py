from django.contrib import admin
from .import models

# Register your models here.

admin.site.register(models.Profile)
admin.site.register(models.question_meta_data)
admin.site.register(models.question_table)
admin.site.register(models.choice_table)
admin.site.register(models.exam_meta_data)
admin.site.register(models.question_paper_table)
admin.site.register(models.exam_response)