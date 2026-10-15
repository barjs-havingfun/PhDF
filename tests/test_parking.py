from phdf.services import parking


def test_add_list_and_tick(tmp_path):
    path = tmp_path / "Vault" / "PhDF" / "Parking Lot.md"
    assert parking.items(path) == []
    parking.add(path, "  Look up\nmontage theory ", "Film Art, p. 214")
    parking.add(path, "Buy coffee")
    parking.add(path, "   ")  # ignored

    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Parking Lot")
    items = parking.items(path)
    assert [i.text.split(" — ")[0] for i in items] == ["Look up montage theory", "Buy coffee"]
    assert "Film Art, p. 214 · " in items[0].text
    assert not any(i.done for i in items)

    first = items[0]
    assert parking.set_done(path, first.line, first.text, True)
    assert parking.items(path)[0].done
    assert not parking.set_done(path, first.line, "changed elsewhere", False)


def test_one_list_per_document_next_to_it(tmp_path, monkeypatch):
    from phdf.api import Api, Core
    from phdf.db import Store
    from phdf.engine import default_engine

    monkeypatch.setenv("PHDF_DATA_DIR", str(tmp_path / "data"))
    api = Api(Core(default_engine(), Store(tmp_path / "db.sqlite")), "main")
    api.set_setting("obsidian.vault", str(tmp_path / "Vault"))  # not used for parking

    pdf = tmp_path / "Books" / "Deep Work.pdf"
    path = api.parking_add("second", "Deep Work, p. 3", str(pdf))
    assert path == str(tmp_path / "Books" / "Deep Work.parking.md")
    text = (tmp_path / "Books" / "Deep Work.parking.md").read_text(encoding="utf-8")
    assert text.startswith("# Parking Lot — Deep Work")
    listing = api.parking_list(str(pdf))
    assert [i["text"].split(" — ")[0] for i in listing["items"]] == ["second"]
    item = listing["items"][0]
    assert api.parking_done(item["line"], item["text"], True, str(pdf))

    general = api.parking_add("no document open")
    assert general == str(tmp_path / "data" / "Parking Lot.md")
    assert not (tmp_path / "Vault").exists()
