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


# All models in the xml_cdr app live in the separate 'cdr' database.
CDR_APP_LABEL = 'xml_cdr'
CDR_DB = 'cdr'


class CdrRouter:
    """
    Route the xml_cdr app (call detail records) to the separate 'cdr' database.
    Everything else falls through to 'default'.

    The XmlCdr model still declares FK fields to core.Tenant/Domain (kept from
    before the split for transition/backfill), but the read path uses the
    denormalized tenant_uuid_val/tenant_code/domain_name columns and never joins
    across the boundary. allow_relation returns True so Django doesn't object to
    assigning those FKs in code (e.g. ingest), even though no cross-DB JOIN is
    ever issued.
    """

    def db_for_read(self, model, **hints):
        if model._meta.app_label == CDR_APP_LABEL:
            return CDR_DB
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label == CDR_APP_LABEL:
            return CDR_DB
        return None

    def allow_relation(self, obj1, obj2, **hints):
        # Permit relations involving a CDR object (the FK is code-only; no JOIN
        # crosses databases at the SQL layer).
        labels = {obj1._meta.app_label, obj2._meta.app_label}
        if CDR_APP_LABEL in labels:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == CDR_APP_LABEL:
            return db == CDR_DB      # xml_cdr tables ONLY in the cdr DB
        if db == CDR_DB:
            return False             # nothing else goes into the cdr DB
        return None
