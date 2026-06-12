import uuid
from django.db import models
from core.models import Domain
from core.validators import validate_multi_email


class Voicemail(models.Model):
    GREETING_CHOICES = [
        ('auto_with_instructions', 'Automatic with Instructions'),
        ('tts_name', 'Text-to-Speech Greeting'),
        ('recorded_name', 'Recorded Name Greeting'),
        ('media_file', 'Media File Greeting'),
    ]
    ON_NEW_MESSAGE_CHOICES = [
        ('nothing', 'Nothing special'),
        ('email', 'Send email'),
        ('both', 'Send email and keep message'),
    ]

    voicemail_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(
        Domain,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='domain_uuid',
        related_name='voicemails',
    )

    # ── Identity ─────────────────────────────────────────────────────────
    voicemail_id = models.CharField(max_length=32)
    voicemail_password = models.CharField(max_length=32, blank=True, default='', verbose_name='PIN')
    voicemail_name = models.CharField(max_length=128, blank=True, default='', verbose_name='Name')
    voicemail_mail_to = models.CharField(
        max_length=512, blank=True, default='', verbose_name='Email',
        validators=[validate_multi_email],
        help_text='One or more email addresses, separated by commas.')
    voicemail_pager = models.EmailField(blank=True, default='', verbose_name='Pager email')
    timezone = models.CharField(max_length=64, blank=True, default='', help_text='Leave blank to use tenant default.')
    voicemail_language = models.CharField(max_length=16, blank=True, default='', verbose_name='Language',
                                          help_text='Leave blank to use tenant default.')
    voicemail_enabled = models.BooleanField(default=True)

    # ── Playback settings ─────────────────────────────────────────────────
    voicemail_envelope = models.BooleanField(default=True, verbose_name='Envelope playback',
                                             help_text='Play date/time before each message.')
    voicemail_say_caller_id = models.BooleanField(default=False, verbose_name='Say caller ID')
    voicemail_greeting = models.CharField(max_length=32, blank=True, default='auto_with_instructions',
                                          choices=GREETING_CHOICES, verbose_name='Greeting style')
    tts_greeting_text = models.CharField(max_length=512, blank=True, default='', verbose_name='TTS greeting text',
                                         help_text='Custom text for TTS greeting. Leave blank for default.')
    # When voicemail_greeting == 'media_file', play this Media File (Recording) as the greeting.
    voicemail_greeting_recording = models.ForeignKey(
        'recordings.Recording',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='greeting_recording_uuid',
        related_name='+',
        verbose_name='Greeting media file',
    )
    voicemail_play_after = models.BooleanField(default=False, verbose_name='Play a message after the other')

    # ── Message handling ──────────────────────────────────────────────────
    voicemail_file = models.CharField(max_length=32, default='attach',
        choices=[('attach', 'Attach'), ('link', 'Link'), ('none', 'None')],
        verbose_name='Attach message to email')
    voicemail_local_after_email = models.BooleanField(default=True, verbose_name='Store message locally after email')
    voicemail_transcription_enabled = models.BooleanField(default=True, verbose_name='Generate transcript')
    voicemail_store_transcript = models.BooleanField(default=True, verbose_name='Store transcript')
    voicemail_auto_delete = models.BooleanField(default=False, verbose_name='Automatic delete')
    voicemail_delete_older_messages = models.BooleanField(default=False, verbose_name='Delete older messages')
    voicemail_sms_to = models.CharField(max_length=32, blank=True, default='', verbose_name='SMS notification number')
    voicemail_on_new_message = models.CharField(max_length=32, default='nothing',
                                                choices=ON_NEW_MESSAGE_CHOICES, verbose_name='On new message')

    # ── Capacity ──────────────────────────────────────────────────────────
    voicemail_max_messages = models.IntegerField(default=100, verbose_name='Max number of messages')
    voicemail_min_len = models.IntegerField(default=0, verbose_name='Min message length (seconds)')
    voicemail_max_len = models.IntegerField(default=3600, verbose_name='Max message length (seconds)')
    voicemail_backup = models.BooleanField(default=False, verbose_name='Backup messages')

    # ── Features ──────────────────────────────────────────────────────────
    voicemail_allow_review = models.BooleanField(default=False, verbose_name='Allow review before sending')
    voicemail_allow_callback = models.BooleanField(default=False, verbose_name='Allow callback')
    voicemail_allow_dialout = models.BooleanField(default=False, verbose_name='Allow dial-out')
    voicemail_dial_by_name = models.BooleanField(default=False, verbose_name='Include in Dial-by-Name directory')

    # ── Operator / IVR ────────────────────────────────────────────────────
    voicemail_allow_operator = models.BooleanField(default=False, verbose_name='Allow operator/extras during greeting')
    voicemail_operator_destination = models.CharField(max_length=64, blank=True, default='', verbose_name='Operator destination')
    voicemail_ivr_destination = models.CharField(max_length=64, blank=True, default='', verbose_name='Voicemail IVR destination')

    # ── Integrations ──────────────────────────────────────────────────────
    post_voicemail_url = models.CharField(max_length=512, blank=True, default='', verbose_name='Post voicemail webhook URL',
                                          help_text='Called after a new voicemail is received. Use %%TENANTID%% as placeholder.')

    # ── Audit ─────────────────────────────────────────────────────────────
    voicemail_description = models.TextField(blank=True, default='')
    insert_date = models.DateTimeField(auto_now_add=True, null=True)
    insert_user = models.UUIDField(null=True, blank=True)
    update_date = models.DateTimeField(auto_now=True, null=True)
    update_user = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_voicemails'
        unique_together = [('tenant', 'voicemail_id')]

    def __str__(self):
        return f'{self.voicemail_id}@{self.domain}'


class VoicemailMessage(models.Model):
    """
    Maps to FreeSWITCH's native voicemail_msgs table.
    FreeSWITCH writes directly to this table when odbc-dsn is configured.
    Audio files are still stored on disk; this table holds metadata only.
    """
    uuid = models.CharField(max_length=255, primary_key=True)
    created_epoch = models.IntegerField(default=0)
    read_epoch = models.IntegerField(default=0)
    username = models.CharField(max_length=255, blank=True, default='')    # mailbox id
    domain = models.CharField(max_length=255, blank=True, default='')     # SIP domain name
    cid_name = models.CharField(max_length=255, blank=True, default='')
    cid_number = models.CharField(max_length=255, blank=True, default='')
    in_folder = models.CharField(max_length=255, blank=True, default='')  # e.g. 'inbox'
    file_path = models.CharField(max_length=512, blank=True, default='')  # path to audio file on disk
    message_len = models.IntegerField(default=0)                          # seconds
    flags = models.CharField(max_length=255, blank=True, default='')
    read_flags = models.CharField(max_length=255, blank=True, default='') # '' = unread, 'read' = read
    forwarded_by = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'voicemail_msgs'
        ordering = ['-created_epoch']

    def __str__(self):
        return f'{self.username}@{self.domain} from {self.cid_number}'


class VoicemailReadState(models.Model):
    """
    Tracks read/unread state for voicemail messages in PostgreSQL.
    Used because the FreeSWITCH SQLite file is not writable by Django.
    reader='admin' → admin panel read state; reader='client' → client API read state.
    """
    READER_ADMIN = 'admin'
    READER_CLIENT = 'client'

    message_uuid = models.CharField(max_length=255)
    reader = models.CharField(max_length=20, default='admin')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voicemail_read_state'
        unique_together = [('message_uuid', 'reader')]


class VoicemailPrefs(models.Model):
    """
    Maps to FreeSWITCH's native voicemail_prefs table.
    Stores per-mailbox greeting/name recording paths and password.
    FreeSWITCH reads/writes this directly.
    """
    username = models.CharField(max_length=255)
    domain = models.CharField(max_length=255)
    name_path = models.CharField(max_length=255, blank=True, default='')
    greeting_path = models.CharField(max_length=255, blank=True, default='')
    password = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'voicemail_prefs'
        unique_together = [('username', 'domain')]

    def __str__(self):
        return f'{self.username}@{self.domain}'


class VoicemailTranscript(models.Model):
    """
    Stores Deepgram transcription results for voicemail messages.
    Linked by message_uuid to VoicemailMessage (which lives in SQLite).
    """
    STATUS_PENDING = 'pending'
    STATUS_DONE = 'done'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_DONE, 'Done'),
        (STATUS_FAILED, 'Failed'),
    ]

    message_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    transcript = models.TextField(blank=True, default='')
    confidence = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=16, default=STATUS_PENDING, choices=STATUS_CHOICES)
    error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voicemail_transcripts'

    def __str__(self):
        return f'Transcript for {self.message_uuid} ({self.status})'


class VoicemailDestination(models.Model):
    voicemail_destination_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, db_column='domain_uuid')
    voicemail = models.ForeignKey(Voicemail, on_delete=models.CASCADE,
                                  db_column='voicemail_uuid', related_name='destinations')
    voicemail_destination_uuid2 = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = 'v_voicemail_destinations'


class VoicemailOption(models.Model):
    voicemail_option_uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='tenant_uuid',
        related_name='%(app_label)s_%(class)s_set',
    )
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, null=True, db_column='domain_uuid')
    voicemail = models.ForeignKey(Voicemail, on_delete=models.CASCADE,
                                  db_column='voicemail_uuid', related_name='options')
    voicemail_option_digits = models.CharField(max_length=8, blank=True, default='')
    voicemail_option_action = models.CharField(max_length=256, blank=True, default='')
    voicemail_option_param = models.CharField(max_length=256, blank=True, default='')
    voicemail_option_order = models.IntegerField(default=10)

    class Meta:
        db_table = 'v_voicemail_options'
        ordering = ['voicemail_option_order']
