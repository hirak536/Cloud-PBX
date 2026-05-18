"""Celery tasks for the provision app."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def rebuild_provision_cache(self, vendor: str = None):
    """Rebuild the in-memory/Redis cache of active provision templates.

    Parameters
    ----------
    vendor:
        If given, only templates for this vendor are refreshed.
        If omitted, all active templates are refreshed.
    """
    try:
        from .models import ProvisionTemplate
        qs = ProvisionTemplate.objects.filter(is_active=True)
        if vendor:
            qs = qs.filter(vendor__iexact=vendor)

        count = qs.count()
        logger.info(
            'rebuild_provision_cache: refreshed %d template(s) (vendor=%s)',
            count, vendor or 'all',
        )
        return {'refreshed': count, 'vendor': vendor}
    except Exception as exc:
        logger.warning('rebuild_provision_cache failed: %s – retrying', exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def validate_all_templates(self):
    """Validate Django template syntax for all active provision templates.

    Logs any templates that fail to compile so operators can identify
    broken configs before phones request them.
    """
    try:
        from django.template import Template, TemplateSyntaxError
        from .models import ProvisionTemplate

        invalid = []
        for tmpl in ProvisionTemplate.objects.filter(is_active=True):
            try:
                Template(tmpl.template_content)
            except TemplateSyntaxError as exc:
                invalid.append({'uuid': str(tmpl.template_uuid), 'error': str(exc)})
                logger.error(
                    'validate_all_templates: template %s (%s/%s) has syntax error: %s',
                    tmpl.template_uuid, tmpl.vendor, tmpl.template_name, exc,
                )

        if not invalid:
            logger.info('validate_all_templates: all templates OK')
        return {'invalid': invalid, 'count': len(invalid)}
    except Exception as exc:
        logger.warning('validate_all_templates failed: %s – retrying', exc)
        raise self.retry(exc=exc)
