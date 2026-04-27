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