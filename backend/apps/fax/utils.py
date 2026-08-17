import os
import subprocess
import shutil
import logging

logger = logging.getLogger(__name__)

def pdf_to_tiff(pdf_path: str) -> str:
    """
    Convert a PDF to a fax-compatible TIFF (G3, 204x196 dpi) using ghostscript.
    Returns the path to the new .tif file. Raises RuntimeError on failure.
    """
    tif_path = os.path.splitext(pdf_path)[0] + '.tif'
    cmd = [
        'gs', '-q', '-dNOPAUSE', '-dBATCH', '-dSAFER',
        '-sDEVICE=tiffg3',
        '-r204x196',
        '-dFIXEDMEDIA', '-dPAPERWIDTH=1728', '-dPAPERHEIGHT=2156',
        f'-sOutputFile={tif_path}',
        pdf_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not os.path.isfile(tif_path):
        raise RuntimeError(f'PDF to TIFF conversion failed: {result.stderr.strip()}')
    return tif_path


def is_fax_ready_tiff(tif_path: str) -> bool:
    """
    True if the TIFF is already a valid TIFF/F that txfax can transmit.

    txfax/spandsp requires bi-level (1 bit/sample) CCITT G3 or G4 data; anything
    else is rejected at send time with "result (41) TIFF/F file cannot be opened"
    AFTER the call has already connected. A TIFF exported from a scanner, phone
    or image editor is typically 8-bit RGB(A) at 72 dpi and fails this check.

    Only bits-per-sample and compression are enforced — those are what spandsp
    hard-rejects. Resolution/width are normalised on re-encode but a compliant
    G3/G4 file at an unusual size is still transmittable, so it passes.
    """
    if not shutil.which('tiffinfo'):
        # Can't inspect — assume non-compliant so the file gets normalised.
        # Sending an unreadable TIFF fails the call; a needless re-encode is cheap.
        logger.warning('is_fax_ready_tiff: tiffinfo unavailable, assuming %s needs conversion', tif_path)
        return False

    result = subprocess.run(['tiffinfo', tif_path], capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning('is_fax_ready_tiff: tiffinfo failed on %s: %s', tif_path, result.stderr.strip())
        return False

    info = result.stdout
    bits_ok = 'Bits/Sample: 1' in info
    compression_ok = 'CCITT Group 3' in info or 'CCITT Group 4' in info
    return bits_ok and compression_ok


def normalize_tiff_for_fax(tif_path: str) -> str:
    """
    Re-encode an arbitrary TIFF into a fax-compatible TIFF/F (1-bit G3, 204x196).
    Returns the path to a normalised .tif. Raises RuntimeError on failure.

    Uses ImageMagick, NOT ghostscript: gs cannot read TIFF input at all (it
    fails with "/undefined in II*"), so pdf_to_tiff's approach does not apply
    here. tiffcp alone is also insufficient — it refuses non-1-bit input with
    "Fax3SetupState: Bits/sample must be 1", which is the same underlying
    complaint spandsp makes. The threshold to 1-bit must happen first.

    Note: this ImageMagick build names the codec 'Fax', not 'Group3'.
    """
    normalized_path = os.path.splitext(tif_path)[0] + '_faxready.tif'

    convert_bin = shutil.which('convert') or shutil.which('magick')
    if not convert_bin:
        raise RuntimeError('TIFF normalisation requires ImageMagick (convert/magick), not found')

    cmd = [
        convert_bin, tif_path,
        '-colorspace', 'Gray',
        '-resize', '1728x',          # standard fax scanline width; height scales
        '-threshold', '50%',         # must precede -compress Fax: G3 needs 1 bit/sample
        '-density', '204x196',
        '-units', 'PixelsPerInch',
        '-compress', 'Fax',
        normalized_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not os.path.isfile(normalized_path):
        raise RuntimeError(f'TIFF normalisation failed: {result.stderr.strip()}')
    return normalized_path


def sniff_file_type(file_path: str) -> str:
    """
    Identify a fax upload by its magic bytes: 'pdf', 'tiff' or 'unknown'.

    The extension is not trustworthy — browsers and EHR exports routinely hand
    us a PDF named .tiff. Routing such a file to the TIFF path fails obscurely:
    ImageMagick's PDF policy blocks the read and raises "not allowed by the
    security policy", which surfaced as a 500 rather than a usable message.
    """
    try:
        with open(file_path, 'rb') as fh:
            head = fh.read(4)
    except OSError:
        return 'unknown'

    if head[:4] == b'%PDF':
        return 'pdf'
    # II* (little-endian) / MM\0* (big-endian) TIFF byte-order marks.
    if head[:4] in (b'II\x2a\x00', b'MM\x00\x2a'):
        return 'tiff'
    return 'unknown'


def ensure_fax_ready(file_path: str) -> str:
    """
    Return a path to a file txfax can send, converting as needed.

    Routes on file CONTENTS, not the extension:
      - PDF bytes                 → pdf_to_tiff (ghostscript)
      - TIFF bytes, compliant     → returned unchanged
      - TIFF bytes, non-compliant → normalize_tiff_for_fax (ImageMagick)

    Raises ValueError for anything that is neither PDF nor TIFF, so callers can
    return a 400 instead of surfacing a converter crash as a 500.
    """
    kind = sniff_file_type(file_path)

    if kind == 'pdf':
        if not file_path.lower().endswith('.pdf'):
            logger.info('ensure_fax_ready: %s is PDF content despite its extension', file_path)
        return pdf_to_tiff(file_path)

    if kind == 'tiff':
        if is_fax_ready_tiff(file_path):
            return file_path
        logger.info('ensure_fax_ready: %s is not a valid TIFF/F, normalising for fax', file_path)
        return normalize_tiff_for_fax(file_path)

    raise ValueError(
        'Unsupported file: expected a PDF or TIFF (the file contents match neither).'
    )


def tiff_to_pdf(tif_path: str) -> str:
    """
    Convert a received fax TIFF (G3/G4 encoded) to PDF.
    Uses tiff2pdf (libtiff-tools) which handles fax encoding correctly.
    Ghostscript produces blank pages with G3/G4 fax TIFFs so it is NOT used here.
    The PDF is cached alongside the TIFF — subsequent calls return the cached file.
    Returns the path to the PDF. Raises RuntimeError on failure.
    """
    pdf_path = os.path.splitext(tif_path)[0] + '.pdf'
    if os.path.isfile(pdf_path):
        return pdf_path  # Already converted — return cached copy

    if shutil.which('tiff2pdf'):
        # tiff2pdf handles G3/G4 fax-encoded TIFFs correctly
        cmd = ['tiff2pdf', '-o', pdf_path, tif_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and os.path.isfile(pdf_path):
            return pdf_path
        logger.warning(f'tiff2pdf failed: {result.stderr.strip() or result.stdout.strip()} — falling back to GS')

    # Fallback: Ghostscript (may produce blank pages for G3/G4 fax TIFFs)
    cmd = [
        'gs', '-q', '-dNOPAUSE', '-dBATCH', '-dSAFER',
        '-sDEVICE=pdfwrite', '-dPDFSETTINGS=/default', '-dCompatibilityLevel=1.4',
        f'-sOutputFile={pdf_path}', tif_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not os.path.isfile(pdf_path):
        raise RuntimeError(f'TIFF to PDF conversion failed: {result.stderr.strip()}')
    return pdf_path
