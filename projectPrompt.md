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
config.user = "esp32";
config.password = "esp32";
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

Configuration includes base path, credentials, anonymous mode, control/passive
ports, transfer-buffer size, timeouts and maximum clients. Copy all configuration
needed after `start()`; do not depend on caller-owned temporary memory.

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

### Remaining robustness work

- Remove the legacy username/password fields and USER/PASS login flow completely.
- Add host-testable unit tests for path confinement, parser framing and response
  formatting.
- Add integration tests for passive transfers, zero-byte files, large files,
  interrupted transfers, repeated PASV/EPSV and concurrent clients.
- Audit every FTP command for malformed arguments and consistent reply codes.
- Improve transfer error reporting, especially explicit storage-full handling
  for ENOSPC.
- Complete lifecycle testing for repeated start/stop, disconnects, timeouts and
  all socket, task, mutex, directory and file cleanup paths.
- Validate the implementation with FileZilla, WinSCP, curl, lftp, Cyberduck and
  a reputable iOS/iPadOS FTP client.
- Remove or separately resolve the unrelated global ota_manager_ext Python
  entry-point warning.

### Coding and documentation rules

- Use Allman brace style.
- Use two spaces for indentation.
- Use lowerCamelCase for functions and variables, except in strict component
  code where PascalCase naming is used.
- Write all code comments and documentation in English.
- Prefix every code comment with `//-- `.
- Never use `/* ... */` comments.
- Place comments above the code they describe, not beside them.
