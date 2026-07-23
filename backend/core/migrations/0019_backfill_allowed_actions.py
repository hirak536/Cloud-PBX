from django.db import migrations


# Pages opted into action-level control. Only these get backfilled; other pages
# in allowed_pages remain page-level only. Must match the frontend action catalog
# and core.permissions._PAGE_PERMISSION_PREFIXES.
ACTION_PAGES = {
    'extensions',
    'ring-groups',
    'ivr-menus',
    'call-flows',
    'destinations',
    'voicemails',
    'call-centers',
    'conferences',
    'working-hours',
}
ALL_ACTIONS = ['view', 'add', 'edit', 'delete']


def backfill(apps, schema_editor):
    """Grant full actions on every action-controlled page a user already has.

    Preserves existing behavior: before this feature a granted page implied full
    CRUD, so existing users keep all four actions on the pages they hold.
    """
    User = apps.get_model('core', 'User')
    for user in User.objects.all().iterator():
        pages = user.allowed_pages or []
        actions = dict(user.allowed_actions or {})
        changed = False
        for page in pages:
            if page in ACTION_PAGES and page not in actions:
                actions[page] = list(ALL_ACTIONS)
                changed = True
        if changed:
            user.allowed_actions = actions
            user.save(update_fields=['allowed_actions'])


def noop_reverse(apps, schema_editor):
    # Non-destructive: leave allowed_actions in place on reverse.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_user_allowed_actions'),
    ]

    operations = [
        migrations.RunPython(backfill, noop_reverse),
    ]
