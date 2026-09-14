from django import template
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType


register = template.Library()


@register.simple_tag
def has_admin_history(obj):
    if obj is None or obj.pk is None:
        return False
    content_type = ContentType.objects.get_for_model(obj, for_concrete_model=False)
    return LogEntry.objects.filter(content_type=content_type, object_id=str(obj.pk)).exists()
