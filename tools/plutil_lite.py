#!/usr/bin/env python3
"""plutil_lite: the few `plutil` calls that tools/herolte-tune-ios-root.sh makes, for Linux.

    plutil_lite.py -create xml1 FILE
    plutil_lite.py -replace KEY -string|-bool|-integer|-json VALUE FILE
    plutil_lite.py -convert xml1 FILE

Only the calls tools/herolte-tune-ios-root.sh makes, nothing more. -replace keeps the file's current format
(xml or binary), -create writes an empty dictionary and refuses to overwrite, -convert xml1 rewrites the file as XML.
KEY is a plain top-level key (a dotted key is refused instead of being guessed). Anything else exits non-zero.
"""
import json
import os
import plistlib
import sys
import tempfile


def die(msg):
    sys.stderr.write("plutil_lite: %s\n" % msg)
    sys.exit(1)


def load(path):
    with open(path, "rb") as f:
        raw = f.read()
    fmt = plistlib.FMT_BINARY if raw.startswith(b"bplist") else plistlib.FMT_XML
    data = plistlib.loads(raw)
    return data, fmt


def save(path, data, fmt):
    # temporary file next to the target, then os.replace: a failure never leaves a half-written plist
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".plutil_lite.", dir=d)
    try:
        with os.fdopen(fd, "wb") as f:
            plistlib.dump(data, f, fmt=fmt)
        st = os.stat(path) if os.path.exists(path) else None
        if st is not None:
            os.chmod(tmp, st.st_mode & 0o7777)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def parse_value(kind, text):
    if kind == "-string":
        return text
    if kind == "-bool":
        t = text.strip().lower()
        if t in ("yes", "true", "1"):
            return True
        if t in ("no", "false", "0"):
            return False
        die("bad bool value: %r" % text)
    if kind == "-integer":
        try:
            return int(text, 0)
        except ValueError:
            die("bad integer value: %r" % text)
    if kind == "-json":
        try:
            return json.loads(text)
        except ValueError as e:
            die("bad json value: %s" % e)
    die("unsupported type %s" % kind)


def main(argv):
    a = argv[1:]
    if len(a) == 3 and a[0] == "-create" and a[1] == "xml1":
        if os.path.exists(a[2]):
            die("%s: file exists" % a[2])
        save(a[2], {}, plistlib.FMT_XML)
        return 0
    if len(a) == 3 and a[0] == "-convert" and a[1] == "xml1":
        data, _ = load(a[2])
        save(a[2], data, plistlib.FMT_XML)
        return 0
    if len(a) == 5 and a[0] == "-replace":
        key, kind, text, path = a[1:]
        if "." in key:
            die("key paths are not supported: %r" % key)
        data, fmt = load(path)
        if not isinstance(data, dict):
            die("%s: top level is not a dictionary" % path)
        data[key] = parse_value(kind, text)
        save(path, data, fmt)
        return 0
    die("unsupported arguments: %s" % " ".join(a))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
