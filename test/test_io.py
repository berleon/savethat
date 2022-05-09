import shutil

from savethat import io


def test_b2_find_remote(storage: io.B2Storage) -> None:
    storage.remove("configs/.test/")
    key = "configs/.test/tests.toml"
    with storage.open(key, "w") as f:
        f.write("test")
    storage.upload("configs/.test/")
    # assert storage.exists_remote("configs/.test") == "configs/.test"


def test_b2_upload(storage: io.B2Storage) -> None:
    key = "test_config_dir"
    storage.remove("test_config_dir")
    path = storage / key
    path.mkdir(exist_ok=True)
    (path / "test_file").write_text("hello world!")
    assert storage / key == path
    storage.upload(key)
    shutil.rmtree(path)
    assert not path.exists()
    download_path = storage.download(key)
    assert download_path == path
    assert (path / "test_file").read_text() == "hello world!"
    shutil.rmtree(path)
