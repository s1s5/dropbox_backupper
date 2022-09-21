import hashlib
import io
import os
import tarfile
from typing import IO, Iterable, Iterator, Optional

import dropbox
import dropbox.files


class IterStream(io.RawIOBase):
    leftover: Optional[bytes]

    def __init__(self, iterable: Iterator[bytes]):
        self.leftover = None
        self.iterable = iterable

    def readable(self):
        return True

    def readinto(self, b):
        try:
            length = len(b)  # We're supposed to return at most this much
            chunk = self.leftover or next(self.iterable)
            output, self.leftover = chunk[:length], chunk[length:]
            b[: len(output)] = output
            return len(output)
        except StopIteration:
            return 0  # indicate EOF


def iterable_to_stream(
    iterable: Iterable[bytes] | Iterator[bytes], buffer_size=io.DEFAULT_BUFFER_SIZE
) -> IO[bytes]:
    if isinstance(iterable, Iterator):
        iterator = iterable
    else:
        iterator = iter(iterable)
    return io.BufferedReader(IterStream(iterator), buffer_size=buffer_size)


class Reader:
    def __init__(self, f, chunk_size):
        self.f = f
        self.chunk_size = chunk_size
        self.pos = 0
        self.content_hash = hashlib.sha256()

    def get(self):
        data = self.f.read(self.chunk_size)
        if data:
            self.content_hash.update(hashlib.sha256(data).digest())
        self.pos += len(data)
        return data

    def get_content_hash(self):
        return self.content_hash.hexdigest()


def upload_to_dropbox(dbx: dropbox.Dropbox, dbx_target_path: str, f):
    chunk_size = 4 * 1024 * 1024

    reader = Reader(f, chunk_size)

    sr = dbx.files_upload_session_start(reader.get())
    cursor = dropbox.files.UploadSessionCursor(
        session_id=sr.session_id, offset=reader.pos
    )
    commit = dropbox.files.CommitInfo(path=dbx_target_path)

    while chunk := reader.get():
        dbx.files_upload_session_append(chunk, cursor.session_id, cursor.offset)
        cursor.offset = reader.pos

    m = dbx.files_upload_session_finish(b"", cursor, commit)
    if reader.get_content_hash() != m.content_hash:
        print("Error: Content hash not equal")
    return m


def dir_to_tgz(root_dir: str) -> Iterator[bytes]:
    bio = io.BytesIO()

    with tarfile.open(fileobj=bio, mode="w:gz") as tf:
        for root, _, files in os.walk(root_dir):
            for f in files:
                af = os.path.join(root, f)
                rf = os.path.relpath(af, start=root_dir)
                print(rf)
                tf.add(af, rf)

                if bio.tell() > 1 << 20:
                    yield bio.getvalue()
                    bio.seek(0)
                    bio.truncate()
    if bio.tell():
        yield bio.getvalue()


def main(root_dir, dropbox_token, target_path):
    dbx = dropbox.Dropbox(dropbox_token)
    upload_to_dropbox(dbx, target_path, iterable_to_stream(dir_to_tgz(root_dir)))


def __entry_point():
    import argparse

    parser = argparse.ArgumentParser(
        description="",  # プログラムの説明
    )
    parser.add_argument("-s", "--root-dir")
    parser.add_argument("-d", "--target-path")
    parser.add_argument("-t", "--dropbox-token")
    main(**dict(parser.parse_args()._get_kwargs()))


if __name__ == "__main__":
    __entry_point()
