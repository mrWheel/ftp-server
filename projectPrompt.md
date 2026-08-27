# FTP Server

# Project Prompt — `ftp_server`

## Goal

Build a production-quality, reusable ESP-IDF component named `ftp_server` that
exposes an already mounted ESP-IDF VFS filesystem on an ESP32 through standard
FTP. It must interoperate with common clients on Windows, Linux, macOS and
iOS/iPadOS, and be suitable for later publication in the Espressif Component
Registry. Development uses VSCode and ESP-IDF. All code comments, API docs,
README files and project documentation are written in English.

## Design boundary

This is an FTP component, not a networking application. It must not configure
Wi-Fi/Ethernet, mount or format filesystems, initialize SD cards or own global
network configuration. The application obtains an IP address, mounts a VFS path
and calls the component:

```c
ftp_server_config_t config = FTP_SERVER_DEFAULT_CONFIG();
config.base_path = "/storage";
ESP_ERROR_CHECK(ftp_server_start(&config));
```

Only data below the supplied path may be exposed.

## Platform

- Target ESP-IDF 6.x and retain practical compatibility with recent 5.x.
- Native C; no Arduino dependency.
- Use FreeRTOS, ESP-IDF VFS, lwIP BSD sockets, ESP logging and `esp_err_t`.
- Support ESP32 and ESP32-S3 without target-specific assumptions.
- Work above LittleFS, FATFS and SD-card FATFS through POSIX/VFS calls.
- Do not use `std::filesystem`, SPIFFS-specific logic or process-global `chdir()`.

## Protocol scope

Implement a configurable TCP control port (21 by default), bounded passive port
range, PASV and EPSV. Passive listeners have timeouts, are per-session, close on
transfer/session termination and never leak. Correctly handle repeated PASV,
early/late data connects, aborted transfers and disconnects. Active `PORT` is not
required initially; if added, prevent FTP bounce attacks.

Required commands:

```text
USER PASS SYST FEAT PWD XPWD CWD CDUP TYPE NOOP QUIT
PASV EPSV LIST NLST RETR STOR DELE MKD XMKD RMD XRMD
SIZE MDTM REST ABOR OPTS UTF8 ON RNFR RNTO
```

Unknown or malformed commands receive standards-compatible errors without
closing the control connection. Use conventional replies including 150, 200,
211, 213, 220, 221, 226, 227, 229, 230, 250, 257, 331, 350, 425, 426, 500, 501,
502, 503, 530, 550 and 553.

## Control parser and responses

Treat TCP as a stream: one `recv()` is not one command. Support partial commands,
multiple commands per packet and CRLF split across packets. Enforce a strict line
limit. Centralize bounded response formatting, support FEAT multiline syntax and
handle partial `send()` calls plus EINTR/EAGAIN/connection errors.

## Paths and sessions

Maintain a virtual current directory in each session. Resolve absolute and
relative FTP paths, `.`, `..` and repeated slashes with a dedicated function.
The resulting VFS path must remain under `base_path`; no client may escape using
traversal. Never use global CWD, file, command-buffer or passive-socket state.
Support UTF-8 names without unnecessary conversion.

## Listings and timestamps

Generate conventional Unix-style LIST lines understood by FileZilla, WinSCP,
Cyberduck, curl/lftp and mobile clients. Generate synthetic permissions and
ownership where VFS lacks those concepts. Implement NLST separately. Use real
timestamps when present, safe fallbacks otherwise, and UTC `YYYYMMDDhhmmss` for
MDTM. Missing metadata must never make a directory inaccessible or malformed.

## Transfers

Accept TYPE I and TYPE A without corrupting data. Stream zero-byte, text, binary,
WAV, firmware and files larger than RAM through a bounded fixed buffer. Never
allocate based on file size. Check partial reads/writes and close/fsync in the
correct order. REST applies to the next RETR (and STOR only if deliberately
documented) and resets afterward. Define and document whether interrupted uploads
remain as partial files.

## Authentication and security

Authentication is intentionally out of scope and must never be implemented.
The FTP server must not require a username or password. Classic FTP is
unencrypted and must only be used on a trusted LAN, never on the public Internet.
FTPS and SFTP are out of scope.

## Lifecycle and concurrency

Provide a minimal API with `ftp_server_start`, `ftp_server_stop` and
`ftp_server_is_running`. Permit stop then start without reboot or leaks. A bounded
task per session is acceptable; never create a task per command. `stop()` closes
the listener and all eventual session resources. Failures in one client must not
crash the server. Avoid holding filesystem locks while waiting for network I/O.

Configuration includes base path, control/passive ports, transfer-buffer size,
timeouts and maximum clients. Copy all configuration needed after `start()`; do
not depend on caller-owned temporary memory.

## Resource and error discipline

Every socket, FILE descriptor, directory handle, task, mutex and allocation has a
clear owner and cleanup path. Audit every error branch. Do not reboot on an FTP
error. Keep RAM per session bounded, avoid large stack arrays and stream listings
instead of building them in memory. Log useful events through ESP_LOG without
passwords or file-content dumps.

## Compatibility validation

Test real passive-mode workflows:

- Windows: FileZilla and WinSCP.
- Linux: curl, lftp and FileZilla.
- macOS: curl/lftp, Cyberduck and FileZilla.
- iOS/iPadOS: a reputable FTP file manager.

For each client cover browse, upload, download, zero-byte/large files, create,
rename and delete. Explicitly reproduce this regression:

1. `MKD newDirectory`;
2. upload a file into it;
3. refresh LIST;
4. CWD into it;
5. rename and delete it.

At no point may a missing LittleFS timestamp turn the directory into an unusable
`00:00 newDirectory` entry. Every operation reports success only after the POSIX
call actually succeeds.

## Manual curl compatibility check

Run these commands from macOS or Linux while the ESP32 is running and reachable
as `ftp-server.local`. They use passive FTP and do not require credentials. The
commands create and remove one temporary directory and file below `/storage`.

```bash
export FTP_HOST=ftp-server.local
export FTP_PORT=21
export FTP_BASE="ftp://${FTP_HOST}:${FTP_PORT}"
export FTP_TEST_DIR="curl_test_$$"
printf 'curl FTP test data\n' > /tmp/ftp-curl-test.txt

# Read the root and an existing directory.
curl --fail --ftp-pasv "${FTP_BASE}/"
curl --fail --ftp-pasv "${FTP_BASE}/NewMap/"

# Create a directory, upload a file, list it and download it again.
curl --fail --ftp-pasv --quote "MKD ${FTP_TEST_DIR}" "${FTP_BASE}/"
curl --fail --ftp-pasv --upload-file /tmp/ftp-curl-test.txt \
  "${FTP_BASE}/${FTP_TEST_DIR}/curl-test.txt"
curl --fail --ftp-pasv "${FTP_BASE}/${FTP_TEST_DIR}/"
curl --fail --ftp-pasv --output /tmp/ftp-curl-downloaded.txt \
  "${FTP_BASE}/${FTP_TEST_DIR}/curl-test.txt"
cmp /tmp/ftp-curl-test.txt /tmp/ftp-curl-downloaded.txt

# Query metadata and verify REST download returns the file suffix.
curl --fail --ftp-pasv --quote "SIZE /${FTP_TEST_DIR}/curl-test.txt" \
  "${FTP_BASE}/"
curl --fail --ftp-pasv --quote "MDTM /${FTP_TEST_DIR}/curl-test.txt" \
  "${FTP_BASE}/"
tail -c +6 /tmp/ftp-curl-test.txt > /tmp/ftp-curl-rest.txt
curl --fail --ftp-pasv --range 5- --output /tmp/ftp-curl-rest-downloaded.txt \
  "${FTP_BASE}/${FTP_TEST_DIR}/curl-test.txt"
cmp /tmp/ftp-curl-rest.txt /tmp/ftp-curl-rest-downloaded.txt

# Rename and delete the file and directory.
curl --fail --ftp-pasv --quote "RNFR /${FTP_TEST_DIR}/curl-test.txt" \
  --quote "RNTO /${FTP_TEST_DIR}/curl-renamed.txt" "${FTP_BASE}/"
curl --fail --ftp-pasv --quote "DELE /${FTP_TEST_DIR}/curl-renamed.txt" \
  "${FTP_BASE}/"
curl --fail --ftp-pasv --quote "RMD /${FTP_TEST_DIR}" "${FTP_BASE}/"
rm -f /tmp/ftp-curl-test.txt /tmp/ftp-curl-downloaded.txt /tmp/ftp-curl-rest.txt \
  /tmp/ftp-curl-rest-downloaded.txt
unset FTP_HOST FTP_PORT FTP_BASE FTP_TEST_DIR
```

Expected result: root/listing, upload, download, `SIZE`, `MDTM`, REST, rename,
delete and cleanup all return success; `cmp` produces no output. Also verify
that paths containing `..` never expose data outside the configured VFS root.
Use `curl --ftp-pasv`; active-mode `PORT` is intentionally not supported.

## Repeatable concurrent test program

For repeatable workflow testing, use `tests/ftp_stress.py`. It creates a unique
directory per iteration, uses passive FTP, verifies upload/download checksums,
checks `NLST` and `SIZE`, renames and deletes the file, and removes its own
directory. Connection retries handle the configured two-client limit, so the
program can be started from multiple terminal windows at the same time.

From the project root:

```bash
python3 tests/ftp_stress.py --iterations 10
```

Useful variants:

```bash
# Run 100 iterations with a short pause between iterations.
python3 tests/ftp_stress.py --iterations 100 --pause 0.2

# Run against an IP address instead of mDNS.
FTP_HOST=192.168.12.2 python3 tests/ftp_stress.py --iterations 10

# Keep remote test directories for post-run inspection.
python3 tests/ftp_stress.py --iterations 3 --keep
```

To run from multiple terminal windows, start the same command in each window.
Every process uses unique names. A `FAIL` line identifies the iteration and
remote directory; temporary `421 Too many clients` responses are retried for
longer so FileBrowser or another stress process can briefly occupy a client
slot. The final exit status is nonzero if any iteration fails after retries.

## Tests

Add host-testable unit tests for path normalization/root confinement and parser
framing. Add integration tests for login, PASV/EPSV, LIST/NLST, transfers, REST,
rename/delete, timeouts, disconnects and repeated start/stop. Exercise concurrent
clients and filesystem access from the application. Use sanitizers in host tests
where possible and document hardware/client test results.

## Deliverables

```text
components/ftp_server/
  CMakeLists.txt
  idf_component.yml
  include/ftp_server.h
  ftp_server.c (or clearly separated private C modules)
README.md
LICENSE
tests and an ESP-IDF example
```

Keep the public API small, implementation private and code reviewable. Study
existing ESP-IDF FTP projects for interoperability lessons, but do not copy code
without license and quality review. Prefer a clear, robust implementation over a
large abstraction framework. State any intentionally unsupported RFC feature and
all known limitations explicitly.

## Patch-log

### Implemented

- Added a reusable ESP-IDF FTP server component for an already-mounted VFS path.
- Added passive FTP support with PASV and EPSV, bounded passive ports and
  per-session data sockets.
- Added core FTP commands for browsing, transfers, directory management, file
  management, metadata and restart handling.
- Added path normalization and root confinement below the configured base path.
- Added bounded transfer buffers, partial socket-send handling and session
  cleanup paths.
- Added configurable component logging through menuconfig using ESP_LOGx().
- Added operation logging for transfers, directory operations, deletion and
  rename operations.
- Added storage reports after operations with automatic MB, KB or Bytes units.
- Added LittleFS and FATFS storage-statistics support, including the LittleFS
  fallback where statvfs() is not implemented.
- Added real mDNS hostname and FTP service advertisement to the basic example.
- Removed the mrwheel/ota_upload dependency and service from the project.
- Removed the unused wear-levelling handle warning from the LittleFS build.
- Increased the FTP session task stack to prevent FileZilla-triggered overflow.
- Kept USER/PASS as compatibility no-ops without storing credentials or requiring login.
- Added host protocol tests for path confinement, parser framing and response formatting.
- Added opt-in integration tests for passive transfers, interrupted uploads, repeated PASV/EPSV and concurrent clients.
- Audited required command arguments and added explicit 501 responses for malformed values.
- Added explicit FTP 552 reporting for storage exhaustion during transfers.
- Added menuconfig control for the maximum number of simultaneous FTP clients,
  defaulting to four in the examples.
- Added active-session tracking so shutdown can close existing control and
  passive sockets instead of waiting for normal client timeouts.
- Added and passed an automated reconnect lifecycle test covering ten abrupt
  disconnects with passive listeners followed by a successful new connection.
- Added an opt-in `XTEST RESTART` hook in the basic test build to exercise a
  real `ftp_server_stop()` followed by `ftp_server_start()` without enabling
  test control in production builds.
- Passed the automated `XTEST RESTART` lifecycle test on hardware; the server
  stopped, released active resources and served a new connection afterwards.
- Fixed integration-test socket cleanup so lifecycle validation completes
  without Python `ResourceWarning` messages.
- Added a repeatable `tests/ftp_stress.py` workflow for concurrent terminal
  runs, with unique remote directories, checksum verification, retry handling
  for temporary `421` client-limit responses and automatic cleanup.
- Fixed the stress harness to rewind upload files before sending them and to
  verify the remote file size before downloading.

### Remaining external validation

- No known implementation robustness blocker remains for the tested workflows.
- Additional client-matrix validation with WinSCP, lftp, Cyberduck and another
  iOS/iPadOS FTP client remains useful, but is external compatibility coverage
  rather than an unresolved server defect.
- The unrelated global `ota_manager_ext` Python entry-point warning remains
  outside this project scope.

### Validation record

The following checks have been completed during this development session:

- The ESP-IDF `examples/basic` application builds successfully with ESP-IDF
  6.0.2 for the configured ESP32 target. The generated application binary fits
  in the configured app partition.
- The host protocol tests pass with `make -C tests/host test`. These cover root
  confinement, `.`, `..`, repeated slashes, backslash rejection, command-line
  framing, CRLF handling, multiple commands and bounded response formatting.
- The focused hardware integration test passes with:
  `python3 -m unittest tests.integration.test_ftp_server.FtpServerIntegrationTests.test_zero_and_large_binary_files`.
  The last successful run completed in approximately 12 seconds.
- The focused hardware test successfully uploaded and downloaded a 57,344-byte
  binary file and verified its SHA-256 digest. It also verified a zero-byte
  upload in the same run.
- The server log confirmed `STOR` and `RETR` both completed with 57,344 bytes,
  and no Wi-Fi disconnect occurred during the successful run.
- The complete six-test hardware integration suite passed in approximately
  40 seconds with `Ran 6 tests ... OK`.
- The hardware lifecycle test passed in approximately 11 seconds, including a
  real stop/start and a successful new connection. Ten abrupt disconnects with
  passive listeners also passed without exhausting client slots.
- FileZilla and FileBrowser were used successfully for directory creation,
  uploads and directory browsing. curl successfully listed both the FTP root
  and `/NewMap/`.
- Two concurrent stress-test processes completed ten iterations each. A longer
  run correctly waited while FileBrowser occupied the configured client slots
  and resumed after FileBrowser disconnected.
- Earlier failed RETR runs were traced to a Wi-Fi beacon timeout and disconnect,
  followed by `Software caused connection abort` after 8,192 bytes. The
  transfer loop now yields between successful socket sends. The data socket
  timeout is directional: uploads use `SO_RCVTIMEO` and downloads use
  `SO_SNDTIMEO`.
- The integration test harness now uses `ftp-server.local` by default, accepts
  `FTP_HOST` as an override, cleans only its own `copilot_test_` directories,
  handles expected FTP 501 exceptions correctly and removes temporary files.

The following checks are not yet complete or are not hardware-proven:

- The complete six-test integration suite is green after the final RETR
  scheduling fix: `Ran 6 tests in 40.069s`, `OK`.
- The final firmware scheduling fix was rebuilt and flashed manually, then
  confirmed by the successful focused hardware test. Firmware is never flashed
  automatically during development.
- No client matrix validation has yet been recorded for FileZilla, WinSCP,
  curl, lftp, Cyberduck or iOS/iPadOS clients.
- Multiple stop/start cycles, passive-listener timeout behavior and explicit
  storage-full behavior remain possible extensions to the test suite, but are
  not currently blocking the validated FTP workflows.

### Coding and documentation rules

- Use Allman brace style.
- Use two spaces for indentation.
- Use lowerCamelCase for functions and variables, except in strict component
  code where PascalCase naming is used.
- Write all code comments and documentation in English.
- Prefix every code comment with `//-- `.
- Never use `/* ... */` comments.
- Place comments above the code they describe, not beside them.
