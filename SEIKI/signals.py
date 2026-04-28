from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import UserProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # For staff users (office heads), create profile with empty office by default
        # The office must be set via admin or user management interface
        UserProfile.objects.get_or_create(user=instance, defaults={'office': '', 'required_hours': 0})

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'userprofile'):
        instance.userprofile.save()

@receiver(pre_save, sender=User)
def validate_staff_user_has_office(sender, instance, **kwargs):
    """
    Validation to ensure staff users (office heads) have an office assigned.
    This runs before User is saved to check if is_staff is being set to True.
    """
    if instance.is_staff and not instance.is_superuser:
        # Check if user already has a profile with office
        try:
            if instance.pk:
                existing_profile = UserProfile.objects.filter(user=instance).first()
                if existing_profile and not existing_profile.office:
                    # Log warning - staff user without office
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f"Staff user '{instance.username}' (ID: {instance.pk}) does not have an office assigned. "
                        f"Office heads must have an office to access their dashboard properly."
                    )
        except Exception:
            pass  # Don't block save if check fails