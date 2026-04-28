from django import template
from calendar import month_name

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key"""
    return dictionary.get(key, '')

@register.filter
def get_month_name(month_num):
    """Convert month number to month name"""
    try:
        return month_name[int(month_num)]
    except (ValueError, IndexError):
        return str(month_num)

@register.filter
def format_duration(duration):
    """Format a timedelta duration as HH:MM:SS"""
    if not duration:
        return "-"
    
    total_seconds = int(duration.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"