"""Models for the ESL app.

PeerStateHistory tracks SIP peer state transitions over time so the operator
panel can render a state-over-time graph. Rows are written by the periodic
``poll_peer_states`` task whenever a peer changes state.
"""
from django.db import models


class PeerStateHistory(models.Model):
    STATE_OFFLINE = 'offline'
    STATE_AVAILABLE = 'available'
    STATE_RINGING = 'ringing'
    STATE_INUSE = 'inuse'
    STATE_RINGINUSE = 'ringinuse'
    STATE_UNKNOWN = 'unknown'
    STATE_CHOICES = [
        (STATE_OFFLINE, 'Offline'),
        (STATE_AVAILABLE, 'Available'),
        (STATE_RINGING, 'Ringing'),
        (STATE_INUSE, 'In use'),
        (STATE_RINGINUSE, 'Ring in use'),
        (STATE_UNKNOWN, 'Unknown'),
    ]

    extension = models.CharField(max_length=64, db_index=True)
    tenant_code = models.CharField(max_length=64, blank=True, default='', db_index=True)
    state = models.CharField(max_length=16, choices=STATE_CHOICES)
    started_at = models.DateTimeField(db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = 'esl_peer_state_history'
        indexes = [
            models.Index(fields=['extension', 'started_at']),
            models.Index(fields=['extension', 'ended_at']),
        ]
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.extension} {self.state} @ {self.started_at}'
