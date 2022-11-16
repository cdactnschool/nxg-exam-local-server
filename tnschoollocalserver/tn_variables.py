from django.conf import settings
import os

DATABASES = settings.DATABASES

MEDIA_ROOT = settings.MEDIA_ROOT

BASE_DIR = settings.BASE_DIR


# Enable authentication for the api calls
AUTH_ENABLE = True # Enable is_authentication in views.py file

CENTRAL_SERVER_IP = 'https://exams1.tnschools.gov.in'
# CENTRAL_SERVER_IP = 'http://10.184.36.118:8000'
# CENTRAL_SERVER_IP = 'https://10.184.36.231/'
# CENTRAL_SERVER_IP = 'http://10.184.36.237:8000'

# CERT_FILE = os.path.join(BASE_DIR, 'cert/schoolexam-RootCA.cert.pem')
CERT_FILE = False

SUPER_USERNAME = 'admin'
SUPER_PASSWORD = 'cdac@Root1234#$'

# Remote DB names:
DB_BASEAPP_GROUP_CODE           = 'baseapp_group_code'
DB_EMIS_USERLOGIN               = 'emis_userlogin'
DB_EMISUSER_STUDENT             = 'emisuser_student'
DB_EMISUSER_TEACHER             = 'emisuser_teacher'
DB_SCHOOLNEW_BLOCK              = 'schoolnew_block'
DB_SCHOOLNEW_DISTRICT           = 'schoolnew_district'
DB_STUDENTS_CHILD_DETAIL        = 'students_child_detail'
DB_STUDENTS_SCHOOL_CHILD_COUNT  = 'students_school_child_count'
DB_UDISE_STAFFREG               = 'udise_staffreg'
DB_USER_CATEGORY                = 'user_category'
DB_USER_SELECTED_ANSWERS        = 'user_selected_answers'

AUTH_FIELDS = {
    'teacher_hm':{
        'username_len': 8,
        'teacher_priority':18,
        'hm_priority':16,
        'username_field':'emis_username',
        'password_field':'ref',
        'hash_field': 'emis_password',
        'auth_table': DB_EMISUSER_TEACHER,
        'master_table': DB_UDISE_STAFFREG,
        'type_checker_foreign_key':'teacher_id',
        'type_checker_field':'teacher_type',
        'type_checker_value':[26,27,28,29],
        'school_key_ref_master' : 'school_key_id',
        'name_field_master':'teacher_name',
        #'auth_'
    },
    'department':{
        'department_priority':14,
        'username_field':'emis_username',
        'password_field':'ref',
        'hash_field': 'emis_password',
        'auth_table':DB_EMIS_USERLOGIN,
    },
    'student':{
        'username_len':16,
        'student_priority':20,
        'username_field':'emis_username',
        'password_field':'ref',
        'hash_field': 'emis_password',
        'auth_table': DB_EMISUSER_STUDENT,
        'type_field': 'emis_usertype',
        'school_field_foreign' :'emis_user_id',
        'master_table': DB_STUDENTS_CHILD_DETAIL,
        'school_field_foreign_ref' : 'id',
        'school_key_ref_master':'school_id',
        'name_field_master':'name',
        'section_field_master':'class_section',
        'student_class': 'class_studying_id',
    },
    'school':{
        'auth_table':DB_STUDENTS_SCHOOL_CHILD_COUNT,
        'school_id':'school_id',
        'district_id': 'district_id',
        'block_id':'block_id',
        'udise_code':'udise_code',
    },
    'superadmin_user':{
        'superadmin_user_priority':1
    }
}

# Days for cleaning
RESIDUAL_DELETE_DAYS = 10


# Language Medium
MEDIUM = {
    19:"English",
    18:"Urdu",
    17:"Telugu",
    16:"Tamil",
    8:"Malayalam",
    5:"Kannada"
}