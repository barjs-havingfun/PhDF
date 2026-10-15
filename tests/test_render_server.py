import urllib.error
import urllib.request

import pytest

from phdf.services.render_server import RenderServer

DOC = "a" * 64
FAKE_PNG = bytes([0x89]) + b"PNG fake"


@pytest.fixture
def server():
    calls = []

    def render(doc_id, page, scale, clip):
        calls.append((doc_id, page, scale, clip))
        return b"\x89PNG fake" if doc_id == DOC and page < 3 else None

    srv = RenderServer(render).start()
    srv.calls = calls
    yield srv
    srv.stop()


def get(url):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.headers["Content-Type"], resp.read()


def test_serves_png(server):
    status, ctype, body = get(f"{server.base_url}/page/{DOC}/1.png?s=2&clip=0,0,10,20")
    assert (status, ctype, body) == (200, "image/png", b"\x89PNG fake")
    assert server.calls == [(DOC, 1, 2.0, (0.0, 0.0, 10.0, 20.0))]


def test_scale_is_clamped(server):
    get(f"{server.base_url}/page/{DOC}/0.png?s=999")
    assert server.calls[-1][2] == 8.0


@pytest.mark.parametrize(
    "path",
    [
        "/wrong-token/page/{doc}/0.png",
        "{base}/page/{doc}/9.png",  # renderer returns None
        "{base}/page/not-a-hash/0.png",
    ],
)
def test_not_found(server, path):
    base = server.base_url
    origin = base.rsplit("/", 1)[0]
    url = path.format(base=base, doc=DOC)
    url = url if url.startswith("http") else origin + url
    with pytest.raises(urllib.error.HTTPError) as err:
        get(url)
    assert err.value.code == 404


def test_bad_clip(server):
    with pytest.raises(urllib.error.HTTPError) as err:
        get(f"{server.base_url}/page/{DOC}/0.png?clip=1,2")
    assert err.value.code == 400


def test_repeat_requests_come_from_the_cache(server):
    url = f"{server.base_url}/page/{DOC}/2.png?s=1"
    first, second = get(url)[2], get(url)[2]
    assert first == second == FAKE_PNG
    assert len(server.calls) == 1


def test_forget_drops_a_documents_images(server):
    url = f"{server.base_url}/page/{DOC}/1.png?s=1"
    get(url)
    server.forget(DOC)
    get(url)
    assert len(server.calls) == 2
