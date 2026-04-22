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
from django.contrib.auth.views import LogoutView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('login/', views.index, name='login'),
    path('logs/', views.logs, name='logs'),
    path('notification/', views.notification, name='notification'),
    path('profile/', views.profile, name='profile'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('qr/', views.qr, name='qr'),
    path('scanner/', views.scanner, name='scanner'),
    path('user-management/', views.user_management, name='user_management'),
    path('user-progress/', views.user_progress, name='user_progress'),
    path('user-dtr-details/<int:user_id>/', views.user_dtr_details, name='user_dtr_details'),
    path('office-users/', views.office_users, name='office_users'),
    path('monthly-dtr/', views.monthly_dtr, name='monthly_dtr'),
    path('submit-dtr/', views.submit_dtr, name='submit_dtr'),
    path('dtr-approvals/', views.dtr_approvals, name='dtr_approvals'),
    path('dtr-approvals/approve/<int:dtr_id>/', views.approve_dtr, name='approve_dtr'),
    path('dtr-approvals/reject/<int:dtr_id>/', views.reject_dtr, name='reject_dtr'),
    path('time-correction/<int:dtr_id>/', views.time_correction, name='time_correction'),
    path('time-correction/update/<int:record_id>/', views.update_time_record, name='update_time_record'),
    path('time-correction/delete/<int:record_id>/', views.delete_time_record, name='delete_time_record'),
    path('time-correction/add/', views.add_time_record, name='add_time_record'),
    path('chat/', views.chat, name='chat'),
    path('chat/send/', views.send_message, name='send_message'),
    path('chat/messages/', views.get_messages, name='get_messages'),
    path('chat/mark-read/<int:user_id>/', views.mark_messages_read, name='mark_messages_read'),
    path('user-management/toggle-status/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'),
    path('user-management/delete/<int:user_id>/', views.delete_user, name='delete_user'),
    path('api/record-time/', views.record_time, name='record_time'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
] + static(settings.STATIC_URL, document_root=str(settings.STATICFILES_DIRS[0]))
