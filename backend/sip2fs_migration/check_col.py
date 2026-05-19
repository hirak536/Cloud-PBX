import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.dev'
django.setup()
from django.db import connection
with connection.cursor() as c:
    c.execute("SELECT column_name, data_type, column_default, is_nullable FROM information_schema.columns WHERE table_name='v_extensions' AND column_name LIKE '%mobile%'")
    for row in c.fetchall():
        print(row)
