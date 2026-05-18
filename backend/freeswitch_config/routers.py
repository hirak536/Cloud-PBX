VOICEMAIL_SQLITE_MODELS = {'voicemailmessage', 'voicemailprefs'}


class VoicemailSQLiteRouter:
    """
    Route VoicemailMessage and VoicemailPrefs reads/writes to the FreeSWITCH
    SQLite database (voicemail_default.db). Everything else uses 'default'.
    """

    def db_for_read(self, model, **hints):
        if model._meta.model_name in VOICEMAIL_SQLITE_MODELS:
            return 'voicemail_sqlite'
        return None

    def db_for_write(self, model, **hints):
        if model._meta.model_name in VOICEMAIL_SQLITE_MODELS:
            return 'voicemail_sqlite'
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if model_name in VOICEMAIL_SQLITE_MODELS:
            return False  # Never migrate these — FreeSWITCH owns the schema
        return None
