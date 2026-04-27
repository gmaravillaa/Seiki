"""
URL configuration for SEIKI project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView, LoginView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [

    # =======================
    # ADMIN
    # =======================
    path('admin/', admin.site.urls),

    # =======================
    # AUTH
    # =======================
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', views.custom_logout, name='logout'),

    # =======================
    # ROOT
    # =======================
    path('', views.index, name='index'),
    path('dashboard-redirect/', views.dashboard_redirect, name='dashboard_redirect'),

    # =======================
    # DASHBOARDS
    # =======================
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('office-dashboard/', views.office_dashboard, name='office_dashboard'),
    path('student-dashboard/', views.student_dashboard, name='student_dashboard'),

    # =======================
    # MODULE PAGES
    # =======================
    path('student-assistants/', views.student_assistant_progress, name='student_assistants_progress '),
    path('student-assistants/', views.student_assistant_progress, name='student_assistants'),
    path('office-users/', views.office_users, name='office_users'),

    # =======================
    # CORE FEATURES
    # =======================
    path('dashboard/', views.dashboard, name='dashboard'),
    path('logs/', views.logs, name='logs'),
    path('profile/', views.profile, name='profile'),
    path('notification/', views.notification, name='notification'),

    # =======================
    # TOOLS
    # =======================
    path('qr/', views.qr, name='qr'),
    path('scanner/', views.scanner, name='scanner'),

    # =======================
    # USER MANAGEMENT
    # =======================
    path('user-management/', views.user_management, name='user_management'),
    path('user-progress/', views.user_progress, name='user_progress'),
    path('user-dtr-details/<int:user_id>/', views.user_dtr_details, name='user_dtr_details'),

    # =======================
    # DTR SYSTEM
    # =======================
    path('monthly-dtr/', views.monthly_dtr, name='monthly_dtr'),
    path('submit-dtr/', views.submit_dtr, name='submit_dtr'),
    path('dtr/', views.dtr_records, name='dtr_records'),
    path('dtr-approvals/', views.dtr_approvals, name='dtr_approvals'),
    path('dtr-approvals/approve/<int:dtr_id>/', views.approve_dtr, name='approve_dtr'),
    path('dtr-approvals/reject/<int:dtr_id>/', views.reject_dtr, name='reject_dtr'),

    # =======================
    # NEW OFFICE HEAD ROUTES
    # =======================
    path('office/students/', views.office_student_assistants, name='office_student_assistants'),
    path('office/logs/', views.office_logs, name='office_logs'),
    path('office/dtr/', views.office_dtr_submissions, name='office_dtr_submissions'),
    path('office/reports/', views.office_reports, name='office_reports'),
    path('export-report/', views.export_students, name='export_report'),

    # =======================
    # TIME CORRECTION
    # =======================
    path('time-correction/', views.time_correction_list, name='time_correction_list'),
    path('time-correction/add/', views.add_time_record, name='add_time_record'),
    path('time-correction/update/<int:record_id>/', views.update_time_record, name='update_time_record'),
    path('time-correction/delete/<int:record_id>/', views.delete_time_record, name='delete_time_record'),
    path('time-correction/add/', views.add_time_record, name='add_time_record'),

    # =======================
    # CHAT SYSTEM
    # =======================
    path('chat/', views.chat, name='chat'),
    path('chat/send/', views.send_message, name='send_message'),
    path('chat/messages/', views.get_messages, name='get_messages'),
    path('chat/mark-read/<int:user_id>/', views.mark_messages_read, name='mark_messages_read'),

    # =======================
    # API
    # =======================
    path('export-students/', views.export_students, name='export_students'),
    path('api/record-time/', views.record_time, name='record_time'),
    path('user-progress/', views.user_progress, name='user_progress'),
    path('user-progress/<int:user_id>/json/', views.student_progress_json, name='student_progress_json'),
    path('user/delete/<int:user_id>/', views.delete_user, name='delete_user'),
    path("dtr/accept/<int:dtr_id>/", views.accept_dtr, name="accept_dtr"),
] + static(settings.STATIC_URL, document_root=str(settings.STATICFILES_DIRS[0]))
