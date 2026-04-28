import json
import csv
from datetime import date, datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import models
from django.db.models import Count, Sum, Q  # Combined all models.db imports
from django.core.paginator import Paginator
from .models import DTRSubmission, TimeRecord

from .models import TimeRecord, UserProfile, DTRSubmission, ChatMessage
from django.contrib.auth import logout


def get_user_office(user):
    try:
        return user.userprofile.office
    except (UserProfile.DoesNotExist, AttributeError):
        return None


def user_in_same_office(request_user, target_user):
    if request_user.is_superuser:
        return True
    if request_user.is_staff and not request_user.is_superuser:
        return get_user_office(request_user) and get_user_office(request_user) == get_user_office(target_user)
    return False


def format_hours_display(hours_value):
    """Format hours to show minutes and seconds for values under one hour."""
    if hours_value < 1:
        total_seconds = int(hours_value * 3600)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        if minutes > 0:
            return f"{minutes} min {seconds} sec" if seconds > 0 else f"{minutes} min"
        return f"{seconds} sec" if seconds > 0 else "0 sec"
    return f"{round(hours_value, 1)} hrs"


def get_paired_records(time_records):
    """Pair time in and time out records into one completed shift row."""
    pairs = []
    current_in = None

    for record in time_records:
        if record.record_type == 'in':
            current_in = record
            continue

        if record.record_type == 'out' and current_in is not None:
            hours_display = ""
            if record.duration:
                try:
                    hours = record.duration.total_seconds() / 3600
                    hours_display = format_hours_display(hours)
                except (AttributeError, TypeError):
                    hours_display = "0 min"

            pairs.append({
                'date': current_in.timestamp.date(),
                'day': current_in.timestamp.strftime('%A'),
                'time_in': current_in.timestamp,
                'time_out': record.timestamp,
                'hours_display': hours_display,
                'time_in_record': current_in,
                'time_out_record': record,
            })
            current_in = None

    pairs.sort(key=lambda pair: pair['time_out'], reverse=True)
    return pairs


def dashboard_redirect(request):
    if request.user.is_superuser:
        return redirect('admin_dashboard')  # Django admin panel

    elif request.user.is_staff:
        return redirect('office_dashboard')

    else:
        return redirect('student_dashboard')
    
def logout_view(request):
    logout(request)
    # Redirecting to 'login' here bypasses the "next" logic 
    # because the login page itself isn't protected by @login_required
    return redirect('login')  
    
@login_required
def dtr_approvals(request):
    office = request.user.userprofile.office
    
    # Get filters from the HTML form
    status_filter = request.GET.get('status', 'pending')
    search_query = request.GET.get('search', '')

    # Filter submissions for THIS office only
    submissions = DTRSubmission.objects.filter(user__userprofile__office=office)
    
    if status_filter:
        submissions = submissions.filter(status=status_filter)
    
    context = {
        'office_name': office,
        'dtr_submissions': submissions,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    return render(request, 'office_head/dtr-approvals.html', context)

@login_required
def admin_dashboard(request):
    total_students = User.objects.filter(is_staff=False, is_superuser=False).count()
    active_offices = UserProfile.objects.values('office').distinct().count()

    # ✅ GET FILTER VALUE
    month = request.GET.get('month')
    year = 2026  # or make dynamic later

    # BASE QUERY
    dtr_query = DTRSubmission.objects.all()

    # APPLY FILTER IF EXISTS
    if month:
        dtr_query = dtr_query.filter(month=month, year=year)

    pending_dtrs = dtr_query.filter(status='pending').count()
    approved_dtrs = dtr_query.filter(status='approved').count()

    students = User.objects.filter(is_staff=False, is_superuser=False)

    for s in students:
        total = TimeRecord.objects.filter(
            user=s,
            record_type='out',
            duration__isnull=False
        ).aggregate(total=Sum('duration'))['total']

        try:
            s.total_hours = round(total.total_seconds() / 3600, 2) if total else 0
        except AttributeError:
            s.total_hours = 0

    context = {
        'total_students': total_students,
        'active_offices': active_offices,
        'pending_dtrs': pending_dtrs,
        'approved_dtrs': approved_dtrs,
        'students': students,
        'selected_month': month,  # optional (for UI highlight)
    }

    return render(request, 'caao_admin/admindashboard.html', context)



def student_progress_json(request, user_id):
    user = User.objects.get(id=user_id)

    total = TimeRecord.objects.filter(
        user=user,
        record_type='out',
        duration__isnull=False
    ).aggregate(total=models.Sum('duration'))['total']

    try:
        hours = round(total.total_seconds()/3600, 2) if total else 0
    except AttributeError:
        hours = 0
    required = user.userprofile.required_hours if hasattr(user, 'userprofile') else 80

    percent = min(100, (hours / required) * 100) if required > 0 else 0

    return JsonResponse({
        'name': user.get_full_name(),
        'office': user.userprofile.office if hasattr(user, 'userprofile') else '',
        'hours': hours,
        'required': required,
        'percent': round(percent, 1)
    })

@login_required(login_url='login')
@user_passes_test(lambda u: u.is_staff and not u.is_superuser, login_url='login')
def office_dashboard(request):
    """Refined Dashboard for Office Heads aligned with System Logic"""
    # Get or create profile for office heads - they MUST have a profile
    try:
        profile = request.user.userprofile
    except (UserProfile.DoesNotExist, AttributeError):
        # Create profile with empty office - validation happens at form level, not here
        profile, created = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={'office': '', 'required_hours': 0}
        )
    
    office = profile.office
    
    # Office heads MUST have an office assigned - this is a data integrity requirement
    if not office:
        messages.error(request, "Your office information is not set. Please contact an administrator to assign you to an office.")
        # Log the error for administrators to fix
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Office head user '{request.user.username}' (ID: {request.user.id}) has no office assigned. This is a data integrity issue.")
        # Do not redirect to profile - office heads should never see student profile
        # Instead, render an error page or show a message on the dashboard
        return render(request, 'office_head/dashboard.html', {
            'office_name': None,
            'error_message': 'No office assigned. Please contact an administrator.',
            'total_students': 0,
            'total_hours': 0,
            'pending_dtrs': 0,
            'today_attendance': 0,
            'recent_students': [],
            'recent_logs': [],
        })

    # 1. Dashboard Stats
    # Total students in this office
    total_students = UserProfile.objects.filter(office=office).exclude(user__is_staff=True).count()
    
    # Count pending DTRs
    pending_dtrs = DTRSubmission.objects.filter(
        user__userprofile__office=office, 
        status='pending'
    ).count()
    
    # SAFE CALCULATION: Total hours across all students
    total_hours_duration = TimeRecord.objects.filter(
        user__userprofile__office=office,
        record_type='out',
        duration__isnull=False
    ).aggregate(total=Sum('duration'))['total']
    
    # CRITICAL FIX: Sum() returns None if no records exist. 
    # Check for None before calling .total_seconds() to prevent a 500 error.
    try:
        total_hours = round(total_hours_duration.total_seconds() / 3600, 2) if total_hours_duration else 0
    except AttributeError:
        total_hours = 0

    # 2. Daily Attendance Percentage
    today_count = TimeRecord.objects.filter(
        user__userprofile__office=office,
        timestamp__date=date.today()
    ).values('user').distinct().count()
    
    # Avoid DivisionByZero error
    today_attendance = round((today_count / total_students) * 100, 0) if total_students > 0 else 0
    
    # 3. Tables/Lists for the UI
    # Recent activity: Students ordered by last login
    # Added select_related('userprofile') for faster performance in the template
    recent_students = User.objects.filter(
        userprofile__office=office,
        is_staff=False
    ).select_related('userprofile').order_by('-last_login')[:5]
    

    recent_logs = TimeRecord.objects.filter(
        user__userprofile__office=office
    ).select_related('user').order_by('-timestamp')[:5]

    context = {
        'office_name': office,
        'total_students': total_students,
        'total_hours': total_hours,
        'pending_dtrs': pending_dtrs,
        'today_attendance': int(today_attendance), # Cast to int for cleaner display
        'recent_students': recent_students,
        'recent_logs': recent_logs,
    }
    
    return render(request, 'office_head/dashboard.html', context)
@login_required
@user_passes_test(lambda u: u.is_staff and not u.is_superuser, login_url='login')
def office_student_assistants(request):
    """View list of all SAs in the department"""
    try:
        profile = request.user.userprofile
    except (UserProfile.DoesNotExist, AttributeError):
        profile, _ = UserProfile.objects.get_or_create(user=request.user, defaults={'office': '', 'required_hours': 0})
    
    office = profile.office
    if not office:
        messages.error(request, "Your office information is not set. Please contact an administrator.")
        return redirect('office_dashboard')
    
    search_query = request.GET.get('search', '')
    
    students = User.objects.filter(
        userprofile__office=office,
        is_staff=False
    ).select_related('userprofile')

    if search_query:
        students = students.filter(
            Q(first_name__icontains=search_query) | 
            Q(last_name__icontains=search_query) |
            Q(userprofile__id_number__icontains=search_query)
        )

    return render(request, 'office_head/student_assistants.html', {
        'students': students,
        'office_name': office,
    })

@login_required
@user_passes_test(lambda u: u.is_staff and not u.is_superuser, login_url='login')
def office_logs(request):
    """Detailed logs for the office head to monitor attendance"""
    try:
        profile = request.user.userprofile
    except (UserProfile.DoesNotExist, AttributeError):
        profile, _ = UserProfile.objects.get_or_create(user=request.user, defaults={'office': '', 'required_hours': 0})
    
    office = profile.office
    if not office:
        messages.error(request, "Your office information is not set. Please contact an administrator.")
        return redirect('office_dashboard')
    
    logs = TimeRecord.objects.filter(
        user__userprofile__office=office
    ).order_by('-timestamp')
    
    return render(request, 'office_head/logs.html', {
        'logs': logs,
        'office_name': office,
    })

@login_required
@user_passes_test(lambda u: u.is_staff and not u.is_superuser, login_url='login')
def office_dtr_submissions(request):
    """View all DTR submissions for the department"""
    try:
        profile = request.user.userprofile
    except (UserProfile.DoesNotExist, AttributeError):
        profile, _ = UserProfile.objects.get_or_create(user=request.user, defaults={'office': '', 'required_hours': 0})
    
    office = profile.office
    if not office:
        messages.error(request, "Your office information is not set. Please contact an administrator.")
        return redirect('office_dashboard')
    
    # TEMPORARY DEBUG: Show all submissions without any filtering
    base_submissions = DTRSubmission.objects.select_related('user', 'user__userprofile').order_by('-submitted_date')
    
    # Filter values for the template
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    month_filter = request.GET.get('month', '')

    # TEMPORARY: No filtering applied
    submissions = base_submissions

    # TEMPORARY: Count all pending submissions
    pending_count = base_submissions.filter(status='pending').count()
    approved_count = base_submissions.filter(status='approved').count()
    rejected_count = base_submissions.filter(status='rejected').count()

    paginator = Paginator(submissions, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'office_head/dtr_submissions.html', {
        'submissions': page_obj,
        'office_name': office,
        'status_filter': status_filter,
        'search_query': search_query,
        'month_filter': month_filter,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
    })

@login_required
@user_passes_test(lambda u: u.is_staff and not u.is_superuser, login_url='login')
def office_reports(request):
    """Departmental analytics and hour breakdowns"""
    # Logic for rendering reports.html
    return render(request, 'office_head/reports.html')


@login_required
@user_passes_test(lambda u: u.is_staff and not u.is_superuser, login_url='login')
def export_report(request):
    """Export office reports as CSV"""
    import csv
    from datetime import datetime
    from django.http import HttpResponse
    
    report_type = request.GET.get('report_type', 'attendance')
    
    # Get user's office
    try:
        profile = request.user.userprofile
    except (UserProfile.DoesNotExist, AttributeError):
        profile, _ = UserProfile.objects.get_or_create(user=request.user, defaults={'office': '', 'required_hours': 0})
    
    office = profile.office
    if not office:
        messages.error(request, "Your office information is not set.")
        return redirect('office_dashboard')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report_{datetime.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    
    if report_type == 'attendance':
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        writer.writerow(['Attendance Report', f'From: {date_from} To: {date_to}'])
        writer.writerow([])
        writer.writerow(['Student Name', 'Date', 'Time In', 'Time Out', 'Duration'])
        
        # Query attendance data
        records = TimeRecord.objects.filter(
            user__userprofile__office=office,
            timestamp__date__gte=date_from,
            timestamp__date__lte=date_to
        ).select_related('user').order_by('user__username', 'timestamp')
        
        for record in records:
            writer.writerow([
                record.user.get_full_name() or record.user.username,
                record.timestamp.date(),
                record.timestamp.time() if record.record_type == 'in' else '',
                record.timestamp.time() if record.record_type == 'out' else '',
                str(record.duration) if record.duration else ''
            ])
    
    elif report_type == 'hours':
        month = request.GET.get('month')  # Format: YYYY-MM
        
        writer.writerow(['Hours Summary Report', f'Month: {month}'])
        writer.writerow([])
        writer.writerow(['Student Name', 'ID Number', 'Total Hours', 'Required Hours', 'Remaining'])
        
        # Get students in office
        students = User.objects.filter(
            userprofile__office=office,
            is_staff=False
        ).select_related('userprofile')
        
        for student in students:
            # Calculate total hours for the month
            records = TimeRecord.objects.filter(
                user=student,
                record_type='out',
                duration__isnull=False,
                timestamp__year=int(month[:4]),
                timestamp__month=int(month[5:7])
            )
            
            total_seconds = sum([r.duration.total_seconds() for r in records if r.duration])
            total_hours = round(total_seconds / 3600, 2)
            required = student.userprofile.required_hours if hasattr(student, 'userprofile') else 80.0
            remaining = max(0, float(required) - total_hours)
            
            writer.writerow([
                student.get_full_name() or student.username,
                student.userprofile.id_number if hasattr(student, 'userprofile') else '',
                total_hours,
                required,
                remaining
            ])
    
    elif report_type == 'dtr_summary':
        month = request.GET.get('month')  # Format: YYYY-MM
        year = int(month[:4])
        month_num = int(month[5:7])
        
        writer.writerow(['DTR Summary Report', f'Month: {month}'])
        writer.writerow([])
        writer.writerow(['Student Name', 'Status', 'Submitted Date', 'Total Hours', 'Approver'])
        
        # Get DTR submissions for the office
        submissions = DTRSubmission.objects.filter(
            user__userprofile__office=office,
            month=month_num,
            year=year
        ).select_related('user', 'approver')
        
        for submission in submissions:
            writer.writerow([
                submission.user.get_full_name() or submission.user.username,
                submission.get_status_display(),
                submission.submitted_date.strftime('%Y-%m-%d') if submission.submitted_date else '',
                submission.total_hours,
                submission.approver.get_full_name() if submission.approver else 'N/A'
            ])
    
    return response


@login_required
def student_dashboard(request):
    """Student Dashboard with dynamic data from database"""
    user = request.user
    
    try:
        profile = user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user, office="", required_hours=80.0)
    
    # Ensure profile has required fields with defaults
    if not profile.office:
        profile.office = ""
    if profile.required_hours is None:
        profile.required_hours = 80.0
    
    # Get all time records for this student
    time_records = TimeRecord.objects.filter(user=user).order_by('-timestamp')
    
    # Calculate total hours rendered
    total_duration = time_records.filter(
        record_type='out',
        duration__isnull=False
    ).aggregate(total=Sum('duration'))['total']
    
    total_hours = 0
    if total_duration:
        total_hours = round(total_duration.total_seconds() / 3600, 2)
    
    # Calculate hours this week
    from django.utils import timezone
    from datetime import timedelta
    today = timezone.now()
    week_start = today - timedelta(days=today.weekday())
    
    week_duration = time_records.filter(
        timestamp__gte=week_start,
        record_type='out',
        duration__isnull=False
    ).aggregate(total=Sum('duration'))['total']
    
    week_hours = 0
    if week_duration:
        week_hours = round(week_duration.total_seconds() / 3600, 2)
    
    # Calculate remaining hours
    required_hours = float(profile.required_hours) if profile.required_hours else 80.0
    remaining_hours = max(required_hours - total_hours, 0)  # Don't show negative
    
    # Get recent time records for logs (not DTR submissions)
    recent_records = time_records[:10]  # Last 10 records
    
    # Group recent records by date for display and aggregate daily totals
    recent_logs = {}
    for record in recent_records:
        record_date = record.timestamp.date()
        if record_date not in recent_logs:
            recent_logs[record_date] = {
                'records': [],
                'total_duration_seconds': 0,
                'daily_total_display': '0 sec',
            }
        
        # Calculate hours for this record if it's an 'out' record with duration
        hours_display = ""
        if record.record_type == "out" and record.duration:
            try:
                hours = record.duration.total_seconds() / 3600
                hours_display = format_hours_display(hours)
                recent_logs[record_date]['total_duration_seconds'] += record.duration.total_seconds()
            except (AttributeError, TypeError):
                hours_display = "0 sec"
        
        # Add hours_display to the record for template use
        record.hours_display = hours_display
        recent_logs[record_date]['records'].append(record)

    for record_date, info in recent_logs.items():
        if info['total_duration_seconds']:
            info['daily_total_display'] = format_hours_display(info['total_duration_seconds'] / 3600)
        else:
            info['daily_total_display'] = '0 sec'
    if required_hours > 0:
        progress_percentage = min((total_hours / required_hours) * 100, 100)
    
    # Format display values for template
    total_hours_display = format_hours_display(total_hours)
    week_hours_display = format_hours_display(week_hours)
    remaining_hours_display = format_hours_display(remaining_hours)
    
    context = {
        'profile': profile,
        'total_hours': total_hours,
        'total_hours_display': total_hours_display,
        'week_hours': week_hours,
        'week_hours_display': week_hours_display,
        'remaining_hours': remaining_hours,
        'remaining_hours_display': remaining_hours_display,
        'required_hours': required_hours,
        'progress_percentage': progress_percentage,
        'recent_logs': recent_logs,
        'time_records_count': time_records.count(),
    }
    return render(request, 'student/studentdashboard.html', context)

@login_required
def student_logs(request):
    """Student Assistant Time Logs"""
    user = request.user
    
    # Get all time records in chronological order so we can pair in/out scans
    time_records = TimeRecord.objects.filter(user=user).order_by('timestamp')
    paired_records = get_paired_records(time_records)
    
    approved_dtrs = DTRSubmission.objects.filter(user=user, status='approved').count()
    pending_dtrs = DTRSubmission.objects.filter(user=user, status='pending').count()

    context = {
        'paired_records': paired_records,
        'total_pairs': len(paired_records),
        'approved_dtrs': approved_dtrs,
        'pending_dtrs': pending_dtrs,
    }
    return render(request, 'student/studentlogs.html', context)

@login_required
def student_submit_dtr(request):
    """Student Assistant Submit DTR"""
    from datetime import datetime
    user = request.user
    
    try:
        profile = user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user, office="", required_hours=80.0)
    
    # Ensure profile has required fields with defaults
    if not profile.office:
        profile.office = ""
    if profile.required_hours is None:
        profile.required_hours = 80.0

    current_month = datetime.now().month
    current_year = datetime.now().year
    month_name = datetime.now().strftime('%B')
    
    # Check if DTR already submitted for this month
    existing_dtr = DTRSubmission.objects.filter(
        user=user,
        month=current_month,
        year=current_year
    ).first()
    
    # Get all time records for current month
    time_records = TimeRecord.objects.filter(
        user=user,
        timestamp__month=current_month,
        timestamp__year=current_year
    ).order_by('timestamp')
    
    # Calculate total hours for this month
    total_duration = time_records.filter(
        record_type='out',
        duration__isnull=False
    ).aggregate(total=Sum('duration'))['total']
    
    total_hours = 0
    if total_duration:
        total_hours = round(total_duration.total_seconds() / 3600, 2)
    
    # Group records by date for daily count and build paired shift records
    daily_logs = {}
    for record in time_records:
        record_date = record.timestamp.date()
        daily_logs.setdefault(record_date, []).append(record)

    monthly_pairs = get_paired_records(time_records)
    has_time_records = time_records.exists()

    context = {
        'current_month': current_month,
        'current_year': current_year,
        'month_name': month_name,
        'daily_logs': daily_logs,
        'monthly_pairs': monthly_pairs,
        'total_hours': total_hours,
        'existing_dtr': existing_dtr,
        'time_records': time_records,
        'has_time_records': has_time_records,
    }
    return render(request, 'student/studentsubmitdtr.html', context)

@login_required
def student_qr_code(request):
    """Student Assistant Availability Schedule - QR Code"""
    user = request.user
    
    try:
        profile = user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user, office="", required_hours=80.0)
    
    # Ensure profile has required fields with defaults
    if not profile.office:
        profile.office = ""
    if profile.required_hours is None:
        profile.required_hours = 80.0
    return render(request, 'student/studentqrcode.html')

@login_required
def student_profile_page(request):
    """Student Assistant Profile Page"""
    user = request.user
    
    try:
        profile = user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user, office="", required_hours=80.0)
    
    # Ensure profile has required fields with defaults
    if not profile.office:
        profile.office = ""
    if profile.required_hours is None:
        profile.required_hours = 80.0
    
    # Get statistics
    total_records = TimeRecord.objects.filter(user=user).count()
    total_duration = TimeRecord.objects.filter(
        user=user,
        record_type='out',
        duration__isnull=False
    ).aggregate(total=Sum('duration'))['total']
    
    total_hours = 0
    if total_duration:
        try:
            total_hours = round(total_duration.total_seconds() / 3600, 2)
        except (AttributeError, TypeError):
            total_hours = 0
    
    # Calculate remaining hours safely
    required_hours = float(profile.required_hours) if profile.required_hours else 80.0
    remaining_hours = max(required_hours - total_hours, 0)
    
    dtr_count = DTRSubmission.objects.filter(user=user).count()
    approved_dtr_count = DTRSubmission.objects.filter(user=user, status='approved').count()
    
    context = {
        'profile': profile,
        'total_hours': total_hours,
        'remaining_hours': remaining_hours,
        'total_records': total_records,
        'dtr_count': dtr_count,
        'approved_dtr_count': approved_dtr_count,
    }
    return render(request, 'student/studentprofile.html', context)

def user_progress_json(request, user_id):

    user = User.objects.select_related('userprofile').get(id=user_id)

    # Total rendered hours
    total_duration = TimeRecord.objects.filter(
        user=user,
        record_type='out',
        duration__isnull=False
    ).aggregate(
        total=models.Sum('duration')
    )['total']

    total_hours_rendered = 0

    if total_duration:
        total_seconds = total_duration.total_seconds()
        total_hours_rendered = total_seconds / 3600

    # Required hours
    required_hours = (
        user.userprofile.required_hours
        if hasattr(user, 'userprofile')
        else 80.0
    )

    # Percentage
    percentage = (
        min(100, (total_hours_rendered / float(required_hours)) * 100)
        if required_hours > 0
        else 0
    )

    return JsonResponse({

        "name": user.get_full_name(),

        "student_id": user.username,

        "office": (
            user.userprofile.office
            if hasattr(user, 'userprofile')
            else "N/A"
        ),

        "status": (
            "Active"
            if user.is_active
            else "Inactive"
        ),

        "percent": round(percentage, 1)

    })

@login_required
def user_management(request):
    return render(request, 'caao_admin/user_management.html')

@login_required
def student_assistants(request):
    return render(request, 'caao_admin/student_assistants.html')

@login_required
def profile(request):
    try:
        user_profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        user_profile = UserProfile.objects.create(user=request.user)
    
    total_duration = TimeRecord.objects.filter(
        user=request.user,
        record_type='out',
        duration__isnull=False
    ).aggregate(total=Sum('duration'))['total']

    try:
        total_hours = round(total_duration.total_seconds() / 3600, 2) if total_duration else 0
    except AttributeError:
        total_hours = 0
    required = user_profile.required_hours
    remaining = max(0, float(required) - total_hours)
    percent = min(100, (total_hours / float(required)) * 100) if required > 0 else 0

    context = {
        'total_hours': total_hours,
        'required_hours': required,
        'remaining_hours': round(remaining, 2),
        'percentage': round(percent, 1),
    }
    
    return render(request, 'core/profile.html', context)
    

@login_required
def dtr_records(request):
    # Only allow staff and superusers to access this page
    if not (request.user.is_staff or request.user.is_superuser):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Access denied. This page is only for staff members.")

    # Get filters from the HTML form
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')

    # For superusers and staff, show all DTR submissions from all students
    dtr_records = DTRSubmission.objects.select_related('user', 'user__userprofile', 'approver').order_by('-submitted_date')

    # Apply search filter
    if search_query:
        dtr_records = dtr_records.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__userprofile__id_number__icontains=search_query)
        )

    # Apply status filter
    if status_filter:
        if status_filter == 'pending':
            dtr_records = dtr_records.filter(status='pending')
        elif status_filter == 'accepted':
            dtr_records = dtr_records.filter(status='approved')
        elif status_filter == 'rejected':
            dtr_records = dtr_records.filter(status='rejected')

    # Calculate counts
    all_submissions = DTRSubmission.objects.all()
    pending_count = all_submissions.filter(status='pending').count()
    accepted_count = all_submissions.filter(status='approved').count()

    context = {
        'dtr_records': dtr_records,
        'pending_count': pending_count,
        'accepted_count': accepted_count,
        'search_query': search_query,
        'status_filter': status_filter,
    }
    return render(request, 'caao_admin/dtr.html', context)

def index(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            auth_login(request, user)
            return redirect('dashboard_redirect')  # Redirect to dashboard after successful login
        else:
            # Display error message on login page
            return render(request, 'core/index.html', {'error': 'Invalid credentials'})

    return render(request, 'core/index.html')

@login_required(login_url='login')
def notification(request):
    total_duration = TimeRecord.objects.filter(
        user=request.user,
        record_type='out',
        duration__isnull=False
    ).aggregate(total=models.Sum('duration'))['total']
    
    # Convert duration to hours (duration is in seconds)
    total_hours_rendered = 0
    if total_duration:
        try:
            total_seconds = total_duration.total_seconds()
            total_hours_rendered = total_seconds / 3600  # Convert to hours
        except AttributeError:
            total_hours_rendered = 0
    
    # Get required hours from user profile
    required_hours = request.user.userprofile.required_hours if hasattr(request.user, 'userprofile') else 80.0
    
    # Calculate remaining hours
    remaining_hours = max(0, float(required_hours) - total_hours_rendered)
    
    # Calculate percentage (capped at 100%)
    percentage = min(100, (total_hours_rendered / float(required_hours)) * 100) if required_hours > 0 else 0
    
    context = {
        'total_hours_rendered': round(total_hours_rendered, 2),
        'required_hours': required_hours,
        'remaining_hours': round(remaining_hours, 2),
        'percentage': round(percentage, 1),
    }
    
    return render(request, 'core/notification.html', context)

@login_required(login_url='login')
def dashboard(request):
    """Dashboard/home page for students/users"""
    
    today = date.today()
    current_time = timezone.now()
    
    # Month names for display
    month_names = {
        1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 6: 'June',
        7: 'July', 8: 'August', 9: 'September', 10: 'October', 11: 'November', 12: 'December'
    }
    
    # Get today's time logs
    today_logs = TimeRecord.objects.filter(
        user=request.user,
        timestamp__date=today
    ).order_by('timestamp')
    
    # Get current month's DTR submission status
    current_month = today.month
    current_year = today.year
    
    dtr_submission = DTRSubmission.objects.filter(
        user=request.user,
        month=current_month,
        year=current_year
    ).first()
    
    # Calculate today's total hours
    today_duration = TimeRecord.objects.filter(
        user=request.user,
        record_type='out',
        duration__isnull=False,
        timestamp__date=today
    ).aggregate(total=models.Sum('duration'))['total']
    
    today_hours = 0
    if today_duration:
        today_hours = today_duration.total_seconds() / 3600
    
    context = {
        'current_date': today,
        'current_time': current_time,
        'today_logs': today_logs,
        'dtr_submission': dtr_submission,
        'today_hours': round(today_hours, 2),
        'month_names': month_names,
    }
    
    return render(request, 'core/dashboard.html', context)

@login_required(login_url='login')
def qr(request):
    return render(request, 'core/qr.html')

@login_required(login_url='login')
def scanner(request):
    if not request.user.is_staff:
        return redirect('dashboard_redirect')
    return render(request, 'office_head/scanner.html')

@csrf_exempt
@require_http_methods(['POST'])
@login_required(login_url='login')
def record_time(request):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

    try:
        data = json.loads(request.body.decode('utf-8')) if isinstance(request.body, bytes) else json.loads(request.body)
        qr_code = data.get('qr_code')
        if not qr_code:
            raise ValueError('Missing qr_code')

        user_id_str, username = qr_code.split(':', 1)
        user_id = int(user_id_str)
    except (ValueError, IndexError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'error': 'Invalid QR code format'}, status=400)

    try:
        target_user = User.objects.get(id=user_id, username=username)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'}, status=404)

    today = date.today()
    last_record = TimeRecord.objects.filter(
        user=target_user,
        timestamp__date=today
    ).order_by('-timestamp').first()

    if last_record and last_record.record_type == 'in':
        record_type = 'out'
        message_text = 'Time out'
    else:
        record_type = 'in'
        message_text = 'Time in'

    time_record = TimeRecord.objects.create(
        user=target_user,
        qr_code=qr_code,
        record_type=record_type
    )

    if record_type == 'out':
        time_in_record = TimeRecord.objects.filter(
            user=target_user,
            timestamp__date=today,
            record_type='in'
        ).order_by('-timestamp').first()
        if time_in_record:
            duration = time_record.timestamp - time_in_record.timestamp
            time_record.duration = duration
            time_record.save()

    return JsonResponse({
        'success': True,
        'message': f'{message_text} recorded for {target_user.username} at {timezone.localtime(time_record.timestamp).strftime("%H:%M:%S")}',
        'timestamp': time_record.timestamp.isoformat(),
        'record_type': record_type
    })

@login_required(login_url='login')
def logs(request):
    # Get all time records for the current user
    time_records = TimeRecord.objects.filter(
        user=request.user
    ).order_by('timestamp')
    
    # Group records by date and pair time in/out
    daily_sessions = {}
    
    for record in time_records:
        date_key = timezone.localtime(record.timestamp).date()
        if date_key not in daily_sessions:
            daily_sessions[date_key] = []
        
        daily_sessions[date_key].append(record)
    
    # Process each day's records to create sessions
    logs_data = []
    for date_key in sorted(daily_sessions.keys(), reverse=True):
        records = daily_sessions[date_key]
        
        # Pair time in with subsequent time out
        i = 0
        while i < len(records):
            if records[i].record_type == 'in':
                time_in = records[i]
                time_out = None
                duration_display = "No time out yet"
                
                # Look for the next time out after this time in
                for j in range(i + 1, len(records)):
                    if records[j].record_type == 'out':
                        time_out = records[j]
                        # Calculate duration between time in and time out
                        duration = time_out.timestamp - time_in.timestamp
                        total_seconds = int(duration.total_seconds())
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        seconds = total_seconds % 60
                        duration_display = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        break
                
                logs_data.append({
                    'date': date_key,
                    'time_in': timezone.localtime(time_in.timestamp),
                    'time_out': timezone.localtime(time_out.timestamp) if time_out else None,
                    'duration': duration_display,
                })
                
                # Skip the time out we just used
                if time_out:
                    i = j
                else:
                    i += 1
            else:
                i += 1
    
    # Sort logs_data by time_in descending (most recent first)
    logs_data.sort(key=lambda x: x['time_in'], reverse=True)
    
    return render(request, 'core/logs.html', {'logs_data': logs_data})

def dtr_acceptance(request):
    search = request.GET.get("search", "")
    status = request.GET.get("status", "")

    dtr_records = DTRSubmission.objects.select_related("user", "user__userprofile")

    if search:
        dtr_records = dtr_records.filter(
            user__first_name__icontains=search
        ) | dtr_records.filter(
            user__last_name__icontains=search
        )

    if status:
        dtr_records = dtr_records.filter(status=status)

    return render(request, "dtr_acceptance.html", {
        "dtr_records": dtr_records,
        "search_query": search
    })

def accept_dtr(request, dtr_id):
    dtr = DTRSubmission.objects.get(id=dtr_id)
    dtr.status = "accepted"
    dtr.save()
    return redirect("dtr_acceptance")

def user_progress_data(request):
    students = User.objects.filter(is_staff=False, is_superuser=False)

    data = []

    for student in students:
        profile = getattr(student, 'userprofile', None)

        # total hours from TimeRecord
        records = TimeRecord.objects.filter(user=student)

        total_seconds = sum([
            r.duration.total_seconds() if r.duration else 0
            for r in records
        ])

        total_hours = round(total_seconds / 3600, 2)

        required = profile.required_hours if profile else 80
        percent = int((total_hours / required) * 100) if required else 0

        data.append({
            'student': student,
            'profile': profile,
            'total_hours': total_hours,
            'required': required,
            'percent': percent
        })

    return render(request, 'caao_admin/user_progress.html', {
        'data': data
    })

@user_passes_test(lambda u: u.is_superuser)
def user_management(request):
    """User management page for superusers"""
    if request.method == 'POST':
        # Handle user creation
        username = request.POST.get('username')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        office = request.POST.get('office')
        id_number = request.POST.get('id_number')
        required_hours = request.POST.get('required_hours')
        role = request.POST.get('role')
        
        # Set permissions based on role
        if role == 'office_head':
            is_staff = True
            is_superuser = False
        elif role == 'caao_staff':
            is_staff = True
            is_superuser = True
        else:  # student_assistant
            is_staff = False
            is_superuser = False
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists!')
            users = User.objects.all().select_related('userprofile').order_by('username')
            return render(request, 'caao_admin/user_management.html', {'users': users})
        
        # Validate office_head has an office selected
        if role == 'office_head' and not office:
            messages.error(request, 'Office Head users must have an office assigned!')
            users = User.objects.all().select_related('userprofile').order_by('username')
            return render(request, 'caao_admin/user_management.html', {'users': users})
        
        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_staff=is_staff,
                is_superuser=is_superuser
            )
            
            # Set appropriate defaults based on role
            if role == 'office_head':
                # Office heads don't need id_number or required_hours
                profile_defaults = {
                    'office': office,
                    'id_number': '',
                    'required_hours': 0
                }
            else:
                # Students need all fields
                profile_defaults = {
                    'office': office,
                    'id_number': id_number,
                    'required_hours': required_hours or 80.0
                }
            
            # Update or create user profile with the provided data
            UserProfile.objects.update_or_create(
                user=user,
                defaults=profile_defaults
            )
            
            messages.success(request, f'User {user.username} created successfully!')
            
        except Exception as e:
            messages.error(request, f'Error creating user: {str(e)}')
    
    # Get all users with their profiles
    users = User.objects.all().select_related('userprofile').order_by('username')
    return render(request, 'caao_admin/user_management.html', {'users': users})
    

@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["POST"])
def toggle_user_status(request, user_id):
    """Toggle user active/inactive status"""
    try:
        user = User.objects.get(id=user_id)
        
        # Prevent superuser from deactivating themselves
        if user == request.user:
            messages.error(request, "You cannot deactivate your own account.")
            return redirect('user_management')
        
        # Toggle the active status
        user.is_active = not user.is_active
        user.save()
        
        status_text = "activated" if user.is_active else "deactivated"
        messages.success(request, f'User {user.username} has been {status_text}.')
        
    except User.DoesNotExist:
        messages.error(request, "User not found.")
    except Exception as e:
        messages.error(request, f"Error updating user status: {str(e)}")
    
    return redirect('user_management')

@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["POST"])
def delete_user(request, user_id):
    """Delete a user"""
    try:
        user = User.objects.get(id=user_id)
        
        # Prevent superuser from deleting themselves
        if user == request.user:
            messages.error(request, "You cannot delete your own account.")
            return redirect('user_management')
        
        # Prevent deleting other superusers
        if user.is_superuser and user != request.user:
            messages.error(request, "You cannot delete other superuser accounts.")
            return redirect('user_management')
        
        username = user.username
        user.delete()
        
        messages.success(request, f'User {username} has been deleted successfully.')
        
    except User.DoesNotExist:
        messages.error(request, "User not found.")
    except Exception as e:
        messages.error(request, f"Error deleting user: {str(e)}")
    
    return redirect('user_management')

@user_passes_test(lambda u: u.is_superuser)
def user_progress(request):
    """User progress page for superusers to view detailed user information and work progress"""
    from django.core.paginator import Paginator
    
    # Get search query
    search_query = request.GET.get('search', '').strip()
    
    # Get all users with their profiles
    users = User.objects.all().select_related('userprofile')
    users = User.objects.filter(is_staff=False, is_superuser=False)
    
    # Apply search filter if query exists
    if search_query:
        users = users.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(userprofile__office__icontains=search_query)
        )
    
    users = users.order_by('username')
    
    # Pagination - 6 users per page
    paginator = Paginator(users, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    users_data = []
    
    # Get current month and year
    from datetime import datetime
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    for user in page_obj:
        # Calculate total hours rendered for this user
        total_duration = TimeRecord.objects.filter(
            user=user,
            record_type='out',
            duration__isnull=False
        ).aggregate(total=models.Sum('duration'))['total']
        
        # Convert duration to hours (duration is in seconds)
        total_hours_rendered = 0
        if total_duration:
            total_seconds = total_duration.total_seconds()
            total_hours_rendered = total_seconds / 3600  # Convert to hours
        
        # Get required hours from user profile
        required_hours = user.userprofile.required_hours if hasattr(user, 'userprofile') else 80.0
        
        # Calculate remaining hours
        remaining_hours = max(0, float(required_hours) - total_hours_rendered)
        
        # Calculate percentage (capped at 100%)
        percentage = min(100, (total_hours_rendered / float(required_hours)) * 100) if required_hours > 0 else 0
        
        # Get recent time records (last 10)
        recent_records = TimeRecord.objects.filter(user=user).order_by('-timestamp')[:10]
        
        # Get DTR submission status for current month
        try:
            dtr_submission = DTRSubmission.objects.get(user=user, month=current_month, year=current_year)
            dtr_status = dtr_submission.get_status_display()
        except DTRSubmission.DoesNotExist:
            dtr_status = "Not Submitted"
        
        users_data.append({
            'user': user,
            'profile': user.userprofile if hasattr(user, 'userprofile') else None,
            'total_hours_rendered': round(total_hours_rendered, 2),
            'required_hours': required_hours,
            'remaining_hours': round(remaining_hours, 2),
            'percentage': round(percentage, 1),
            'recent_records': recent_records,
            'dtr_status': dtr_status,
        })
    
    context = {
        'users_data': users_data,
        'page_obj': page_obj,
        'search_query': search_query,
        'is_paginated': page_obj.has_other_pages(),
    }
    
    return render(request, 'caao_admin/user_progress.html', context)

def student_assistant_progress(request):
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'all')

    students = User.objects.filter(is_staff=False, is_superuser=False)

    data = []

    for student in students:
        profile = UserProfile.objects.filter(user=student).first()

        # 🔍 SEARCH FILTER
        if search:
            if not (
                search.lower() in student.get_full_name().lower() or
                (profile and search.lower() in (profile.office or '').lower()) or
                (profile and search.lower() in (profile.id_number or '').lower())
            ):
                continue

        records = TimeRecord.objects.filter(user=student, record_type='out')

        total_hours = sum([
            (r.duration.total_seconds() / 3600) for r in records if r.duration
        ])

        required = float(profile.required_hours) if profile else 80
        percent = int((total_hours / required) * 100) if required else 0

        # 🎯 STATUS
        if percent >= 100:
            status = "Eligible"
            color = "green"
        else:
            status = "Ineligible"
            color = "red"

        # 🎯 STATUS FILTER
        if status_filter == "eligible" and percent < 100:
            continue
        if status_filter == "ineligible" and percent >= 100:
            continue

        data.append({
            "student": student,
            "profile": profile,
            "total_hours": round(total_hours, 2),
            "required": required,
            "percent": percent,
            "status": status,
            "color": color,
        })

    return render(request, "caao_admin/student_assistant_progress.html", {
        "data": data
    })


def export_students(request):
    students = User.objects.filter(is_staff=False, is_superuser=False)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="students.csv"'

    writer = csv.writer(response)
    writer.writerow(['Name', 'ID', 'Office', 'Total Hours', 'Required', 'Status'])

    for student in students:
        profile = UserProfile.objects.filter(user=student).first()

        records = TimeRecord.objects.filter(user=student, record_type='out')

        total_hours = sum([
            (r.duration.total_seconds() / 3600) for r in records if r.duration
        ])

        required = float(profile.required_hours) if profile else 80

        status = "Eligible" if total_hours >= required else "Ineligible"

        writer.writerow([
            student.get_full_name(),
            profile.id_number if profile else "",
            profile.office if profile else "",
            round(total_hours, 2),
            required,
            status
        ])

    return response

@user_passes_test(lambda u: u.is_superuser)
def user_dtr_details(request, user_id):
    """View all DTR submissions for a specific user"""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect('user_progress')
    
    # Get all DTR submissions for this user, sorted from latest to oldest
    dtr_submissions = DTRSubmission.objects.filter(user=user).order_by('-year', '-month', '-submitted_date')
    
    # Calculate user stats
    total_duration = TimeRecord.objects.filter(
        user=user,
        record_type='out',
        duration__isnull=False
    ).aggregate(total=models.Sum('duration'))['total']
    
    total_hours_rendered = 0
    if total_duration:
        try:
            total_seconds = total_duration.total_seconds()
            total_hours_rendered = total_seconds / 3600
        except AttributeError:
            total_hours_rendered = 0
    
    required_hours = user.userprofile.required_hours if hasattr(user, 'userprofile') else 80.0
    remaining_hours = max(0, float(required_hours) - total_hours_rendered)
    percentage = min(100, (total_hours_rendered / float(required_hours)) * 100) if required_hours > 0 else 0
    
    context = {
        'user': user,
        'profile': user.userprofile if hasattr(user, 'userprofile') else None,
        'dtr_submissions': dtr_submissions,
        'total_hours_rendered': round(total_hours_rendered, 2),
        'required_hours': required_hours,
        'remaining_hours': round(remaining_hours, 2),
        'percentage': round(percentage, 1),
    }
    
    return render(request, 'caao_admin/user_dtr_details.html', context)

#office head
@login_required(login_url='login')
@user_passes_test(lambda u: u.is_staff and not u.is_superuser, login_url='login')
def office_users(request):
    """Office users page for office heads to view users in their office"""
    from django.core.paginator import Paginator
    
    # Get current user's office - create profile if missing
    try:
        profile = request.user.userprofile
    except (UserProfile.DoesNotExist, AttributeError):
        profile, _ = UserProfile.objects.get_or_create(user=request.user, defaults={'office': '', 'required_hours': 0})
    
    user_office = profile.office
    if not user_office:
        messages.error(request, "Your office information is not set. Please contact an administrator.")
        return redirect('office_dashboard')
    
    # Get search query
    search_query = request.GET.get('search', '').strip()
    
    # Get users in the same office (excluding the current user)
    office_users = User.objects.filter(
        userprofile__office=user_office
    ).exclude(id=request.user.id).select_related('userprofile')
    
    # Apply search filter if query exists
    if search_query:
        office_users = office_users.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(username__icontains=search_query)
        )
    
    office_users = office_users.order_by('username')
    
    # Pagination - 6 users per page
    paginator = Paginator(office_users, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    users_data = []
    
    for user in page_obj:
        # Calculate total hours rendered for this user
        total_duration = TimeRecord.objects.filter(
            user=user,
            record_type='out',
            duration__isnull=False
        ).aggregate(total=models.Sum('duration'))['total']
        
        # Convert duration to hours (duration is in seconds)
        total_hours_rendered = 0
        if total_duration:
            total_seconds = total_duration.total_seconds()
            total_hours_rendered = total_seconds / 3600  # Convert to hours
        
        # Get required hours from user profile
        required_hours = user.userprofile.required_hours if hasattr(user, 'userprofile') else 80.0
        
        # Calculate remaining hours
        remaining_hours = max(0, float(required_hours) - total_hours_rendered)
        
        # Calculate percentage (capped at 100%)
        percentage = min(100, (total_hours_rendered / float(required_hours)) * 100) if required_hours > 0 else 0
        
        # Get recent time records (last 5 for office view)
        recent_records = TimeRecord.objects.filter(user=user).order_by('-timestamp')[:5]
        
        users_data.append({
            'user': user,
            'profile': user.userprofile if hasattr(user, 'userprofile') else None,
            'total_hours_rendered': round(total_hours_rendered, 2),
            'required_hours': required_hours,
            'remaining_hours': round(remaining_hours, 2),
            'percentage': round(percentage, 1),
            'recent_records': recent_records,
        })
    
    context = {
        'users_data': users_data,
        'page_obj': page_obj,
        'search_query': search_query,
        'is_paginated': page_obj.has_other_pages(),
        'office_name': user_office,
        'total_office_users': office_users.count(),
    }
    
    return render(request, 'office_head/student_assistants.html', context)

@login_required(login_url='login')
def monthly_dtr(request):
    """Display monthly DTR for user before submission"""
    from calendar import monthrange
    from datetime import datetime as dt
    
    # Get month and year from request or use current
    month_year = request.GET.get('month_year', '')
    if month_year:
        # Parse the format YYYY-MM
        try:
            year, month = map(int, month_year.split('-'))
        except (ValueError, AttributeError):
            month = dt.now().month
            year = dt.now().year
    else:
        month = int(request.GET.get('month', dt.now().month))
        year = int(request.GET.get('year', dt.now().year))
    
    # Get all time records for the selected month
    time_records = TimeRecord.objects.filter(
        user=request.user,
        timestamp__month=month,
        timestamp__year=year
    ).order_by('timestamp')
    
    # Group records by date and pair time in/out
    daily_records = {}
    for record in time_records:
        date_key = timezone.localtime(record.timestamp).date()
        if date_key not in daily_records:
            daily_records[date_key] = {'in_times': [], 'out_times': [], 'duration': 0}
        
        if record.record_type == 'in':
            daily_records[date_key]['in_times'].append(timezone.localtime(record.timestamp))
        else:
            daily_records[date_key]['out_times'].append(timezone.localtime(record.timestamp))
            if record.duration:
                hours = record.duration.total_seconds() / 3600
                daily_records[date_key]['duration'] += round(hours, 2)  # Accumulate duration
    
    # Process daily records to get first in and last out
    for date_key, record in daily_records.items():
        record['in'] = min(record['in_times']) if record['in_times'] else None
        record['out'] = max(record['out_times']) if record['out_times'] else None
    
    # Calculate total hours
    total_hours = sum(
        daily['duration'] for daily in daily_records.values() 
        if daily['duration'] > 0
    )
    total_hours = round(total_hours, 2) if total_hours else 0
    
    # Sort by date
    sorted_records = sorted(daily_records.items())
    
    # Calculate cumulative hours
    cumulative_hours = 0
    for date, record in sorted_records:
        if record['duration'] > 0:
            cumulative_hours += record['duration']
            record['cumulative_duration'] = round(cumulative_hours, 2)
            record['cumulative_duration_formatted'] = format_hours_minutes(round(cumulative_hours, 2))
        else:
            record['cumulative_duration'] = round(cumulative_hours, 2)  # Keep the same if no hours on this day
            record['cumulative_duration_formatted'] = format_hours_minutes(round(cumulative_hours, 2))
    
    # Check if DTR for this month is already submitted
    try:
        dtr_submission = DTRSubmission.objects.get(user=request.user, month=month, year=year)
    except DTRSubmission.DoesNotExist:
        dtr_submission = None
    
    context = {
        'month': month,
        'year': year,
        'month_name': dt(year, month, 1).strftime('%B'),
        'daily_records': sorted_records,
        'total_hours': total_hours,
        'total_hours_formatted': format_hours_minutes(total_hours),
        'dtr_submission': dtr_submission,
        'can_submit': not dtr_submission,  # Can only submit if not already submitted
    }
    
    return render(request, 'core/monthly_dtr.html', context)

def format_hours_minutes(decimal_hours):
    """Convert decimal hours to hours and minutes format (e.g., 8.5 -> '8h 30m')"""
    if decimal_hours is None or decimal_hours == 0:
        return "0h 0m"
    
    hours = int(decimal_hours)
    minutes = int((decimal_hours - hours) * 60)
    return f"{hours}h {minutes}m"

@login_required(login_url='login')
@require_http_methods(["POST"])
def submit_dtr(request):
    """Submit monthly DTR"""
    from datetime import datetime as dt
    
    month = int(request.POST.get('month'))
    year = int(request.POST.get('year'))
    
    # Calculate total hours for the month
    time_records = TimeRecord.objects.filter(
        user=request.user,
        timestamp__month=month,
        timestamp__year=year,
        record_type='out',
        duration__isnull=False
    ).aggregate(total=models.Sum('duration'))['total']
    
    total_hours = 0
    if time_records:
        total_seconds = time_records.total_seconds()
        total_hours = round(total_seconds / 3600, 2)
    
    # Create or update DTR submission
    try:
        dtr_submission = DTRSubmission.objects.get(user=request.user, month=month, year=year)
        messages.error(request, "This DTR has already been submitted.")
    except DTRSubmission.DoesNotExist:
        dtr_submission = DTRSubmission.objects.create(
            user=request.user,
            month=month,
            year=year,
            status='pending',
            total_hours=total_hours
        )
        messages.success(request, f"DTR for {dt(year, month, 1).strftime('%B %Y')} submitted successfully!")
    
    return redirect('monthly_dtr')

@user_passes_test(lambda u: u.is_staff or u.is_superuser, login_url='login')
def dtr_approvals(request):
    """View to approve/reject DTR submissions"""
    from django.core.paginator import Paginator
    
    # Get filter status from request
    default_status = ''  # Show all for both staff and superusers
    status_filter = request.GET.get('status', default_status).strip()
    search_query = request.GET.get('search', '').strip()
    
    # Get DTR submissions
    dtr_submissions = DTRSubmission.objects.select_related('user', 'approver').all()
    
    # Filter by office for office heads only (not for superusers)
    # Superusers see all DTR submissions regardless of office
    if request.user.is_staff and not request.user.is_superuser:
        # This is an office head, filter to their office only
        try:
            user_office = request.user.userprofile.office
            dtr_submissions = dtr_submissions.filter(user__userprofile__office=user_office)
        except (UserProfile.DoesNotExist, AttributeError):
            dtr_submissions = dtr_submissions.none()
    
    # Apply status filter
    if status_filter in ['pending', 'approved', 'rejected']:
        dtr_submissions = dtr_submissions.filter(status=status_filter)
    
    # Apply search filter
    if search_query:
        dtr_submissions = dtr_submissions.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(user__userprofile__office__icontains=search_query)
        )
    
    dtr_submissions = dtr_submissions.order_by('-year', '-month', '-submitted_date')
    
    # Pagination
    paginator = Paginator(dtr_submissions, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'dtr_submissions': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
    }
    
    return render(request, 'office_head/dtr-approvals.html', context)

@user_passes_test(lambda u: u.is_staff, login_url='login')
@require_http_methods(["POST"])
def approve_dtr(request, dtr_id):
    """Approve a DTR submission"""
    try:
        dtr_submission = DTRSubmission.objects.get(id=dtr_id)

        if not user_in_same_office(request.user, dtr_submission.user):
            messages.error(request, "You are not authorized to approve that DTR.")
            return redirect('dtr_approvals')

        remarks = request.POST.get('remarks', '')
        
        dtr_submission.status = 'approved'
        dtr_submission.approver = request.user
        dtr_submission.approved_date = timezone.now()
        dtr_submission.remarks = remarks
        dtr_submission.save()
        
        # Notify all superusers about the approval
        superusers = User.objects.filter(is_superuser=True)
        for superuser in superusers:
            ChatMessage.objects.create(
                sender=request.user,
                recipient=superuser,
                message=f"DTR for {dtr_submission.user.get_full_name() or dtr_submission.user.username} ({dtr_submission.month}/{dtr_submission.year}) has been approved."
            )
        
        messages.success(request, f"DTR for {dtr_submission.user.username} ({dtr_submission.month}/{dtr_submission.year}) approved successfully!")
    except DTRSubmission.DoesNotExist:
        messages.error(request, "DTR submission not found.")
    except Exception as e:
        messages.error(request, f"Error approving DTR: {str(e)}")
    
    return redirect('dtr_approvals')

@user_passes_test(lambda u: u.is_staff, login_url='login')
@require_http_methods(["POST"])
def reject_dtr(request, dtr_id):
    """Reject a DTR submission"""
    try:
        dtr_submission = DTRSubmission.objects.get(id=dtr_id)

        if not user_in_same_office(request.user, dtr_submission.user):
            messages.error(request, "You are not authorized to reject that DTR.")
            return redirect('dtr_approvals')

        remarks = request.POST.get('remarks', 'No reason provided')
        
        dtr_submission.status = 'rejected'
        dtr_submission.approver = request.user
        dtr_submission.approved_date = timezone.now()
        dtr_submission.remarks = remarks
        dtr_submission.save()
        
        messages.success(request, f"DTR for {dtr_submission.user.username} ({dtr_submission.month}/{dtr_submission.year}) rejected. Reason: {remarks}")
    except DTRSubmission.DoesNotExist:
        messages.error(request, "DTR submission not found.")
    except Exception as e:
        messages.error(request, f"Error rejecting DTR: {str(e)}")
    
    return redirect('dtr_approvals')

@login_required
@user_passes_test(lambda u: u.is_staff, login_url='login')
def time_correction(request, dtr_id):
    """
    Handles path('time-correction/<int:dtr_id>/', name='time_correction')
    Matches the file: templates/office_head/time-correction.html
    """
    template_name = 'office_head/time-correction.html' 
    dtr_submission = get_object_or_404(DTRSubmission, id=dtr_id)

    if request.user.is_staff and not request.user.is_superuser:
        if not user_in_same_office(request.user, dtr_submission.user):
            messages.error(request, "You are not authorized to access that student's DTR records.")
            return redirect('office_dashboard')
    
    # Fetch records for the specific month/year of the DTR
    time_records = TimeRecord.objects.filter(
        user=dtr_submission.user,
        timestamp__month=dtr_submission.month,
        timestamp__year=dtr_submission.year
    ).order_by('timestamp')
    
    # Grouping logic for the daily UI rows
    grouped_data = {}
    for record in time_records:
        date_key = timezone.localtime(record.timestamp).date()
        if date_key not in grouped_data:
            grouped_data[date_key] = []
        grouped_data[date_key].append(record)

    daily_records = sorted(grouped_data.items(), key=lambda x: x[0], reverse=True)

    context = {
        'dtr_submission': dtr_submission,
        'daily_records': daily_records,
        'student_name': dtr_submission.user.get_full_name()
    }
    return render(request, template_name, context)

@login_required
@user_passes_test(lambda u: u.is_staff, login_url='login')
@require_http_methods(["POST"])
def update_time_record(request, record_id):
    """
    Handles path('time-correction/update/<int:record_id>/', name='update_time_record')
    Called by the modal in time-correction.html
    """
    record = get_object_or_404(TimeRecord, id=record_id)
    dtr_id = request.POST.get('dtr_id') # Passed via hidden input in your modal

    if request.user.is_staff and not request.user.is_superuser:
        if not user_in_same_office(request.user, record.user):
            messages.error(request, "You are not authorized to edit this time record.")
            return redirect('office_dashboard')
    
    try:
        timestamp_str = request.POST.get('timestamp')
        if timestamp_str:
            # HTML5 datetime-local uses 'T' separator (e.g., 2026-04-28T14:30)
            new_dt = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M')
            record.timestamp = timezone.make_aware(new_dt)
            record.save()
            
            # Auto-recalculate duration for the shift
            if record.record_type == 'out':
                prev_in = TimeRecord.objects.filter(
                    user=record.user, record_type='in', timestamp__lt=record.timestamp
                ).order_by('-timestamp').first()
                if prev_in:
                    record.duration = record.timestamp - prev_in.timestamp
                    record.save()
            else:
                next_out = TimeRecord.objects.filter(
                    user=record.user, record_type='out', timestamp__gt=record.timestamp
                ).order_by('timestamp').first()
                if next_out:
                    next_out.duration = next_out.timestamp - record.timestamp
                    next_out.save()

            messages.success(request, "Record updated and shift duration recalculated.")
    except Exception as e:
        messages.error(request, f"Update failed: {str(e)}")
        
    return redirect('time_correction', dtr_id=dtr_id)

@login_required
@user_passes_test(lambda u: u.is_staff, login_url='login')
@require_http_methods(["POST"])
def add_time_record(request):
    """Handles path('time-correction/add/', name='add_time_record')"""
    dtr_id = request.POST.get('dtr_id')
    dtr = get_object_or_404(DTRSubmission, id=dtr_id)

    if request.user.is_staff and not request.user.is_superuser:
        if not user_in_same_office(request.user, dtr.user):
            messages.error(request, "You are not authorized to add a time record for this student.")
            return redirect('office_dashboard')
    
    try:
        ts_str = request.POST.get('timestamp')
        r_type = request.POST.get('record_type')
        
        new_dt = datetime.strptime(ts_str, '%Y-%m-%dT%H:%M')
        new_record = TimeRecord.objects.create(
            user=dtr.user,
            timestamp=timezone.make_aware(new_dt),
            record_type=r_type,
            qr_code="MANUAL_CORRECTION"
        )
        
        # Calculate duration if it's an OUT record
        if r_type == 'out':
            prev_in = TimeRecord.objects.filter(
                user=dtr.user, record_type='in', timestamp__lt=new_record.timestamp
            ).order_by('-timestamp').first()
            if prev_in:
                new_record.duration = new_record.timestamp - prev_in.timestamp
                new_record.save()
                
        messages.success(request, "Manual record added.")
    except Exception as e:
        messages.error(request, f"Add failed: {str(e)}")
        
    return redirect('time_correction', dtr_id=dtr_id)

@login_required
@user_passes_test(lambda u: u.is_staff, login_url='login')
def delete_time_record(request, record_id):
    """Handles path('time-correction/delete/<int:record_id>/', name='delete_time_record')"""
    record = get_object_or_404(TimeRecord, id=record_id)
    dtr_id = request.POST.get('dtr_id')

    if request.user.is_staff and not request.user.is_superuser:
        if not user_in_same_office(request.user, record.user):
            messages.error(request, "You are not authorized to delete this time record.")
            return redirect('office_dashboard')

    record.delete()
    messages.success(request, "Log entry removed.")
    return redirect('time_correction', dtr_id=dtr_id)

@user_passes_test(lambda u: u.is_superuser, login_url='login')
def debug_dtr_submissions(request):
    """Temporary debug view to list all DTR submissions"""
    submissions = DTRSubmission.objects.select_related('user', 'user__userprofile', 'approver').order_by('-submitted_date')[:50]
    
    context = {
        'submissions': submissions,
    }
    
    return render(request, 'caao_admin/debug_dtr.html', context)

@user_passes_test(lambda u: u.is_staff, login_url='login')
def time_correction_list(request):
    """List all students for time correction"""
    students = User.objects.filter(is_staff=False, is_superuser=False)
    if request.user.is_staff and not request.user.is_superuser:
        office = get_user_office(request.user)
        students = students.filter(userprofile__office=office)
    students = students.order_by('first_name', 'last_name')
    
    context = {
        'students': students,
    }
    
    return render(request, 'caao_admin/time_correction_list.html', context)

@user_passes_test(lambda u: u.is_staff, login_url='login')
def time_correction_user(request, user_id):
    """Show DTR submissions for a specific user"""
    try:
        user = User.objects.get(id=user_id, is_staff=False, is_superuser=False)
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect('time_correction_list')

    if request.user.is_staff and not request.user.is_superuser:
        if not user_in_same_office(request.user, user):
            messages.error(request, "You are not authorized to view that student's DTR submissions.")
            return redirect('time_correction_list')
    
    # Get all DTR submissions for this user
    dtr_submissions = DTRSubmission.objects.filter(user=user).order_by('-year', '-month')
    
    context = {
        'selected_user': user,
        'dtr_submissions': dtr_submissions,
        'is_superuser': request.user.is_superuser,  # Flag for read-only mode
    }
    
    return render(request, 'caao_admin/time_correction.html', context)

@login_required(login_url='login')
def chat(request):
    """Main chat view"""
    # Get all users for the user list (excluding current user)
    users = User.objects.exclude(id=request.user.id).order_by('username')
    
    # Get recent messages (global messages only for initial load)
    recent_messages = ChatMessage.objects.filter(
        Q(recipient__isnull=True)  # Global messages
    ).order_by('-timestamp')[:50]  # Last 50 messages
    
    context = {
        'users': users,
        'recent_messages': recent_messages[::-1],  # Reverse to show oldest first
    }
    
    return render(request, 'core/chat.html', context)

@login_required(login_url='login')
@require_http_methods(["POST"])
def send_message(request):
    """Send a chat message"""
    try:
        message_text = request.POST.get('message', '').strip()
        recipient_id = request.POST.get('recipient_id')
        
        if not message_text:
            return JsonResponse({'success': False, 'error': 'Message cannot be empty'})
        
        recipient = None
        if recipient_id:
            try:
                recipient = User.objects.get(id=recipient_id)
            except User.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Recipient not found'})
        
        # Create the message
        chat_message = ChatMessage.objects.create(
            sender=request.user,
            recipient=recipient,
            message=message_text
        )
        
        return JsonResponse({
            'success': True,
            'message_id': chat_message.id,
            'timestamp': chat_message.timestamp.strftime('%H:%M'),
            'sender': chat_message.sender.username,
            'recipient': chat_message.recipient.username if chat_message.recipient else None
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required(login_url='login')
def get_messages(request):
    """Get new messages via AJAX"""
    last_message_id = request.GET.get('last_id', 0)
    recipient_id = request.GET.get('recipient_id')
    
    if recipient_id:
        # Private chat with this user
        try:
            recipient = User.objects.get(id=recipient_id)
            new_messages = ChatMessage.objects.filter(
                (Q(sender=request.user, recipient=recipient) | Q(sender=recipient, recipient=request.user))
            ).filter(id__gt=last_message_id).order_by('timestamp')
        except User.DoesNotExist:
            return JsonResponse({'messages': []})
    else:
        # Global chat
        new_messages = ChatMessage.objects.filter(
            Q(recipient__isnull=True)
        ).filter(id__gt=last_message_id).order_by('timestamp')
    
    messages_data = []
    for msg in new_messages:
        messages_data.append({
            'id': msg.id,
            'sender': msg.sender.username,
            'sender_id': msg.sender.id,
            'recipient': msg.recipient.username if msg.recipient else None,
            'recipient_id': msg.recipient.id if msg.recipient else None,
            'message': msg.message,
            'timestamp': msg.timestamp.strftime('%H:%M'),
            'is_own': msg.sender == request.user
        })
    
    return JsonResponse({'messages': messages_data})

@login_required(login_url='login')
def mark_messages_read(request, user_id):
    """Mark messages from a specific user as read"""
    try:
        # Mark messages from the specified user to current user as read
        ChatMessage.objects.filter(
            sender_id=user_id,
            recipient=request.user,
            is_read=False
        ).update(is_read=True)
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
