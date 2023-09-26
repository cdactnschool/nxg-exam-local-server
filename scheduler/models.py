from django.db import models
from django.contrib.auth.models import User
import random

def generate_color():
    """
    This is a function to return a hex colour
    
    The hex colour code is generated by appending R G B random values in the range of 0 - 255 range
    """
    color = '#{:02x}{:02x}{:02x}'.format(*map(lambda x: random.randint(0, 255), range(3)))
     
    return color


class StatusChoices(models.TextChoices):
    CREATED     = 'CREATED',    'CREATED'
    PUBLISHED   = 'PUBLISHED',  'PUBLISHED'

class EventStatusChoices(models.TextChoices):
    INPROGRESS  = 'INPROGRESS', 'INPROGRESS'
    COMPLETED   = 'COMPLETED',  'COMPLETED'

class CategoryChoices(models.TextChoices):
    DISTRICT    = 'DISTRICT',   'DISTRICT'
    #EDUDISTRICT = 'EDU-DISTRICT','EDU-DISTRICT'
    ZONE        = 'BLOCK',      'BLOCK'
    SCHOOL      = 'SCHOOL',     'SCHOOL'
    STUDENT     = 'STUDENT',    'STUDENT'

class LocationChoices(models.TextChoices):
    ONLINE      = 'ONLINE',     'ONLINE'
    OFFLINE     = 'OFFLINE',    'OFFLINE'

class MediumChoices(models.TextChoices):
    ENGLISH     = 'ENGLISH',    'ENGLISH'
    TAMIL       = 'TAMIL',      'TAMIL'

class ApprovalChoices(models.TextChoices):
    WAIT        = 'WAIT',       'WAIT'
    APPROVED    = 'APPROVED',   'APPROVED'    
    NOTAPPROVED = 'NOTAPPROVED','NOTAPPROVED'

class subject_choices(models.TextChoices):
    ENGLISH             = 'ENGLISH',    'ENGLISH'
    TAMIL               = 'TAMIL',      'TAMIL'
    MATHS               = 'MATHS',      'MATHS'
    SCIENCE             = 'SCIENCE',    'SCIENCE'
    SOCIAL              = 'SOCIAL','    SOCIAL'
    COMPUTER            = 'COMPUTER',   'COMPUTER'


class event(models.Model):
    id                  = models.BigIntegerField(primary_key=True)
    event_type_id       = models.IntegerField(null=True,blank=True)
    event_type          = models.CharField(max_length=200)
    
    created_on          = models.DateTimeField(blank =False)

    def __str__(self):
        return "{0}-{1}".format(self.id,self.event_type)


class participants(models.Model):
    id                              = models.BigIntegerField(primary_key = True)
    # participant_pk                  = models.IntegerField(blank = True, null = True)
    schedule_id                     = models.BigIntegerField()
    participant_category            = models.CharField(max_length=20)
    participant_catid               = models.IntegerField(blank = True, null = True)
    participant_id                  = models.CharField(max_length=250)
    event_participation_status      = models.IntegerField()
    event_allocationid              = models.TextField(blank=True, null=True)
    allocated_by                    = models.CharField(max_length=250, blank=True, null=True)
    section                         = models.CharField(max_length=250, blank=True, null=True)
    allocation_status               = models.IntegerField(default = 0, blank = True, null = True)
    generation_status               = models.IntegerField(blank = True, null = True)
    flag1                           = models.IntegerField(blank = True, null = True)
    flag2                           = models.CharField(max_length=250, blank=True, null=True)
    allocator_id                   = models.CharField(max_length=250,blank = True, null = True)

    created_on                      = models.DateTimeField(auto_now=True ,blank =False)

    def __str__(self):
        return "{0}-{1}-{2}-{3}".format(self.id,self.schedule_id,self.participant_category,self.participant_id)


class scheduling(models.Model):
    schedule_id             = models.BigIntegerField(primary_key=True)
    event_title             = models.CharField(max_length=200)
    class_std               = models.IntegerField(blank = True, null = True) #models.CharField(max_length=200)
    class_section           = models.CharField(max_length=10,blank=True, null=True)
    class_group             = models.CharField(max_length=1000,blank=True, null=True)
    class_subject           = models.CharField(max_length=200)
    class_medium            = models.CharField(max_length=20, blank=True, null=True)#,choices=MediumChoices.choices,default=MediumChoices.ENGLISH)
    event_startdate         = models.DateField(blank=True, null=True)
    event_enddate           = models.DateField(blank=True, null=True)
    event_updatedatetime    = models.DateTimeField(auto_now=True)
    event_author_id         = models.CharField(max_length=20, blank=True, null=True)
    event_location          = models.CharField(max_length=20,choices=LocationChoices.choices,default=LocationChoices.ONLINE)
    event_location_id       = models.IntegerField(blank = True, null = True)
    event_tags              = models.CharField(max_length=200, blank=True, null=True)
    event_type_id           = models.CharField(max_length=20,blank=True, null=True)
    event_approval_status   = models.CharField(max_length=50,choices=ApprovalChoices.choices,default=ApprovalChoices.WAIT)
    event_approval_status_id= models.IntegerField(blank = True, null = True)
    event_approved_by       = models.CharField(max_length=200,blank=True,null=True)
    event_approved_date     = models.DateTimeField(blank=True,null=True)
    event_remark            = models.CharField(max_length=250,blank=True, null=True)
    
    event_deleted_by        = models.CharField(max_length=250, blank=True, null=True)
    event_deleted_on        = models.DateTimeField(blank=True,null=True)
    event_deletion_reason   = models.CharField(max_length=250,blank=True, null=True)
    
    no_of_days              = models.IntegerField(blank=True,null=True)
    event_is_allday         = models.BooleanField(default = False)
    event_starttime         = models.TimeField(blank=True, null=True)
    event_endtime           = models.TimeField(blank=True, null=True)
    batch_count             = models.IntegerField(default=1)
    event_colour            = models.CharField(max_length=200, blank=True, null=True, default=generate_color)
    event_completion_status = models.CharField(max_length=20,choices=EventStatusChoices.choices,default=EventStatusChoices.INPROGRESS)
    event_completion_id     = models.IntegerField(blank = True, null = True)
    event_allocationid      = models.IntegerField(blank = True, null = True) #CharField(max_length=250, blank=True, null=True)
    school_type             = models.CharField(max_length=250, blank=True, null=True)
    school_category         = models.CharField(max_length=250, blank=True, null=True)
    is_1_n                  = models.IntegerField(default = 0)
    flag1                   = models.IntegerField(blank = True, null = True)
    flag2                   = models.CharField(max_length=250, blank=True, null=True)
    allowed_allocation_id   = models.IntegerField(blank = True, null = True)
    exam_category           = models.IntegerField(blank = True, null = True)
    priority                = models.IntegerField(blank = True, null = True)
    
    created_on              = models.DateTimeField(blank =False)
    
    def __str__(self):
        return "{0}-{1}-{2}-{3}".format(self.schedule_id,self.event_title,self.class_std,self.class_subject)