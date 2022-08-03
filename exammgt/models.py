import random
from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):

    '''
    Class to add extra fields to the User model

    Parameters:
    ``````````

    user        - Foreign key to the django's buildin user model
    usertype    - Type of the user
    udise_code  - unique code for the school
    district_id - unique id for the district
    block_id    - unique id for the block
    prioriy     - priority of the user
    
    '''

    user        = models.OneToOneField(User, on_delete=models.CASCADE)
    name_text   = models.CharField(max_length=30,null=True,blank=True)
    student_class = models.IntegerField(null=True,blank=True)
    usertype    = models.CharField(max_length=30,null=True,blank=True)
    udise_code  = models.CharField(max_length=30,null=True,blank=True)
    district_id = models.CharField(max_length=30,null=True,blank=True)
    block_id    = models.CharField(max_length=30,null=True,blank=True)
    school_id   = models.CharField(max_length=30,null=True,blank=True)
    priority    = models.IntegerField(default=20)


    def __str__(self):
        return "{0}-{1}".format(self.user.username, self.usertype)

class ExamMeta(models.Model):
    event_id                            = models.BigIntegerField(primary_key=True)
    subject                             = models.CharField(max_length=1024)
    no_of_questions                     = models.IntegerField()
    duraion_mins                        = models.IntegerField()
    qtype                               = models.CharField(max_length=1024)
    total_marks                         = models.IntegerField()
    qshuffle                            = models.BooleanField(default=False)
    show_submit_at_last_question        = models.BooleanField(default=False)
    show_summary                        = models.BooleanField(default=False)
    show_result                         = models.BooleanField(default=False)
    end_alert_time                      = models.IntegerField()
    show_instruction                    = models.BooleanField(default=False)
    qp_set_list                         = models.TextField()
    created_on                          = models.DateTimeField(auto_now = True)

    def __str__(self):
        return "{0}-{1}-{2}-{3}".format(self.duraion_mins, self.event_id, self.subject, self.created_on)

class QpSet(models.Model):
    event_id                            = models.BigIntegerField()
    qp_set_id                           = models.IntegerField(primary_key=True)
    qid_list                            = models.TextField()
    created_on                          = models.DateTimeField(auto_now = True)


    def __str__(self):
        return "{0}-{1}-{2}".format(self.event_id, self.qp_set_id, self.created_on)


class Question(models.Model):
    qid                                 = models.BigIntegerField(primary_key=True)
    qimage                              = models.TextField()
    no_of_choices                       = models.IntegerField()
    correct_choice                      = models.IntegerField()
    created_on                          = models.DateTimeField(auto_now = True)

    def __str__(self):
        return "{0}-{1}-{2}".format(self.qid, self.no_of_choices, self.created_on)


class Choice(models.Model):
    qid                           = models.BigIntegerField()
    cid                           = models.IntegerField(primary_key=True)
    cimage                        = models.TextField()
    created_on                    = models.DateTimeField(auto_now = True)

    def __str__(self):
        return "{0}-{1}-{2}".format(self.qid, self.cid, self.created_on)


class exam_response(models.Model):
    event_id                            = models.BigIntegerField()
    user                                = models.ForeignKey(User,on_delete=models.SET_NULL,null=True)
    #student_id                          = models.BigIntegerField()
    qp_set_id                           = models.IntegerField()
    question_id                         = models.IntegerField()
    selected_choice_id                  = models.IntegerField(null=True, blank=True)
    question_result                     = models.IntegerField(null=True,  blank=True)
    mark                                = models.CharField(max_length=1024,blank=True,null=True)
    review                              = models.BooleanField(default=False)
    created_on                          = models.DateTimeField(auto_now = True)

    def __str__(self):
        return "{0}-{1}-{2}".format(self.id,self.event_id,self.created_on)

class event_attendance(models.Model):
    event_id        = models.BigIntegerField()
    student_id      = models.ForeignKey(User,on_delete=models.SET_NULL,null=True)
    student_username= models.CharField(max_length=30,null=True,blank=True)
    qp_set          = models.CharField(max_length=30,null=True,blank=True)
    start_time      = models.DateTimeField(null=True,blank=True)
    end_time        = models.DateTimeField(null=True,blank=True)
    remaining_time  = models.IntegerField(null=True,blank=True)
    total_marks     = models.FloatField(null=True,default=0)
    json_created    = models.BooleanField(default=False)
    sync_done       = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.event_id}-{self.student_username}-{self.qp_set}-{self.json_created}-{self.sync_done}"