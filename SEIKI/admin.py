from django.contrib import admin
from .models import UserProfile, TimeRecord

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'office', 'id_number', 'required_hours')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'office', 'id_number')
    list_filter = ('office', 'required_hours')

@admin.register(TimeRecord)
class TimeRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'record_type', 'timestamp', 'duration')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    list_filter = ('record_type', 'timestamp')
    date_hierarchy = 'timestamp'