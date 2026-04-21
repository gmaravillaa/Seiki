from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
from .models import TimeRecord, UserProfile, DTRSubmission, ChatMessage
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import models
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from datetime import date, datetime
from django.db import models

def format_hours_minutes(decimal_hours):
    """Convert decimal hours to hours and minutes format (e.g., 8.5 -> '8h 30m')"""
    if decimal_hours is None or decimal_hours == 0:
        return "0h 0m"
    
    hours = int(decimal_hours)
    minutes = int((decimal_hours - hours) * 60)
    return f"{hours}h {minutes}m"

def index(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            auth_login(request, user)
            return redirect('dashboard')  # Redirect to dashboard after successful login
        else:
            # Display error message on login page
            return render(request, 'index.html', {'error': 'Invalid credentials'})

    return render(request, 'index.html')

@login_required(login_url='login')
def notification(request):
    return render(request, 'notification.html')

@login_required(login_url='login')
def profile(request):
    # Calculate total hours rendered
    total_duration = TimeRecord.objects.filter(
        user=request.user,
        record_type='out',
        duration__isnull=False
    ).aggregate(total=models.Sum('duration'))['total']
    
    # Convert duration to hours (duration is in seconds)
    total_hours_rendered = 0
    if total_duration:
        total_seconds = total_duration.total_seconds()
        total_hours_rendered = total_seconds / 3600  # Convert to hours
    
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
    
    return render(request, 'profile.html', context)

@login_required(login_url='login')
def dashboard(request):
    """Dashboard/home page for students/users"""
    from datetime import date, datetime
    from django.utils import timezone
    
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
    
    return render(request, 'dashboard.html', context)

@login_required(login_url='login')
def qr(request):
    return render(request, 'qr.html')

@login_required(login_url='login')
def scanner(request):
    if not request.user.is_staff:
        return redirect('profile')
    return render(request, 'scanner.html')

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
    
    return render(request, 'logs.html', {'logs_data': logs_data})

@login_required(login_url='login')
@require_http_methods(["POST"])
def record_time(request):
    """Record time when QR code is scanned"""
    try:
        print(f"Record time called by user: {request.user}")
        print(f"Request body: {request.body}")
        
        data = json.loads(request.body)
        qr_code = data.get('qr_code')
        
        if not qr_code:
            return JsonResponse({'success': False, 'error': 'QR code data required'}, status=400)
        
        # Parse QR code to get user ID (format: "user_id:username")
        try:
            user_id_str, username = qr_code.split(':', 1)
            user_id = int(user_id_str)
        except (ValueError, IndexError):
            return JsonResponse({'success': False, 'error': 'Invalid QR code format'}, status=400)
        
        # Get the user whose QR code was scanned
        try:
            target_user = User.objects.get(id=user_id, username=username)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
        
        # Get today's date
        today = date.today()
        
        # Get the last time record for today for the target user
        last_record = TimeRecord.objects.filter(
            user=target_user,
            timestamp__date=today
        ).order_by('-timestamp').first()
        
        # Determine record type: if last was 'in', make this 'out', else 'in'
        if last_record and last_record.record_type == 'in':
            record_type = 'out'
            message_text = 'Time out'
        else:
            record_type = 'in'
            message_text = 'Time in'
        
        # Create time record
        time_record = TimeRecord.objects.create(
            user=target_user,
            qr_code=qr_code,
            record_type=record_type
        )
        
        # If this is a time out, calculate and store the duration
        if record_type == 'out':
            # Find the last time in record for today
            time_in_record = TimeRecord.objects.filter(
                user=target_user,
                timestamp__date=today,
                record_type='in'
            ).order_by('-timestamp').first()
            
            if time_in_record:
                # Calculate duration between time in and time out
                duration = time_record.timestamp - time_in_record.timestamp
                time_record.duration = duration
                time_record.save()
        
        print(f"Time record created: {time_record}")
        
        return JsonResponse({
            'success': True,
            'message': f'{message_text} recorded for {target_user.username} at {timezone.localtime(time_record.timestamp).strftime("%H:%M:%S")}',
            'timestamp': time_record.timestamp.isoformat(),
            'record_type': record_type
        })
        
    except json.JSONDecodeError as e:
        print(f"JSON Error: {e}")
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

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
            return render(request, 'user_management.html', {'users': users})
        
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
            
            # Update or create user profile with the provided data
            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    'office': office,
                    'id_number': id_number,
                    'required_hours': required_hours
                }
            )
            
            messages.success(request, f'User {user.username} created successfully!')
            
        except Exception as e:
            messages.error(request, f'Error creating user: {str(e)}')
    
    # Get all users with their profiles
    users = User.objects.all().select_related('userprofile').order_by('username')
    return render(request, 'user_management.html', {'users': users})

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
def user_progress(request):
    """User progress page for superusers to view detailed user information and work progress"""
    from django.core.paginator import Paginator
    
    # Get search query
    search_query = request.GET.get('search', '').strip()
    
    # Get all users with their profiles
    users = User.objects.all().select_related('userprofile')
    
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
    }
    
    return render(request, 'user_progress.html', context)

@login_required(login_url='login')
@user_passes_test(lambda u: u.is_staff and not u.is_superuser)
def office_users(request):
    """Office users page for office heads to view users in their office"""
    from django.core.paginator import Paginator
    
    # Get current user's office
    try:
        user_office = request.user.userprofile.office
        if not user_office:
            messages.error(request, "Your office information is not set. Please contact an administrator.")
            return redirect('profile')
    except UserProfile.DoesNotExist:
        messages.error(request, "Your profile information is not complete. Please contact an administrator.")
        return redirect('profile')
    
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
    
    return render(request, 'office_users.html', context)

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
    
    return render(request, 'monthly_dtr.html', context)

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

@user_passes_test(lambda u: u.is_superuser)
def dtr_approvals(request):
    """Superuser view to approve/reject DTR submissions"""
    from django.core.paginator import Paginator
    
    # Get filter status from request
    status_filter = request.GET.get('status', 'pending')
    search_query = request.GET.get('search', '').strip()
    
    # Get all DTR submissions
    dtr_submissions = DTRSubmission.objects.select_related('user', 'approver').all()
    
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
    
    return render(request, 'dtr_approvals.html', context)

@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["POST"])
def approve_dtr(request, dtr_id):
    """Approve a DTR submission"""
    try:
        dtr_submission = DTRSubmission.objects.get(id=dtr_id)
        remarks = request.POST.get('remarks', '')
        
        dtr_submission.status = 'approved'
        dtr_submission.approver = request.user
        dtr_submission.approved_date = timezone.now()
        dtr_submission.remarks = remarks
        dtr_submission.save()
        
        messages.success(request, f"DTR for {dtr_submission.user.username} ({dtr_submission.month}/{dtr_submission.year}) approved successfully!")
    except DTRSubmission.DoesNotExist:
        messages.error(request, "DTR submission not found.")
    except Exception as e:
        messages.error(request, f"Error approving DTR: {str(e)}")
    
    return redirect('dtr_approvals')

@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["POST"])
def reject_dtr(request, dtr_id):
    """Reject a DTR submission"""
    try:
        dtr_submission = DTRSubmission.objects.get(id=dtr_id)
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

@user_passes_test(lambda u: u.is_superuser)
def time_correction(request, dtr_id):
    """Superuser view to edit time logs for a DTR submission"""
    try:
        dtr_submission = DTRSubmission.objects.get(id=dtr_id)
    except DTRSubmission.DoesNotExist:
        messages.error(request, "DTR submission not found.")
        return redirect('dtr_approvals')
    
    # Get all time records for the month
    time_records = TimeRecord.objects.filter(
        user=dtr_submission.user,
        timestamp__month=dtr_submission.month,
        timestamp__year=dtr_submission.year
    ).order_by('timestamp')
    
    # Group records by date for display
    daily_records = {}
    for record in time_records:
        date_key = timezone.localtime(record.timestamp).date()
        if date_key not in daily_records:
            daily_records[date_key] = []
        daily_records[date_key].append(record)
    
    # Sort by date
    sorted_records = sorted(daily_records.items())
    
    context = {
        'dtr_submission': dtr_submission,
        'daily_records': sorted_records,
    }
    
    return render(request, 'time_correction.html', context)

@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["POST"])
def update_time_record(request, record_id):
    """Update a specific time record"""
    try:
        time_record = TimeRecord.objects.get(id=record_id)
        
        # Get the updated timestamp
        new_timestamp_str = request.POST.get('timestamp')
        if new_timestamp_str:
            # Parse the timestamp (format: YYYY-MM-DDTHH:MM)
            new_timestamp = datetime.strptime(new_timestamp_str, '%Y-%m-%dT%H:%M')
            # Make it timezone aware
            new_timestamp = timezone.make_aware(new_timestamp)
            time_record.timestamp = new_timestamp
            time_record.save()
            
            # If this is a time out record, recalculate duration
            if time_record.record_type == 'out':
                # Find the last time in record for the same day
                same_day = time_record.timestamp.date()
                time_in_record = TimeRecord.objects.filter(
                    user=time_record.user,
                    timestamp__date=same_day,
                    record_type='in',
                    timestamp__lt=time_record.timestamp
                ).order_by('-timestamp').first()
                
                if time_in_record:
                    duration = time_record.timestamp - time_in_record.timestamp
                    time_record.duration = duration
                    time_record.save()
        
        messages.success(request, f"Time record updated successfully!")
    except TimeRecord.DoesNotExist:
        messages.error(request, "Time record not found.")
    except Exception as e:
        messages.error(request, f"Error updating time record: {str(e)}")
    
    return redirect('time_correction', dtr_id=request.POST.get('dtr_id'))

@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["POST"])
def delete_time_record(request, record_id):
    """Delete a specific time record"""
    try:
        time_record = TimeRecord.objects.get(id=record_id)
        dtr_id = request.POST.get('dtr_id')
        time_record.delete()
        messages.success(request, f"Time record deleted successfully!")
    except TimeRecord.DoesNotExist:
        messages.error(request, "Time record not found.")
    except Exception as e:
        messages.error(request, f"Error deleting time record: {str(e)}")
    
    return redirect('time_correction', dtr_id=dtr_id)

@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["POST"])
def add_time_record(request):
    """Add a new time record"""
    try:
        dtr_id = request.POST.get('dtr_id')
        dtr_submission = DTRSubmission.objects.get(id=dtr_id)
        
        timestamp_str = request.POST.get('timestamp')
        record_type = request.POST.get('record_type')
        qr_code = request.POST.get('qr_code', f"admin_{dtr_submission.user.username}")
        
        if timestamp_str and record_type:
            # Parse the timestamp
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M')
            timestamp = timezone.make_aware(timestamp)
            
            # Create the time record
            time_record = TimeRecord.objects.create(
                user=dtr_submission.user,
                qr_code=qr_code,
                timestamp=timestamp,
                record_type=record_type
            )
            
            # If this is a time out, calculate duration
            if record_type == 'out':
                same_day = timestamp.date()
                time_in_record = TimeRecord.objects.filter(
                    user=dtr_submission.user,
                    timestamp__date=same_day,
                    record_type='in',
                    timestamp__lt=timestamp
                ).order_by('-timestamp').first()
                
                if time_in_record:
                    duration = timestamp - time_in_record.timestamp
                    time_record.duration = duration
                    time_record.save()
            
            messages.success(request, f"Time record added successfully!")
        else:
            messages.error(request, "Please provide timestamp and record type.")
            
    except Exception as e:
        messages.error(request, f"Error adding time record: {str(e)}")
    
    return redirect('time_correction', dtr_id=dtr_id)

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
    
    return render(request, 'chat.html', context)

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


