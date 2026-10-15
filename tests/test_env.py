import os

from phdf.env import load_dotenv


def test_load_dotenv(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('# comment\nPHDF_A=1\nPHDF_B = "quoted"\nPHDF_KEEP=from-file\nbroken line\n')
    monkeypatch.delenv("PHDF_A", raising=False)
    monkeypatch.delenv("PHDF_B", raising=False)
    monkeypatch.setenv("PHDF_KEEP", "from-env")

    load_dotenv(env)

    assert os.environ["PHDF_A"] == "1"
    assert os.environ["PHDF_B"] == "quoted"
    assert os.environ["PHDF_KEEP"] == "from-env"  # real env wins


def test_missing_file_is_ignored(tmp_path):
    load_dotenv(tmp_path / "nope.env")
