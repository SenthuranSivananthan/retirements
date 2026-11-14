"""Atomic, guarded JSON stage files and a single cross-platform writer lease."""

import json
import os
import tempfile
import threading
from pathlib import Path

from .enrichment_http import sha256

STAGES = (
    "retirement_source_automatic", "retirement_source_manual",
    "retirement_enrichment_automatic", "retirement_enrichment_manual",
    "retirements_canonical",
)


def fingerprint(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def read_bytes(path):
    try:
        return Path(path).read_bytes()
    except FileNotFoundError:
        return None


def write_json(path, value, expected):
    path = Path(path)
    body = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    if read_bytes(path) != expected:
        raise ValueError(f"Concurrent change to {path}; retry without replacing the new content")
    if body == expected:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        if read_bytes(path) != expected:
            raise ValueError(f"Concurrent change to {path}; existing content preserved")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class Stages:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.work = self.directory / ".enrichment-work"
        self.originals = {}
        self.values = {}
        self.lease = None
        self.blob_lock = threading.Lock()

    def __enter__(self):
        self.work.mkdir(parents=True, exist_ok=True)
        self.lease = (self.work / ".lock").open("a+b")
        self.lease.seek(0, 2)
        if self.lease.tell() == 0:
            self.lease.write(b"\0")
            self.lease.flush()
        self.lease.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.lease.close()
            self.lease = None
            raise ValueError("Another JSON enrichment process owns the writer lease") from error
        return self

    def __exit__(self, *args):
        if self.lease is not None:
            if os.name == "nt":
                import msvcrt
                self.lease.seek(0)
                msvcrt.locking(self.lease.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lease, fcntl.LOCK_UN)
            self.lease.close()

    def load(self, name):
        if name not in STAGES:
            raise ValueError(f"Unknown stage: {name}")
        if name not in self.values:
            body = read_bytes(self.directory / f"{name}.json")
            value = json.loads(body) if body is not None else {
                "schemaVersion": 1, "kind": name, "records": {}, "pages": {},
                **({"inputs": {}, "recordOverrides": {}} if name == "retirement_enrichment_manual" else {}),
                **({"catalogMetadata": {}, "revisions": {}, "projectionRevision": None}
                   if name == "retirements_canonical" else {}),
            }
            invalid = (
                not isinstance(value, dict) or value.get("schemaVersion") != 1
                or value.get("kind") != name or not isinstance(value.get("records"), dict)
                or not isinstance(value.get("pages"), dict)
            )
            if not invalid and name == "retirement_enrichment_manual":
                invalid = (
                    not isinstance(value.get("inputs"), dict)
                    or not isinstance(value.get("recordOverrides", {}), dict)
                )
            if not invalid and name == "retirements_canonical":
                pending = value.get("pendingProjection")
                invalid = (
                    "catalogMetadata" not in value or not isinstance(value["catalogMetadata"], dict)
                    or "revisions" not in value or not isinstance(value["revisions"], dict)
                    or "projectionRevision" not in value
                    or (value["projectionRevision"] is not None
                        and not isinstance(value["projectionRevision"], str))
                    or any(not isinstance(record, dict) or record.get("id") != identifier
                           for identifier, record in value["records"].items())
                    or (
                        "pendingProjection" in value and (
                            not value["records"] or not isinstance(pending, dict)
                            or "baseSha256" not in pending
                            or (pending.get("baseSha256") is not None and (
                                not isinstance(pending["baseSha256"], str)
                                or len(pending["baseSha256"]) != 64
                                or any(char not in "0123456789abcdef"
                                       for char in pending["baseSha256"])
                            ))
                            or not isinstance(pending.get("outputPath"), str)
                            or not pending["outputPath"]
                        )
                    )
                )
            if invalid:
                raise ValueError(f"Invalid JSON stage: {name}")
            self.originals[name] = body
            self.values[name] = value
        return self.values[name]

    def guard(self):
        for name, body in self.originals.items():
            if read_bytes(self.directory / f"{name}.json") != body:
                raise ValueError(f"Stage changed during processing: {name}; retry from saved checkpoints")

    def save(self, name):
        self.guard()
        path = self.directory / f"{name}.json"
        write_json(path, self.values[name], self.originals[name])
        self.originals[name] = path.read_bytes()

    def initialize(self):
        for name in STAGES:
            self.load(name)
            self.save(name)

    def blob(self, content_hash):
        if (not isinstance(content_hash, str) or len(content_hash) != 64
                or any(char not in "0123456789abcdef" for char in content_hash)):
            raise ValueError("Invalid transient content hash")
        return self.work / f"{content_hash}.txt"

    def stage_text(self, text):
        body = text.encode("utf-8")
        content_hash = sha256(body)
        path = self.blob(content_hash)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.work, suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            with self.blob_lock:
                if read_bytes(path) != body:
                    os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return content_hash

    def text(self, content_hash):
        body = self.blob(content_hash).read_bytes()
        if sha256(body) != content_hash:
            raise ValueError("Transient content changed; download again before processing")
        return body.decode("utf-8")
