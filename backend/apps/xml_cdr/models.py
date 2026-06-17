import uuid
from django.db import models
from core.models import Domain


class XmlCdr(models.Model):
    xml_cdr_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # FKs to core.* with db_constraint=False: CDRs live in a separate database
    # (the 'cdr' DB) so a real DB-level FK can't span to v_tenants/v_domains in
    # the main DB. The relation is kept at the ORM layer only — for transition and
    # for the rare ingest dereference — and emits NO constraint, so the schema is
    # self-contained in the cdr DB. The read path uses the denormalized columns
    # below and never dereferences these.
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        db_constraint=False,
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.DO_NOTHING, null=True, blank=True,
                               db_column='domain_uuid', db_constraint=False,
                               related_name='cdr_records')
    # ── Denormalized tenant/domain (Phase 1 of CDR-DB separation) ───────────────
    # The `tenant`/`domain` FKs above join to core.* tables. When CDRs move to a
    # separate database those joins can't span DBs, so we carry the identifying
    # values directly on the row. These are the read path everywhere now
    # (serializers + tenant scoping); the FKs remain only for backfill/transition.
    # NOTE: the `tenant` FK already uses db_column='tenant_uuid'; this denormalized
    # copy uses a distinct column name to avoid colliding with it.
    tenant_uuid_val = models.UUIDField(null=True, blank=True, db_index=True, db_column='tenant_uuid_denorm')
    tenant_code = models.CharField(max_length=32, blank=True, default='', db_index=True)
    domain_uuid_val = models.UUIDField(null=True, blank=True, db_column='domain_uuid_denorm')
    domain_name = models.CharField(max_length=128, blank=True, default='')
    caller_id_name = models.CharField(max_length=128, blank=True, default='')
    caller_id_number = models.CharField(max_length=32, blank=True, default='', db_index=True)
    extension_number = models.CharField(max_length=32, blank=True, default='')  # SIP username of the extension involved
    caller_destination = models.CharField(max_length=32, blank=True, default='')
    destination_number = models.CharField(max_length=32, blank=True, default='', db_index=True)
    context = models.CharField(max_length=128, blank=True, default='')
    start_epoch = models.BigIntegerField(default=0)
    start_stamp = models.DateTimeField(null=True, blank=True, db_index=True)
    answer_epoch = models.BigIntegerField(default=0)
    answer_stamp = models.DateTimeField(null=True, blank=True)
    end_epoch = models.BigIntegerField(default=0)
    end_stamp = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(default=0, db_index=True)
    mduration = models.IntegerField(default=0)
    billsec = models.IntegerField(default=0, db_index=True)
    billmsec = models.IntegerField(default=0)
    call_uuid = models.UUIDField(null=True, blank=True, db_index=True)  # FreeSWITCH channel UUID
    bridge_uuid = models.UUIDField(null=True, blank=True, db_index=True)
    # SIP Call-ID header for this leg. Used to slice this leg's SIP packets out of
    # the rolling tcpdump capture for the per-leg PCAP/SIP-ladder viewer. One SIP
    # dialog (INVITE branch) == one Call-ID == one leg row.
    sip_call_id = models.CharField(max_length=256, blank=True, default='', db_index=True)
    # Path to the pre-sliced per-leg pcap file (legacy/fallback). Superseded by
    # sip_pcap_data below; kept for the sentinel value 'none' = "tried, no packets".
    sip_pcap_path = models.CharField(max_length=512, blank=True, default='')
    # The pre-sliced per-leg SIP pcap stored IN the row (bytea). SIP-only slices
    # are tiny (a few KB), so this keeps packets with the CDR — they travel with
    # DB backups and need no disk files. The SIP/PCAP viewer decodes straight from
    # here, so reads don't depend on the rolling capture or disk at all.
    sip_pcap_data = models.BinaryField(null=True, blank=True, editable=False)
    read_codec = models.CharField(max_length=32, blank=True, default='')
    read_rate = models.CharField(max_length=8, blank=True, default='')
    write_codec = models.CharField(max_length=32, blank=True, default='')
    write_rate = models.CharField(max_length=8, blank=True, default='')
    remote_media_ip = models.CharField(max_length=64, blank=True, default='')
    network_addr = models.CharField(max_length=64, blank=True, default='')
    record_path = models.CharField(max_length=512, blank=True, default='')
    record_name = models.CharField(max_length=256, blank=True, default='')
    leg = models.CharField(max_length=8, default='a', choices=[('a','A-leg'),('b','B-leg')])
    pdd_ms = models.IntegerField(default=0)
    last_app = models.CharField(max_length=64, blank=True, default='')
    last_arg = models.CharField(max_length=1024, blank=True, default='')
    cc_queue = models.CharField(max_length=256, blank=True, default='')
    cc_agent = models.CharField(max_length=256, blank=True, default='')
    waitsec = models.IntegerField(default=0)
    conference_name = models.CharField(max_length=256, blank=True, default='')
    hangup_cause = models.CharField(max_length=64, blank=True, default='', db_index=True)
    hangup_cause_q850 = models.IntegerField(default=0)
    direction = models.CharField(max_length=16, default='inbound',
        choices=[('inbound','Inbound'),('outbound','Outbound'),('local','Local')])
    missed_call = models.BooleanField(default=False)
    bypass_media = models.BooleanField(default=False)
    insert_date = models.DateTimeField(auto_now_add=True, null=True, db_index=True)

    class Meta:
        db_table = 'v_xml_cdr'
        ordering = ['-start_stamp']
        constraints = [
            models.UniqueConstraint(
                fields=['call_uuid', 'leg'],
                condition=models.Q(call_uuid__isnull=False),
                name='unique_call_uuid_leg',
            ),
        ]
        indexes = [
            models.Index(fields=['start_stamp']),
            models.Index(fields=['caller_id_number']),
            models.Index(fields=['destination_number']),
            models.Index(fields=['hangup_cause']),
            models.Index(fields=['tenant', 'start_stamp']),
            models.Index(fields=['tenant', 'caller_id_number']),
            models.Index(fields=['direction', 'start_stamp']),
            models.Index(fields=['missed_call', 'start_stamp']),
        ]

    def __str__(self):
        return f'{self.caller_id_number} -> {self.destination_number} ({self.billsec}s)'
