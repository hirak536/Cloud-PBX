"""
Background SIP-pcap slicing for CDRs.

At call end the CDR ingest enqueues slice_call_pcap for each leg that has a SIP
Call-ID. The task slices that leg's dialog out of the rolling capture ONCE into a
small per-call file, so the SIP/PCAP viewer later reads a ~20KB file instead of
re-scanning hundreds of MB on every tab open (which took ~8-17s).

Doing it in Celery (not inline in ingest) keeps FreeSWITCH's CDR POST fast.
"""
import os
import logging

from celery import shared_task

logger = logging.getLogger(__name__)

# Per-call sliced pcaps live here (separate from the rolling capture files so a
# capture-dir cleanup of the big files doesn't take the per-call ones with it).
SLICED_DIR = os.environ.get('SIP_SLICED_DIR', '/var/spool/sip/calls')

# Stored in sip_pcap_path when a slice attempt found no packets (almost always a
# scanner call we don't capture). Distinguishes "tried, nothing there" from ''
# ("not yet tried") so the sweep skips it instead of retrying every minute.
NO_CAPTURE_SENTINEL = 'none'

# Safety cap on the per-call pcap we store in the DB. SIP-only slices are a few KB
# normally; this guards against a pathological call (huge retransmit storm) from
# bloating a row. Above this we keep the file on disk and store only the path.
MAX_DB_PCAP_BYTES = int(os.environ.get('SIP_MAX_DB_PCAP_BYTES', str(2 * 1024 * 1024)))  # 2 MB


@shared_task(
    bind=True,
    # A few retries with backoff: capture writes are now packet-buffered (-U) so
    # packets land on disk almost immediately, but a call that ends right as the
    # sweep runs may still have its final messages (BYE/200) arriving. Retrying a
    # few times over ~1.5 min reliably catches them without much waste.
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def slice_call_pcap(self, xml_cdr_uuid):
    from .models import XmlCdr  # noqa: PLC0415
    from . import sip_capture as sc  # noqa: PLC0415

    try:
        leg = XmlCdr.objects.get(pk=xml_cdr_uuid)
    except XmlCdr.DoesNotExist:
        return  # row gone (dedup) — nothing to do

    if not leg.sip_call_id:
        return
    if leg.sip_pcap_data:
        return  # already sliced & stored in the DB

    import tempfile  # noqa: PLC0415
    with tempfile.NamedTemporaryFile(suffix='.pcap', delete=False) as tmp:
        tmp_path = tmp.name
    try:
        sliced = sc.slice_leg_pcap(
            leg.sip_call_id, leg.start_stamp, leg.end_stamp, tmp_path,
        )
    except sc.CaptureUnavailable as e:
        logger.info('slice_call_pcap: capture toolchain unavailable: %s', e)
        _safe_unlink(tmp_path)
        return

    if not sliced:
        _safe_unlink(tmp_path)
        # Retry a few times — packets for a just-ended call may still be arriving.
        try:
            raise self.retry()
        except self.MaxRetriesExceededError:
            pass
        # Retries exhausted. Only mark NO_CAPTURE permanently once the call is old
        # enough that packets will never appear (past the capture window). For a
        # still-recent call, leave it pending so the next sweep retries — this is
        # what prevents a call whose packets land slightly late from being
        # permanently stuck as "no captured packets".
        from django.utils import timezone  # noqa: PLC0415
        from datetime import timedelta  # noqa: PLC0415
        age_min = (timezone.now() - leg.start_stamp).total_seconds() / 60 if leg.start_stamp else 999
        if age_min >= SWEEP_LOOKBACK_MINUTES:
            XmlCdr.objects.filter(pk=leg.xml_cdr_uuid).update(sip_pcap_path=NO_CAPTURE_SENTINEL)
            logger.info('slice_call_pcap: no packets for %s (call_id=%s), age=%.0fm — marked',
                        leg.xml_cdr_uuid, leg.sip_call_id, age_min)
        else:
            logger.info('slice_call_pcap: no packets yet for %s (age=%.0fm) — leaving pending',
                        leg.xml_cdr_uuid, age_min)
        return

    size = os.path.getsize(sliced)
    if size <= MAX_DB_PCAP_BYTES:
        # Store the packets IN the row (the normal case — SIP slices are tiny).
        with open(sliced, 'rb') as fh:
            data = fh.read()
        XmlCdr.objects.filter(pk=leg.xml_cdr_uuid).update(
            sip_pcap_data=data, sip_pcap_path='',
        )
        _safe_unlink(tmp_path)
        logger.info('slice_call_pcap: stored %d bytes in DB for %s', size, leg.xml_cdr_uuid)
    else:
        # Pathologically large — keep it on disk and store only the path so the
        # row doesn't bloat. Rare.
        try:
            os.makedirs(SLICED_DIR, exist_ok=True)
            final = os.path.join(SLICED_DIR, f'{leg.xml_cdr_uuid}.pcap')
            os.replace(sliced, final)
            XmlCdr.objects.filter(pk=leg.xml_cdr_uuid).update(sip_pcap_path=final)
            logger.info('slice_call_pcap: %d bytes > cap, kept on disk for %s', size, leg.xml_cdr_uuid)
        except OSError as e:
            logger.warning('slice_call_pcap: oversize slice store failed: %s', e)
            _safe_unlink(tmp_path)


def _safe_unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass


# How far back the sweep looks for un-sliced calls. The rolling capture only
# holds the recent past anyway, so there's no point scanning older rows — they
# have no packets on disk to slice.
SWEEP_LOOKBACK_MINUTES = int(os.environ.get('SIP_SLICE_LOOKBACK_MINUTES', '30'))
SWEEP_BATCH = int(os.environ.get('SIP_SLICE_BATCH', '200'))


@shared_task
def sweep_unsliced_pcaps():
    """Periodic sweep (Celery Beat): pre-slice recently-ended calls that have a
    SIP Call-ID but no sliced pcap yet.

    This runs ENTIRELY off the CDR ingest path — ingest never enqueues or slices —
    so it cannot slow down how fast new CDRs appear. Calls get their per-leg pcap a
    minute or two after they end, which is well before anyone opens the SIP tab.
    """
    from django.utils import timezone  # noqa: PLC0415
    from datetime import timedelta  # noqa: PLC0415
    from .models import XmlCdr  # noqa: PLC0415

    since = timezone.now() - timedelta(minutes=SWEEP_LOOKBACK_MINUTES)
    # Only slice calls whose traffic we actually capture: real tenant calls
    # (tenant_code set). The capture filter intentionally excludes internet
    # scanner traffic, so scanner CDRs have a Call-ID but no packets on disk —
    # enqueuing them just burns worker time retrying for packets that aren't there.
    # Pending = tenant call, has a Call-ID, not yet stored in DB (sip_pcap_data
    # null) and not already marked no-capture (sip_pcap_path != sentinel) and not
    # kept-on-disk (sip_pcap_path == '').
    pending = (
        XmlCdr.objects
        .filter(sip_call_id__gt='', sip_pcap_data__isnull=True, sip_pcap_path='',
                start_stamp__gte=since, tenant_code__gt='')
        .values_list('xml_cdr_uuid', flat=True)[:SWEEP_BATCH]
    )
    n = 0
    for uuid in pending:
        slice_call_pcap.delay(str(uuid))
        n += 1
    if n:
        logger.info('sweep_unsliced_pcaps: enqueued %d slice task(s)', n)
    return n
