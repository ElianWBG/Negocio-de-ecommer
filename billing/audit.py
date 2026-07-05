from billing.models import AuditLog


def log_action(request, action, model_name, object_id=None, description=''):
    """Record an audit event. Never raises — a logging failure must not break the request."""
    try:
        ip = (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR')
        ) or None
        AuditLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            action=action,
            model_name=model_name,
            object_id=object_id,
            description=description,
            ip_address=ip,
        )
    except Exception:
        pass
