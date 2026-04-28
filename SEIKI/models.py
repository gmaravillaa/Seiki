from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    office = models.CharField(max_length=100, blank=True)
    id_number = models.CharField(max_length=50, blank=True, null=True)
    required_hours = models.DecimalField(max_digits=5, decimal_places=2, default=80.0, help_text="Total hours needed to render")  # total hours required
    
    def clean(self):
        """
        Validate that office head users (is_staff=True, is_superuser=False)
        have an office assigned.
        """
        super().clean()
        if self.user.is_staff and not self.user.is_superuser:
            if not self.office:
                raise ValidationError({
                    'office': 'Office Head users must have an office assigned.'
                })
    
    def save(self, *args, **kwargs):
        # Note: Validation is handled in clean() for forms/admin
        # We don't call full_clean() here to allow temporary invalid states
        # during automated profile creation
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.user.username} - {self.office}"

class TimeRecord(models.Model):
    RECORD_TYPES = [
        ('in', 'Time In'),
        ('out', 'Time Out'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    qr_code = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    record_type = models.CharField(max_length=3, choices=RECORD_TYPES, default='in')
    duration = models.DurationField(null=True, blank=True)  # Duration in seconds for time out records
    edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='edited_time_records')
    edited_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user.username} - {self.record_type} - {self.timestamp}"

class DTRSubmission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dtr_submissions')
    month = models.IntegerField()  # Month (1-12)
    year = models.IntegerField()  # Year
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    submitted_date = models.DateTimeField(auto_now_add=True)
    approved_date = models.DateTimeField(null=True, blank=True)
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='dtr_approvals')
    remarks = models.TextField(blank=True)  # For rejection remarks or approval notes
    total_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    class Meta:
        unique_together = ('user', 'month', 'year')

class ChatMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages', null=True, blank=True)  # None for global messages
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        if self.recipient:
            return f"{self.sender.username} -> {self.recipient.username}: {self.message[:50]}"
        else:
            return f"{self.sender.username} (global): {self.message[:50]}"
        ordering = ['-year', '-month']
    
    def __str__(self):
        return f"{self.user.username} - {self.month}/{self.year} - {self.status}"
