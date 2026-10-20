import os
import stat

import pytest

from buddy_host.qa.photos import PhotoRejected, PhotoStore

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class Clock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def test_saves_a_jpeg_and_a_png_with_the_right_extension(tmp_path):
    store = PhotoStore(tmp_path / "photos")

    jpeg = store.save(JPEG)
    png = store.save(PNG)

    assert jpeg.suffix == ".jpg" and jpeg.read_bytes() == JPEG
    assert png.suffix == ".png" and png.read_bytes() == PNG
    assert jpeg.parent == tmp_path / "photos"


def test_only_the_owner_can_read_a_saved_photo(tmp_path):
    path = PhotoStore(tmp_path / "photos").save(JPEG)

    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_something_that_is_not_an_image_is_rejected(tmp_path):
    store = PhotoStore(tmp_path / "photos")

    for junk in (b"", b"hello", b"GIF89a....", b"<html></html>"):
        with pytest.raises(PhotoRejected):
            store.save(junk)
    assert not (tmp_path / "photos").exists() or not list((tmp_path / "photos").iterdir())


def test_an_oversized_photo_is_rejected(tmp_path):
    store = PhotoStore(tmp_path / "photos", max_bytes=100)

    with pytest.raises(PhotoRejected, match="太大"):
        store.save(JPEG + b"\x00" * 100)


def test_every_photo_gets_its_own_unpredictable_name(tmp_path):
    store = PhotoStore(tmp_path / "photos")

    names = {store.save(JPEG).name for _ in range(5)}

    assert len(names) == 5


def test_photos_older_than_the_retention_period_are_deleted(tmp_path):
    clock = Clock()
    store = PhotoStore(tmp_path / "photos", retention_s=3600, clock=clock)
    old = store.save(JPEG)
    os.utime(old, (clock.now - 7200, clock.now - 7200))
    fresh = store.save(JPEG)  # 存新的照片時順便清掉過期的

    assert not old.exists()
    assert fresh.exists()


def test_purge_keeps_photos_within_the_retention_period(tmp_path):
    clock = Clock()
    store = PhotoStore(tmp_path / "photos", retention_s=3600, clock=clock)
    recent = store.save(JPEG)
    os.utime(recent, (clock.now - 3500, clock.now - 3500))

    removed = store.purge()

    assert removed == 0 and recent.exists()


def test_purge_returns_how_many_were_deleted_and_ignores_other_files(tmp_path):
    clock = Clock()
    store = PhotoStore(tmp_path / "photos", retention_s=60, clock=clock)
    a, b = store.save(JPEG), store.save(PNG)
    for path in (a, b):
        os.utime(path, (clock.now - 120, clock.now - 120))
    note = tmp_path / "photos" / "notes.txt"
    note.write_text("not a photo", encoding="utf-8")
    os.utime(note, (clock.now - 120, clock.now - 120))

    assert store.purge() == 2
    assert note.exists()  # 只清自己存的照片


def test_purge_on_a_missing_directory_is_a_no_op(tmp_path):
    assert PhotoStore(tmp_path / "never-created").purge() == 0


def test_the_photo_directory_is_private_too(tmp_path):
    store = PhotoStore(tmp_path / "photos")

    store.save(JPEG)

    assert stat.S_IMODE(os.stat(tmp_path / "photos").st_mode) == 0o700


def test_a_failed_write_leaves_no_half_written_photo(tmp_path, monkeypatch):
    store = PhotoStore(tmp_path / "photos")

    def boom(fd, mode):
        raise OSError("磁碟滿了")

    monkeypatch.setattr(os, "fdopen", boom)

    with pytest.raises(OSError):
        store.save(JPEG)

    assert list((tmp_path / "photos").iterdir()) == []


def test_a_purge_that_cannot_read_the_directory_does_not_break_saving(tmp_path, monkeypatch):
    store = PhotoStore(tmp_path / "photos")
    store.save(JPEG)

    from pathlib import Path

    def broken(self):
        raise PermissionError("不能列出")

    monkeypatch.setattr(Path, "iterdir", broken)

    assert store.purge() == 0  # 清理失敗只記 log，不會讓存照片或問答跟著失敗
