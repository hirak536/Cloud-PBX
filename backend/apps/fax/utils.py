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
