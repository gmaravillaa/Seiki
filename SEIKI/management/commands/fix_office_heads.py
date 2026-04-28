"""
Management command to audit and fix office head users with missing office assignments.

Usage:
    python manage.py fix_office_heads [--fix]

Without --fix: Only reports issues
With --fix: Attempts to fix issues by setting a placeholder office
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from SEIKI.models import UserProfile


class Command(BaseCommand):
    help = 'Audit and fix office head users with missing office assignments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Actually fix the issues (without this, only reports)',
        )

    def handle(self, *args, **options):
        fix_mode = options['fix']
        
        # Find all staff users who are not superusers (office heads)
        office_heads = User.objects.filter(is_staff=True, is_superuser=False)
        
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Found {office_heads.count()} office head users"
        ))
        
        issues_found = 0
        issues_fixed = 0
        
        for user in office_heads:
            issues = []
            
            # Check if user has a profile
            try:
                profile = user.userprofile
            except UserProfile.DoesNotExist:
                issues.append("Missing UserProfile")
                if fix_mode:
                    profile = UserProfile.objects.create(
                        user=user,
                        office='',
                        required_hours=0
                    )
                    issues_fixed += 1
                    self.stdout.write(f"  Created UserProfile for {user.username}")
                else:
                    profile = None
            
            # Check if office is set
            if profile and not profile.office:
                issues.append("Missing office assignment")
                if fix_mode:
                    # Don't auto-fix office - require manual assignment
                    self.stdout.write(self.style.WARNING(
                        f"  User {user.username} needs manual office assignment"
                    ))
            
            # Check other required fields
            if profile and not user.first_name:
                issues.append("Missing first name")
            if profile and not user.last_name:
                issues.append("Missing last name")
            
            if issues:
                issues_found += 1
                self.stdout.write(self.style.ERROR(
                    f"\nUser: {user.username} (ID: {user.id})"
                ))
                for issue in issues:
                    self.stdout.write(f"  - {issue}")
        
        self.stdout.write("\n" + "=" * 50)
        if issues_found == 0:
            self.stdout.write(self.style.SUCCESS(
                "\nNo issues found! All office heads have proper assignments."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"\nFound {issues_found} users with issues"
            ))
            if fix_mode:
                self.stdout.write(self.style.SUCCESS(
                    f"Fixed {issues_fixed} issues"
                ))
                self.stdout.write(self.style.NOTICE(
                    "\nNote: Users without offices still need manual assignment.\n"
                    "Go to Django admin or user management to assign offices."
                ))
            else:
                self.stdout.write(self.style.NOTICE(
                    "\nRun with --fix to create missing profiles (offices require manual assignment)"
                ))
