#!/usr/bin/env python3
#-- SPDX-License-Identifier: GPL-3.0-or-later
#-- Copyright (C) 2026 Willem Aandewiel

"""Opt-in FTP integration tests for a running ESP32 FTP server."""

import concurrent.futures
import ftplib
import hashlib
import os
import socket
import tempfile
import time
import unittest


HOST = os.environ.get("FTP_HOST", "ftp-server.local")
PORT = int(os.environ.get("FTP_PORT", "21"))


class FtpServerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.ftp = None
        self.root = "copilot_test_%d_%d" % (os.getpid(), time.time_ns())
        self.ftp = ftplib.FTP()
        self.ftp.connect(HOST, PORT, timeout=10)
        self.ftp.timeout = 300
        self.ftp.login()
        self.ftp.cwd("/")
        self._cleanup_stale_test_directories()
        self.ftp.mkd(self.root)
        self.ftp.cwd(self.root)

    def tearDown(self):
        if self.ftp is None:
            return
        try:
            self.ftp.cwd("/")
            self._remove_directory(self.root)
        except (EOFError, OSError, ftplib.Error):
            pass
        finally:
            self._close_ftp(self.ftp)

    @staticmethod
    def _close_ftp(ftp):
        try:
            if ftp.sock is not None:
                try:
                    ftp.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                ftp.sock.close()
        finally:
            ftp.close()

    def _remove_directory(self, path):
        self.ftp.cwd(path)
        entries = self.ftp.nlst()
        self.ftp.cwd("..")
        for entry in entries:
            try:
                self.ftp.delete(path + "/" + entry)
            except ftplib.error_perm:
                self._remove_directory(path + "/" + entry)
        self.ftp.rmd(path)

    def _cleanup_stale_test_directories(self):
        for entry in self.ftp.nlst():
            if entry.startswith("copilot_test_"):
                self._remove_directory(entry)

    def test_directory_file_rename_and_delete(self):
        self.ftp.mkd("newDirectory")
        self.ftp.cwd("newDirectory")
        with tempfile.SpooledTemporaryFile() as source:
            self.ftp.storbinary("STOR sample.bin", source)
        self.assertIn("sample.bin", self.ftp.nlst())
        self.ftp.rename("sample.bin", "renamed.bin")
        self.ftp.delete("renamed.bin")
        self.ftp.cwd("..")
        self.ftp.rmd("newDirectory")

    def test_zero_and_large_binary_files(self):
        with tempfile.SpooledTemporaryFile() as zero:
            self.ftp.storbinary("STOR zero.bin", zero)
        self.assertEqual(self.ftp.size("zero.bin"), 0)

        payload = (b"ftp-server integration test\n" * 2048)
        with tempfile.SpooledTemporaryFile() as source:
            source.write(payload)
            source.seek(0)
            self.ftp.storbinary("STOR large.bin", source)
        with tempfile.SpooledTemporaryFile() as downloaded:
            self.ftp.retrbinary("RETR large.bin", downloaded.write)
            downloaded.seek(0)
            self.assertEqual(hashlib.sha256(downloaded.read()).digest(), hashlib.sha256(payload).digest())

    def test_repeated_pasv_and_epsv(self):
        for command in ("PASV", "PASV", "EPSV", "EPSV", "PASV"):
            response = self.ftp.sendcmd(command)
            self.assertIn(response[:3], ("227", "229"))
        self.assertEqual(self.ftp.voidcmd("NOOP")[:3], "200")

    def test_malformed_arguments_keep_control_connection(self):
        for command in ("CWD", "RETR", "STOR", "REST", "TYPE X", "OPTS UTF8 OFF"):
            with self.assertRaises(ftplib.error_perm) as error:
                self.ftp.sendcmd(command)
            self.assertTrue(str(error.exception).startswith("501"))
        self.assertEqual(self.ftp.voidcmd("NOOP")[:3], "200")

    def test_interrupted_upload_leaves_partial_file(self):
        connection = self.ftp.transfercmd("STOR interrupted.bin")
        connection.sendall(b"partial upload")
        connection.shutdown(socket.SHUT_WR)
        connection.close()
        self.ftp.voidresp()
        self.assertEqual(self.ftp.size("interrupted.bin"), len(b"partial upload"))

    def test_concurrent_clients(self):
        self._close_ftp(self.ftp)
        self.ftp = None

        def list_root(_):
            ftp = ftplib.FTP()
            try:
                ftp.connect(HOST, PORT, timeout=10)
                ftp.login()
                return ftp.nlst()
            finally:
                self._close_ftp(ftp)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(list_root, range(2)))
        self.assertEqual(len(results), 2)

    def test_reconnect_after_abrupt_disconnect(self):
        self._close_ftp(self.ftp)
        self.ftp = None

        for _ in range(10):
            ftp = ftplib.FTP()
            ftp.connect(HOST, PORT, timeout=10)
            ftp.login()
            self.assertIn(ftp.sendcmd("PASV")[:3], ("227", "229"))
            self._close_ftp(ftp)
            time.sleep(0.2)

        ftp = ftplib.FTP()
        try:
            ftp.connect(HOST, PORT, timeout=10)
            ftp.login()
            self.assertEqual(ftp.voidcmd("NOOP")[:3], "200")
        finally:
            self._close_ftp(ftp)

    def test_stop_start_restart_hook(self):
        self.ftp.sendcmd("XTEST RESTART")
        self._close_ftp(self.ftp)
        self.ftp = None

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            ftp = ftplib.FTP()
            try:
                ftp.connect(HOST, PORT, timeout=2)
                ftp.login()
                self.assertEqual(ftp.voidcmd("NOOP")[:3], "200")
                return
            except (ConnectionRefusedError, ConnectionResetError, TimeoutError, OSError, ftplib.Error):
                self._close_ftp(ftp)
                time.sleep(0.2)
        self.fail("FTP server did not restart within 10 seconds")


if __name__ == "__main__":
    unittest.main()
