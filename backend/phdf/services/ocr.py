"""OCR for scanned pages, using the Tesseract engine built into MuPDF.

No Tesseract install is needed: only language files (*.traineddata, ~4 MB each), downloaded on
first use into PhDF's data folder (an installed Tesseract's files are used too, if present).

Recognition runs on a rendered image, outside the document lock, so the rest of the app stays
responsive. The words come back with positions and are written into the page as invisible text
— like OCRmyPDF — so selection, search, quotes and export work, in PhDF and in any other viewer
after saving.
"""

import os
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from phdf.paths import data_dir

OCR_DPI = 300
LANGUAGE_URL = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/{lang}.traineddata"
# Offered for download in the UI (code -> name); any other Tesseract code works too.
COMMON_LANGUAGES = {
    "eng": "English",
    "tur": "Turkish",
    "deu": "German",
    "fra": "French",
    "spa": "Spanish",
    "ita": "Italian",
    "por": "Portuguese",
    "rus": "Russian",
    "ara": "Arabic",
}


@dataclass(frozen=True)
class OcrWord:
    text: str
    bbox: tuple[float, float, float, float]  # PDF points of the original page


def own_tessdata() -> Path:
    path = data_dir() / "tessdata"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _system_tessdata() -> list[Path]:
    candidates = [os.environ.get("TESSDATA_PREFIX")]
    if exe := shutil.which("tesseract"):
        candidates.append(str(Path(exe).parent / "tessdata"))
    if sys.platform == "win32":
        for base in (os.environ.get("PROGRAMFILES"), os.environ.get("LOCALAPPDATA")):
            if base:
                candidates.append(str(Path(base) / "Tesseract-OCR" / "tessdata"))
                candidates.append(str(Path(base) / "Programs" / "Tesseract-OCR" / "tessdata"))
    else:
        candidates += [
            "/opt/homebrew/share/tessdata",
            "/usr/local/share/tessdata",
            "/usr/share/tesseract-ocr/5/tessdata",
            "/usr/share/tesseract-ocr/4.00/tessdata",
            "/usr/share/tessdata",
        ]
    return [Path(c) for c in candidates if c and Path(c).is_dir()]


def installed_languages() -> list[str]:
    langs = {p.stem for p in own_tessdata().glob("*.traineddata")}
    for folder in _system_tessdata():
        langs |= {p.stem for p in folder.glob("*.traineddata")}
    langs.discard("osd")
    return sorted(langs)


def tessdata_for(languages: list[str]) -> str:
    """A folder containing every requested language (copies system files into ours if needed)."""
    own = own_tessdata()
    for lang in languages:
        target = own / f"{lang}.traineddata"
        if target.exists():
            continue
        source = next(
            (f / target.name for f in _system_tessdata() if (f / target.name).exists()), None
        )
        if source is None:
            raise FileNotFoundError(f"OCR language '{lang}' is not installed")
        shutil.copyfile(source, target)
    return str(own)


def download_language(lang: str) -> None:
    if not lang.replace("_", "").isalnum():
        raise ValueError(f"invalid language code {lang!r}")
    target = own_tessdata() / f"{lang}.traineddata"
    tmp = target.with_suffix(".part")
    with urllib.request.urlopen(LANGUAGE_URL.format(lang=lang), timeout=60) as resp:  # noqa: S310
        tmp.write_bytes(resp.read())
    tmp.replace(target)


def recognize(png: bytes, scale: float, languages: list[str]) -> list[OcrWord]:
    """OCR a page image rendered at `scale` (pixels per point). Runs in a worker process."""
    tessdata = tessdata_for(languages)
    pix = pymupdf.Pixmap(png)
    pix.set_dpi(OCR_DPI, OCR_DPI)
    data = pix.pdfocr_tobytes(language="+".join(languages), tessdata=tessdata)
    with pymupdf.open("pdf", data) as ocr:
        page = ocr[0]
        # The OCR page is the image at OCR_DPI; map back to the original page's points.
        factor = (pix.width / scale) / page.rect.width
        return [
            OcrWord(text=w[4], bbox=(w[0] * factor, w[1] * factor, w[2] * factor, w[3] * factor))
            for w in page.get_text("words")
            if w[4].strip()
        ]


def unicode_font() -> str | None:
    """A system TrueType font covering Latin Extended (Turkish etc.) for the hidden text layer."""
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        paths = [Path(windir) / "Fonts" / name for name in ("arial.ttf", "segoeui.ttf")]
    elif sys.platform == "darwin":
        paths = [
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/Library/Fonts/Arial.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        ]
    else:
        paths = [
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),  # Debian, Ubuntu
            Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),  # Arch
            Path("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"),  # Fedora
            Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),  # openSUSE
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
        ]
    found = next((str(p) for p in paths if p.is_file()), None)
    if found is None and sys.platform.startswith("linux") and shutil.which("fc-match"):
        # Ask fontconfig for any TrueType sans font.
        try:
            out = subprocess.run(
                ["fc-match", "-f", "%{file}", "sans:fontformat=TrueType"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()  # fmt: skip
            if out.lower().endswith(".ttf") and Path(out).is_file():
                found = out
        except (OSError, subprocess.SubprocessError):
            pass
    return found
