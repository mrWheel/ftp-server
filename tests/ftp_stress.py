#!/usr/bin/env python3
#-- SPDX-License-Identifier: GPL-3.0-or-later
#-- Copyright (C) 2026 Willem Aandewiel

"""Repeat FTP workflow tests against a running server."""

import argparse
import ftplib
import hashlib
import os
import tempfile
import time
import uuid


HOST = os.environ.get("FTP_HOST", "ftp-server.local")
PORT = int(os.environ.get("FTP_PORT", "21"))


def close_ftp(ftp):
    if ftp is None:
        return
    try:
        ftp.quit()
    except (EOFError, OSError, ftplib.Error):
        ftp.close()


def connect(retries, retry_delay, timeout):
    last_error = None
    for attempt in range(retries):
        ftp = ftplib.FTP()
        try:
            ftp.connect(HOST, PORT, timeout=timeout)
            ftp.timeout = timeout
            ftp.set_pasv(True)
            ftp.login()
            return ftp
        except (ConnectionError, TimeoutError, OSError, ftplib.Error) as error:
            last_error = error
            ftp.close()
            if attempt + 1 < retries:
                if isinstance(error, ftplib.error_temp) and str(error).startswith("421"):
                    print("WAIT server client slot available", flush=True)
                time.sleep(retry_delay * (attempt + 1))
    raise RuntimeError("could not connect to %s:%d: %s" % (HOST, PORT, last_error))


def remove_remote_file(ftp, path):
    try:
        ftp.delete(path)
        return True
    except ftplib.error_perm:
        return False


def remove_remote_directory(ftp, path):
    try:
        ftp.cwd(path)
        entries = ftp.nlst()
        ftp.cwd("..")
    except (EOFError, OSError, ftplib.Error):
        return
    for entry in entries:
        child = path + "/" + entry
        if not remove_remote_file(ftp, child):
            remove_remote_directory(ftp, child)
    try:
        ftp.rmd(path)
    except ftplib.error_perm:
        pass


def run_iteration(index, retries, retry_delay, timeout, keep):
    name = "ftp_stress_%d_%s" % (os.getpid(), uuid.uuid4().hex[:12])
    ftp = None
    try:
        ftp = connect(retries, retry_delay, timeout)
        ftp.mkd(name)
        ftp.cwd(name)
        payload = ("iteration %d from pid %d\n" % (index, os.getpid())).encode()
        with tempfile.NamedTemporaryFile() as source:
            source.write(payload)
            source.flush()
            source.seek(0)
            ftp.storbinary("STOR source.bin", source)
        if ftp.size("source.bin") != len(payload):
            raise RuntimeError("uploaded file has the wrong size")
        with tempfile.NamedTemporaryFile() as downloaded:
            ftp.retrbinary("RETR source.bin", downloaded.write)
            downloaded.flush()
            downloaded.seek(0)
            if hashlib.sha256(downloaded.read()).digest() != hashlib.sha256(payload).digest():
                raise RuntimeError("download checksum mismatch")
        if "source.bin" not in ftp.nlst():
            raise RuntimeError("uploaded file missing from NLST")
        ftp.rename("source.bin", "renamed.bin")
        if ftp.size("renamed.bin") != len(payload):
            raise RuntimeError("SIZE returned the wrong value")
        ftp.delete("renamed.bin")
        ftp.cwd("..")
        if not keep:
            ftp.rmd(name)
        return True
    except (ConnectionError, TimeoutError, OSError, ftplib.Error, RuntimeError) as error:
        print("FAIL iteration %d (%s): %s" % (index, name, error), flush=True)
        if ftp is not None:
            try:
                ftp.cwd("/")
                if not keep:
                    remove_remote_directory(ftp, name)
            except (EOFError, OSError, ftplib.Error):
                pass
        return False
    finally:
        close_ftp(ftp)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", "--iterations", type=int, default=10)
    parser.add_argument("--retries", type=int, default=30)
    parser.add_argument("--retry-delay", type=float, default=0.5)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--pause", type=float, default=0)
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()
    if args.iterations < 1 or args.retries < 1 or args.timeout <= 0:
        parser.error("iterations, retries and timeout must be positive")

    passed = 0
    print("Testing %s:%d for %d iteration(s)" % (HOST, PORT, args.iterations), flush=True)
    for index in range(1, args.iterations + 1):
        if run_iteration(index, args.retries, args.retry_delay, args.timeout, args.keep):
            passed += 1
            print("OK iteration %d" % index, flush=True)
        if args.pause and index < args.iterations:
            time.sleep(args.pause)
    print("Result: %d/%d passed" % (passed, args.iterations), flush=True)
    return 0 if passed == args.iterations else 1


if __name__ == "__main__":
    raise SystemExit(main())
