"""
Install a Postgres trigger that mirrors outbound-call rows into the
v_caller_extension_affinity table.

Why a DB trigger: FreeSWITCH writes CDR rows directly into v_xml_cdr via
mod_xml_cdr / mod_cdr_pg_csv. Those INSERTs bypass Django's ORM, so the
post_save signal in apps.custom_destinations.signals never fires for them.
A trigger catches every INSERT regardless of source.

Behaviour mirrors apps.custom_destinations.affinity.upsert_affinity:
  - only on direction='outbound' with a real extension_number and tenant
  - normalize destination_number to last 10 digits (US)
  - upsert (tenant, caller_number); only overwrite if start_stamp is newer
"""
from django.db import migrations


FORWARD_SQL = r"""
CREATE OR REPLACE FUNCTION custom_destinations_xmlcdr_affinity_upsert()
RETURNS TRIGGER
LANGUAGE plpgsql AS $$
DECLARE
    customer_raw  text;
    customer_norm text;
    digits        text;
    when_ts       timestamptz;
BEGIN
    -- Track affinity from any CDR where a real extension actually talked to a
    -- customer for some non-zero duration. Two cases produce a usable row:
    --   - Live FreeSWITCH A-leg of an inbound call: direction='inbound',
    --     caller_id_number is the customer, extension_number is the answering ext.
    --   - Django-imported outbound migration: direction='outbound',
    --     destination_number is the customer, extension_number is the dialer.
    -- Both express "ext X is the agent for customer Y".
    IF NEW.tenant_uuid IS NULL
       OR NEW.extension_number IS NULL OR NEW.extension_number = ''
       OR (NEW.last_app IS NOT NULL AND lower(NEW.last_app) = 'voicemail')
    THEN
        RETURN NEW;
    END IF;

    IF NEW.direction = 'outbound' THEN
        customer_raw := NEW.destination_number;
    ELSIF NEW.direction = 'inbound' THEN
        customer_raw := NEW.caller_id_number;
    ELSE
        RETURN NEW;
    END IF;

    IF customer_raw IS NULL OR customer_raw = '' THEN
        RETURN NEW;
    END IF;

    -- Normalize: strip non-digits, drop leading 1, last 10
    digits := regexp_replace(customer_raw, '\D', '', 'g');
    IF length(digits) > 10 AND left(digits, 1) = '1' THEN
        digits := substring(digits from 2);
    END IF;
    IF length(digits) >= 10 THEN
        customer_norm := right(digits, 10);
    ELSE
        customer_norm := digits;
    END IF;
    IF customer_norm = '' THEN
        RETURN NEW;
    END IF;

    when_ts := COALESCE(NEW.start_stamp, NEW.insert_date, now());

    INSERT INTO v_caller_extension_affinity
        (affinity_uuid, tenant_uuid, domain_uuid, caller_number,
         extension_number, last_seen, source, insert_date, update_date)
    VALUES
        (gen_random_uuid(), NEW.tenant_uuid, NEW.domain_uuid, customer_norm,
         NEW.extension_number, when_ts, 'cdr', now(), now())
    ON CONFLICT ON CONSTRAINT uniq_affinity_tenant_caller DO UPDATE SET
        extension_number = EXCLUDED.extension_number,
        last_seen        = EXCLUDED.last_seen,
        source           = 'cdr',
        update_date      = now(),
        domain_uuid      = COALESCE(v_caller_extension_affinity.domain_uuid, EXCLUDED.domain_uuid)
      WHERE EXCLUDED.last_seen > v_caller_extension_affinity.last_seen;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_xmlcdr_affinity_upsert ON v_xml_cdr;
CREATE TRIGGER trg_xmlcdr_affinity_upsert
    AFTER INSERT ON v_xml_cdr
    FOR EACH ROW
    EXECUTE FUNCTION custom_destinations_xmlcdr_affinity_upsert();
"""

REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS trg_xmlcdr_affinity_upsert ON v_xml_cdr;
DROP FUNCTION IF EXISTS custom_destinations_xmlcdr_affinity_upsert();
"""


class Migration(migrations.Migration):

    dependencies = [
        ('custom_destinations', '0009_relax_legacy_columns'),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]
