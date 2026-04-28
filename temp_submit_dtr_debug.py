import traceback
from django.test import RequestFactory
from django.contrib.auth.models import User
from SEIKI import views

user = User.objects.filter(is_superuser=False).first()
print('USER', user)
request = RequestFactory().get('/student-submit-dtr/')
request.user = user
try:
    response = views.student_submit_dtr(request)
    print(type(response), getattr(response, 'status_code', None))
except Exception:
    traceback.print_exc()
