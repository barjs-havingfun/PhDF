"""Backend shared by all windows (`Core`) and the per-window API exposed to the frontend (`Api`).

Each window gets its own `Api`, exposed as `window.pywebview.api.*`; pywebview exposes every
public attribute, so internals are underscore-prefixed. Open documents are shared between windows
and reference-counted, so closing a tab in one window never closes the document in another.
Calls arrive on worker threads; MuPDF is not thread-safe, so engine access is serialized.
Page images are served separately by `RenderServer` (see `Core.render`).

Document ids are content hashes, so saving annotations gives a file a new id. `Core` keeps the
old ids as aliases: the frontend can keep using the id it was given for the whole session.
"""

from phdf.api.ai import AiApi
from phdf.api.annotations import AnnotationsApi
from phdf.api.core import SESSION_PREFIX, Core
from phdf.api.documents import DocumentsApi
from phdf.api.library import LibraryApi
from phdf.api.links import LinksApi
from phdf.api.notes import NotesApi
from phdf.api.ocr_export import OcrExportApi
from phdf.api.tools import ToolsApi
from phdf.api.windows import WindowsApi

__all__ = ["SESSION_PREFIX", "Api", "Core"]


class Api(
    WindowsApi,
    DocumentsApi,
    AnnotationsApi,
    LibraryApi,
    OcrExportApi,
    NotesApi,
    AiApi,
    ToolsApi,
    LinksApi,
):
    """One per window, exposed to its page as `window.pywebview.api.*`."""
