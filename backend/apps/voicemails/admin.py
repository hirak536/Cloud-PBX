from django.contrib import admin, messages
from django.utils.html import format_html
from .models import Voicemail, VoicemailMessage, VoicemailPrefs, VoicemailDestination, VoicemailOption, VoicemailTranscript


class VoicemailOptionInline(admin.TabularInline):
    model = VoicemailOption
    extra = 1


@admin.register(Voicemail)
class VoicemailAdmin(admin.ModelAdmin):
    list_display = ['voicemail_id', 'voicemail_name', 'tenant', 'voicemail_mail_to', 'voicemail_enabled']
    list_filter = ['voicemail_enabled', 'tenant']
    search_fields = ['voicemail_id', 'voicemail_name', 'voicemail_mail_to']
    readonly_fields = ['insert_date', 'update_date']
    inlines = [VoicemailOptionInline]
    fieldsets = [
        ('Identity', {
            'fields': [
                'tenant', 'domain',
                'voicemail_id', 'voicemail_password', 'voicemail_name',
                'voicemail_mail_to', 'voicemail_pager',
                'timezone', 'voicemail_language',
                'voicemail_enabled',
            ],
        }),
        ('Playback', {
            'fields': [
                'voicemail_envelope', 'voicemail_say_caller_id',
                'voicemail_greeting', 'voicemail_play_after',
            ],
        }),
        ('Message Handling', {
            'fields': [
                'voicemail_file', 'voicemail_local_after_email',
                'voicemail_transcription_enabled', 'voicemail_store_transcript',
                'voicemail_auto_delete', 'voicemail_delete_older_messages',
                'voicemail_sms_to', 'voicemail_on_new_message',
            ],
        }),
        ('Capacity', {
            'fields': [
                'voicemail_max_messages', 'voicemail_min_len', 'voicemail_max_len',
                'voicemail_backup',
            ],
        }),
        ('Features', {
            'fields': [
                'voicemail_allow_review', 'voicemail_allow_callback',
                'voicemail_allow_dialout', 'voicemail_dial_by_name',
            ],
        }),
        ('Operator / IVR', {
            'classes': ['collapse'],
            'fields': [
                'voicemail_allow_operator', 'voicemail_operator_destination',
                'voicemail_ivr_destination',
            ],
        }),
        ('Integrations', {
            'classes': ['collapse'],
            'fields': ['post_voicemail_url'],
        }),
        ('Audit', {
            'classes': ['collapse'],
            'fields': [
                'voicemail_description',
                'insert_date', 'insert_user',
                'update_date', 'update_user',
            ],
        }),
    ]


@admin.register(VoicemailMessage)
class VoicemailMessageAdmin(admin.ModelAdmin):
    list_display = ['username', 'domain', 'cid_number', 'cid_name', 'read_flags', 'message_len', 'created_epoch']
    list_filter = ['domain', 'read_flags', 'in_folder']
    search_fields = ['username', 'cid_number', 'cid_name']
    readonly_fields = ['uuid', 'created_epoch', 'read_epoch', 'file_path']


@admin.register(VoicemailPrefs)
class VoicemailPrefsAdmin(admin.ModelAdmin):
    list_display = ['username', 'domain', 'greeting_path', 'name_path']
    search_fields = ['username', 'domain']


def _retry_transcription(transcript_obj):
    """Queue a fresh transcription attempt for a single VoicemailTranscript."""
    from apps.voicemails.tasks import transcribe_voicemail_google  # noqa: PLC0415

    # Look up the original message to recover ingest args
    msg = VoicemailMessage.objects.filter(uuid=transcript_obj.message_uuid).first()
    if msg is None:
        return False, 'VoicemailMessage not found'

    # Reset status so the task saves correctly
    transcript_obj.status = VoicemailTranscript.STATUS_PENDING
    transcript_obj.error = ''
    transcript_obj.save(update_fields=['status', 'error', 'updated_at'])

    transcribe_voicemail_google.apply_async(
        args=[
            msg.uuid,
            msg.file_path,
            msg.username,   # voicemail UUID (stored as username after the isolation fix)
            msg.domain,
            msg.cid_name,
            msg.cid_number,
            msg.message_len,
            msg.created_epoch,
        ],
        countdown=5,
    )
    return True, ''


@admin.action(description='Retry transcription for selected messages')
def retry_transcription(modeladmin, request, queryset):
    ok = failed = 0
    for obj in queryset:
        success, err = _retry_transcription(obj)
        if success:
            ok += 1
        else:
            failed += 1
            modeladmin.message_user(
                request,
                f'Could not retry {obj.message_uuid}: {err}',
                level=messages.WARNING,
            )
    if ok:
        modeladmin.message_user(request, f'Queued {ok} transcription(s) for retry.', level=messages.SUCCESS)


@admin.register(VoicemailTranscript)
class VoicemailTranscriptAdmin(admin.ModelAdmin):
    list_display = [
        'message_uuid', 'status_badge', 'confidence_pct',
        'transcript_preview', 'created_at', 'updated_at',
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['message_uuid', 'transcript', 'error']
    readonly_fields = ['message_uuid', 'created_at', 'updated_at', 'status', 'confidence', 'transcript', 'error']
    ordering = ['-created_at']
    actions = [retry_transcription]

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            VoicemailTranscript.STATUS_DONE: 'green',
            VoicemailTranscript.STATUS_FAILED: 'red',
            VoicemailTranscript.STATUS_PENDING: 'orange',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color, obj.status.upper(),
        )

    @admin.display(description='Confidence')
    def confidence_pct(self, obj):
        if obj.confidence is None:
            return '-'
        return f'{obj.confidence * 100:.0f}%'

    @admin.display(description='Transcript')
    def transcript_preview(self, obj):
        if not obj.transcript:
            return obj.error[:80] if obj.error else '-'
        return obj.transcript[:80] + ('…' if len(obj.transcript) > 80 else '')
