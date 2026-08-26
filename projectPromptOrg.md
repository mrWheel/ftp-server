# FTP Server

# Project Prompt — `ftp_server`

## Goal

Build a production-quality, reusable ESP-IDF component named `ftp_server` that exposes an already mounted ESP-IDF VFS filesystem on an ESP32 through the standard FTP protocol.

The FTP server must be compatible with common FTP clients running on:

- Windows
- Linux
- macOS
- iOS / iPadOS

The primary goal is reliable file transfer between an ESP32 and computers or mobile devices on a local network.

The implementation must be suitable for use as an independent ESP-IDF component and should eventually be suitable for publication in the Espressif Component Registry.

The project is developed using VSCode + ESP-IDF.

All source-code comments, API documentation, README files and other project documentation must be written in English.

---

# Important design philosophy

This must be an **FTP server component**, not a complete networking application.

The component must NOT:

- configure WiFi
- connect to WiFi
- create an Access Point
- configure Ethernet
- mount filesystems
- format filesystems
- initialize SD cards
- own the application's network configuration

The application using the component is responsible for:

1. initializing networking;
2. obtaining an IP address;
3. mounting the filesystem;
4. calling the FTP server component with the VFS mount point that should be shared.

Example:

```c
ftp_server_config_t config = FTP_SERVER_DEFAULT_CONFIG();

config.base_path = "/sdcard";
config.user = "esp32";
config.password = "esp32";

ESP_ERROR_CHECK(ftp_server_start(&config));
```

The FTP server must then expose only the contents below `/sdcard`.

---

# ESP-IDF version

Target the current ESP-IDF 6.x architecture.

The component should preferably also remain compatible with recent ESP-IDF 5.x releases where practical, but do not compromise the ESP-IDF 6.x design for old releases.

Use standard ESP-IDF APIs.

Prefer:

- FreeRTOS
- ESP-IDF VFS
- BSD sockets provided by ESP-IDF/lwIP
- ESP-IDF logging
- ESP-IDF error handling

Avoid Arduino dependencies.

This is a native ESP-IDF component.

---

# Supported ESP32 targets

The architecture must not contain assumptions specific to one ESP32 variant.

At minimum it should be suitable for:

- ESP32
- ESP32-S3

Prefer compatibility with other ESP-IDF targets that provide WiFi and BSD sockets.

Do not introduce architecture-specific code unless absolutely necessary.

---

# Filesystems

The FTP component operates on an already mounted ESP-IDF VFS path.

Support:

- LittleFS
- FATFS
- FATFS on SD card

The FTP server must not need to know which filesystem is underneath the VFS mount point.

Do NOT implement filesystem-specific FTP logic unless absolutely necessary.

Do NOT add SPIFFS-specific support.

Typical mount points:

```text
/littlefs
/sdcard
/storage
```

The application supplies the root path.

Example:

```c
config.base_path = "/littlefs";
```

All FTP paths must be safely translated to paths underneath this root.

A client must NEVER be able to escape the configured root using constructs such as:

```text
..
../
../../
/../
foo/../../
```

Path canonicalization and root confinement are mandatory.

---

# FTP protocol

Implement a standards-compatible FTP server using TCP.

The server must implement the FTP control connection and separate data connections correctly.

Default control port:

```text
21
```

The port must be configurable so that development can also use ports such as:

```text
2121
```

---

# Passive mode is mandatory

Reliable Passive FTP support is one of the highest priorities.

Implement:

```text
PASV
```

correctly.

Also investigate and preferably implement:

```text
EPSV
```

for modern FTP clients.

The passive data port range must be configurable.

For example:

```text
50000 - 50100
```

Do not allocate arbitrary ports without bounds.

The passive listener must:

- be created only when needed;
- have proper timeouts;
- be closed after the transfer;
- be closed when the control session terminates;
- not leak sockets;
- not leave stale passive listeners behind.

The server must correctly handle clients that:

- send PASV before LIST;
- issue multiple PASV commands;
- abort a transfer;
- disconnect during a transfer;
- open the data connection slightly before or after issuing the transfer command.

---

# Active FTP

Passive mode has priority.

Active FTP using:

```text
PORT
```

may be implemented after passive mode is proven reliable.

Do not make active FTP a prerequisite for the first working implementation.

If PORT is implemented, validate the supplied IP address and port and do not allow it to be abused to connect the ESP32 to arbitrary remote systems.

---

# Required FTP commands

Implement at least:

```text
USER
PASS
SYST
FEAT
PWD
XPWD
CWD
CDUP
TYPE
NOOP
QUIT
PASV
EPSV
LIST
NLST
RETR
STOR
DELE
MKD
XMKD
RMD
XRMD
SIZE
MDTM
REST
ABOR
```

Also support when useful for compatibility:

```text
OPTS UTF8 ON
```

Unknown commands must produce a correct FTP error reply instead of closing the connection.

---

# File listing compatibility

Directory listing compatibility is extremely important.

`LIST` output should use a format understood by:

- FileZilla
- WinSCP
- Cyberduck
- Linux command-line FTP clients
- macOS FTP clients
- iOS/iPadOS FTP clients

Prefer a conventional Unix-style LIST representation.

Example:

```text
-rw-r--r-- 1 ftp ftp       1234 Aug 26 10:42 example.txt
drwxr-xr-x 1 ftp ftp          0 Aug 25 18:01 samples
```

Do not assume that every filesystem provides Unix ownership or permission information.

Generate sensible synthetic values where necessary.

Implement `NLST` separately and correctly.

---

# File transfers

Support binary file transfer reliably.

At minimum:

```text
TYPE I
```

must work correctly.

`TYPE A` should be accepted for client compatibility.

Do not corrupt files by applying inappropriate newline conversion.

FTP transfers must work for:

- zero-byte files
- small text files
- binary files
- WAV files
- firmware binaries
- files larger than available RAM

Files must be streamed.

NEVER load an entire file into RAM before transmitting it.

Likewise, uploads must be written incrementally to the filesystem.

Use bounded transfer buffers.

---

# Large files

The implementation must support files significantly larger than available ESP32 RAM.

Example design:

```text
filesystem -> fixed transfer buffer -> socket
```

and:

```text
socket -> fixed transfer buffer -> filesystem
```

The transfer buffer size should be configurable or chosen conservatively.

Do not use file-size-dependent heap allocations.

---

# Restartable downloads

Implement:

```text
REST
```

for resumed downloads when practical.

Example:

```text
REST 1048576
RETR firmware.bin
```

The following RETR should start reading from the requested byte offset.

Reset the REST position after the relevant transfer.

---

# Authentication

Support at least:

## Username/password mode

Example:

```text
USER esp32
PASS secret
```

## Anonymous mode

Optional but desirable:

```text
USER anonymous
```

Authentication must be configurable by the application.

Do not hardcode credentials.

Do not log passwords.

Example configuration:

```c
ftp_server_config_t config = FTP_SERVER_DEFAULT_CONFIG();

config.user = "esp32";
config.password = "secret";
config.allow_anonymous = false;
```

Credentials supplied by the application do not have to be stored by the FTP server in NVS.

---

# Public API

Provide a small, clean public API.

For example:

```c
#pragma once

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct
{
  const char *base_path;

  const char *user;
  const char *password;

  bool allow_anonymous;

  uint16_t control_port;

  uint16_t passive_port_min;
  uint16_t passive_port_max;

  size_t transfer_buffer_size;

  uint32_t control_timeout_ms;
  uint32_t data_timeout_ms;

  size_t max_clients;
} ftp_server_config_t;

#define FTP_SERVER_DEFAULT_CONFIG() \
{                                   \
  .base_path = "/sdcard",           \
  .user = NULL,                     \
  .password = NULL,                 \
  .allow_anonymous = true,          \
  .control_port = 21,               \
  .passive_port_min = 50000,        \
  .passive_port_max = 50100,        \
  .transfer_buffer_size = 4096,     \
  .control_timeout_ms = 300000,     \
  .data_timeout_ms = 30000,         \
  .max_clients = 2                  \
}

esp_err_t ftp_server_start(const ftp_server_config_t *config);

esp_err_t ftp_server_stop(void);

bool ftp_server_is_running(void);

#ifdef __cplusplus
}
#endif
```

This is an example API, not an inflexible requirement.

Improve it if there is a good architectural reason.

Keep the public API minimal.

Implementation details must remain private.

---

# Runtime lifecycle

The server must support:

```c
ftp_server_start(...)
```

followed later by:

```c
ftp_server_stop()
```

and another:

```c
ftp_server_start(...)
```

without requiring an ESP32 reboot.

`ftp_server_stop()` must:

- stop accepting clients;
- terminate or gracefully close active sessions;
- close the listening socket;
- close passive sockets;
- close active data sockets;
- close open files;
- delete FTP tasks;
- release queues, mutexes and event groups;
- release dynamically allocated memory.

There must be no resource leakage across repeated start/stop cycles.

---

# FreeRTOS architecture

Use a simple architecture appropriate for the ESP32.

Prefer clarity over unnecessary abstraction.

Possible architecture:

```text
ftp_server task
      |
      +-- accepts control connections
              |
              +-- ftp_session task
                      |
                      +-- command parser
                      +-- passive listener
                      +-- data socket
                      +-- filesystem operations
```

A dedicated task per FTP session is acceptable for a small configurable number of simultaneous clients.

Do not create a new FreeRTOS task for every individual FTP command or packet.

The maximum number of sessions must be bounded.

---

# Socket handling

Use the ESP-IDF/lwIP BSD socket API.

Handle correctly:

```c
socket()
bind()
listen()
accept()
connect()
recv()
send()
shutdown()
close()
setsockopt()
select()
poll()
```

where appropriate.

Every socket must have clearly defined ownership.

Every error path must close resources belonging to that operation.

Handle partial:

```c
send()
recv()
write()
read()
```

correctly.

Never assume:

```c
send(fd, buffer, length, 0)
```

sends the complete buffer.

Implement helper functions such as:

```c
send_all()
```

where useful.

Handle:

```text
EINTR
EAGAIN
EWOULDBLOCK
ECONNRESET
ETIMEDOUT
```

appropriately.

---

# FTP control channel parser

FTP commands arrive as CRLF terminated lines:

```text
USER esp32\r\n
```

The TCP stream must be treated as a stream.

Do NOT assume one `recv()` equals one FTP command.

The parser must correctly handle:

- partial commands;
- multiple commands in one recv();
- CRLF split across TCP packets;
- commands without parameters;
- maximum command length;
- malformed commands.

Set a strict maximum command-line size.

Malformed or oversized requests must not overflow buffers.

---

# FTP response handling

Create a centralized function for FTP responses.

For example:

```c
ftp_reply(session, 220, "ESP32 FTP Server ready.");
```

Do not scatter unsafe combinations of `sprintf()` and `send()` throughout the code.

Use bounded formatting functions.

Support multiline responses correctly when necessary, especially:

```text
FEAT
```

---

# Relevant FTP reply codes

Use standards-compatible replies.

Examples include:

```text
150 File status okay; about to open data connection
200 Command okay
211 System status / FEAT
213 File status
220 Service ready
221 Service closing control connection
226 Closing data connection; transfer complete
227 Entering Passive Mode
229 Entering Extended Passive Mode
230 User logged in
250 Requested file action okay
257 Path created / current directory
331 Username okay, need password
350 Requested file action pending further information
425 Cannot open data connection
426 Connection closed; transfer aborted
450 Requested file action not taken
500 Syntax error
501 Syntax error in parameters
502 Command not implemented
530 Not logged in
550 Requested action not taken
553 Requested action not taken; filename not allowed
```

Do not invent proprietary behavior where a standard FTP reply exists.

---

# Path handling

Treat FTP paths separately from VFS paths.

For example:

FTP client sees:

```text
/
/
/samples
/samples/kick.wav
```

while the ESP-IDF VFS paths may be:

```text
/sdcard
/sdcard/samples
/sdcard/samples/kick.wav
```

Implement a dedicated path resolver.

Example:

```c
esp_err_t ftp_resolve_path(
    ftp_session_t *session,
    const char *ftp_path,
    char *vfs_path,
    size_t vfs_path_size);
```

It must handle:

```text
.
..
/
relative paths
absolute paths
repeated slashes
```

and must guarantee that the resulting VFS path remains inside:

```text
config.base_path
```

This function deserves dedicated tests.

---

# Current working directory

Each FTP session has its own virtual current directory.

For example:

```text
/
```

or:

```text
/samples/drums
```

It must not use the process-global C working directory.

Do NOT implement FTP CWD using:

```c
chdir()
```

because simultaneous clients would then interfere with each other.

Maintain the FTP working directory inside the session object and translate it explicitly to a VFS path.

---

# Filenames and UTF-8

Support UTF-8 filenames where the underlying ESP-IDF filesystem supports them.

Implement or advertise:

```text
UTF8
```

through FEAT where appropriate.

Accept:

```text
OPTS UTF8 ON
```

Do not perform unnecessary character conversion.

---

# Timestamps

Use filesystem timestamps where available.

Support:

```text
MDTM filename
```

using standard UTC FTP timestamp formatting:

```text
YYYYMMDDhhmmss
```

Directory listings should use sensible timestamps.

Do not crash or return malformed listings when timestamps are unavailable.

---

# Concurrency

Multiple clients may connect simultaneously.

The component must therefore avoid:

- global current-directory state;
- global open-file state;
- shared passive sockets;
- shared command buffers.

Each session gets its own state.

Shared server state must be protected where required.

Start with a small maximum such as:

```text
2 clients
```

and make it configurable.

Correctness is more important than supporting many clients.

---

# Filesystem concurrency

Assume that the application itself may also access the mounted filesystem while FTP is running.

The FTP component must not globally lock the entire VFS for the lifetime of a session.

Use locking only where actually required.

Do not hold a filesystem mutex while waiting for network traffic.

Document any filesystem concurrency limitations that cannot reasonably be solved by the FTP component.

---

# Network interruptions

The server must survive:

- client disconnect during LIST;
- client disconnect during RETR;
- client disconnect during STOR;
- control connection disappearance;
- WiFi temporarily disappearing;
- data connection timeout;
- half-open TCP connections.

A failed FTP session must not crash or restart the ESP32.

A failed transfer must not stop the FTP server.

---

# Upload safety

For STOR:

- stream data directly;
- detect write failures;
- correctly close the file;
- return an appropriate FTP response;
- never write outside the FTP root.

Consider whether incomplete uploads should remain as partial files.

Document the chosen behavior.

Do not introduce complicated transactional storage unless needed.

---

# Logging

Use:

```c
ESP_LOGE
ESP_LOGW
ESP_LOGI
ESP_LOGD
ESP_LOGV
```

appropriately.

Example tags:

```text
ftp_server
ftp_session
ftp_data
```

Normal operation must not produce excessive logging.

Useful debug logging should include:

```text
client connected
USER
authentication result
CWD
PASV port
LIST
RETR filename
STOR filename
transfer size
transfer duration
disconnect reason
```

Never log passwords.

Do not dump entire transferred files.

---

# Error handling

Use:

```c
esp_err_t
```

for the component API.

Internal functions may use their natural return values where appropriate.

All error paths must be audited for:

- socket leaks;
- FILE pointer leaks;
- directory handle leaks;
- memory leaks;
- task leaks;
- mutex leaks.

Do not simply restart the ESP32 when an error occurs.

---

# Memory usage

The ESP32 has limited RAM.

Avoid:

- unbounded malloc();
- large stack arrays;
- storing directory listings completely in RAM;
- storing complete uploaded/downloaded files in RAM;
- dynamically allocating memory for every FTP command where unnecessary.

Prefer fixed-size bounded buffers inside a session structure.

Document approximate RAM use per connected FTP client.

---

# Security model

This FTP server is primarily intended for trusted local networks.

Classic FTP transmits usernames, passwords and file contents unencrypted.

Clearly document this limitation.

Do not imply that FTP is secure over the public Internet.

Do not expose the ESP32 FTP service directly to the Internet.

FTPS is NOT required for the initial implementation.

Keep the architecture sufficiently modular that explicit TLS/FTPS support could theoretically be added later, but do not complicate the initial server with unused TLS abstractions.

---

# Client compatibility

The implementation must be tested with real clients.

## Windows

At least:

```text
FileZilla
WinSCP
```

Passive mode must work.

Do not use the limitations of the traditional Windows `ftp.exe` client as the protocol design target.

## Linux

Test with at least:

```text
curl
lftp
FileZilla
```

where available.

Examples:

```bash
curl ftp://esp32.local/
curl -u esp32:esp32 ftp://esp32.local/
curl -u esp32:esp32 -T test.bin ftp://esp32.local/
curl -u esp32:esp32 ftp://esp32.local/test.bin -o test.bin
```

## macOS

Test command-line clients such as:

```text
curl
lftp
Cyberduck
FileZilla
```

Finder FTP access may also be tested, but do not use Finder's limitations as proof that the FTP server cannot upload files.

## iOS / iPadOS

Test with at least one reputable FTP-capable file-management application.

The goal is:

- browse directories;
- download files;
- upload files;
- create directories;
- rename/delete where supported by the implemented commands.

Do not assume that Apple's native Files app provides full FTP client functionality.

---

# mDNS

The FTP component itself should not be responsible for starting the global mDNS subsystem unless necessary.

However, document how the application can advertise the FTP service.

Typical desired hostname:

```text
esp32.local
```

and service:

```text
_ftp._tcp
```

If a small optional helper for registering the FTP mDNS service makes architectural sense, keep it clearly separated from the FTP protocol implementation.

---

# Existing implementations

Before implementing the protocol, investigate existing open-source ESP-IDF FTP server implementations.

In particular inspect:

```text
https://github.com/nopnop2002/esp-idf-ftpServer
```

Use existing projects to learn:

- FTP interoperability requirements;
- PASV behavior;
- ESP-IDF socket handling;
- LIST formatting;
- filesystem integration;
- compatibility workarounds.

However:

**Do not blindly copy an existing FTP server.**

Check:

- license compatibility;
- code quality;
- buffer safety;
- ESP-IDF 6.x compatibility;
- architecture;
- error handling;
- socket ownership;
- resource cleanup.

If code is reused, preserve legally required copyright and license notices.

Prefer implementing a clean component architecture rather than turning an example application into the final component without review.

---

# Repository structure

Use a conventional ESP-IDF component layout.

For example:

```text
ftp-server/
|
+-- CMakeLists.txt
+-- idf_component.yml
+-- LICENSE
+-- README.md
+-- projectPrompt.md
|
+-- include/
|   +-- ftp_server.h
|
+-- src/
|   +-- ftp_server.c
|   +-- ftp_session.c
|   +-- ftp_commands.c
|   +-- ftp_data.c
|   +-- ftp_path.c
|   +-- ftp_listing.c
|
+-- private_include/
|   +-- ftp_internal.h
|
+-- examples/
|   +-- basic/
|       +-- CMakeLists.txt
|       +-- sdkconfig.defaults
|       +-- main/
|           +-- CMakeLists.txt
|           +-- main.c
|
+-- test/
    +-- ...
```

Do not create artificial abstraction layers merely to increase the number of source files.

If fewer source files produce a clearer implementation, use fewer.

---

# Component dependencies

Keep dependencies minimal.

Likely ESP-IDF dependencies include:

```text
freertos
esp_event
esp_netif
lwip
vfs
```

Only list dependencies that are actually needed.

The FTP component must NOT require:

```text
esp_wifi
```

merely because the example application happens to use WiFi.

Networking is owned by the application.

---

# CMake

Create a proper component `CMakeLists.txt`.

For example:

```cmake
idf_component_register(
    SRCS
        "src/ftp_server.c"
        "src/ftp_session.c"
        "src/ftp_commands.c"
        "src/ftp_data.c"
        "src/ftp_path.c"
        "src/ftp_listing.c"

    INCLUDE_DIRS
        "include"

    PRIV_INCLUDE_DIRS
        "private_include"

    REQUIRES
        lwip
)
```

Adjust the dependencies based on the actual implementation.

Do not add unnecessary components.

---

# idf_component.yml

Prepare the project for eventual Espressif Component Registry publication.

Create an appropriate:

```text
idf_component.yml
```

including:

- component description;
- version;
- URL;
- repository;
- license;
- ESP-IDF version requirement.

Do not invent third-party dependencies when none are required.

---

# Kconfig

Prefer runtime configuration through:

```c
ftp_server_config_t
```

for settings applications may want to change.

Use Kconfig only for true compile-time settings.

Do not force username, password, root path or FTP port into menuconfig if they can reasonably be runtime configuration.

---

# Example application

Provide:

```text
examples/basic
```

The example must demonstrate:

1. initialize NVS if needed;
2. initialize networking;
3. connect to WiFi;
4. mount a filesystem;
5. start FTP server;
6. print the FTP URL/IP address;
7. keep running.

The example may contain WiFi and filesystem setup.

The reusable FTP component must not.

Keep this separation very clear.

---

# Testing

Do not declare the server complete because it compiles.

Test behavior.

At minimum test:

## Authentication

```text
USER
PASS
incorrect password
anonymous where enabled
command before login
```

## Navigation

```text
PWD
CWD /
CWD directory
CWD ..
CDUP
```

## Directory operations

```text
LIST
NLST
MKD
RMD
```

## Files

```text
SIZE
MDTM
RETR
STOR
DELE
```

## Transfer cases

```text
0 bytes
1 byte
1 KB
100 KB
1 MB
10+ MB where storage allows
```

Compare uploaded and downloaded files byte-for-byte.

Use hashes where practical.

---

# Stress tests

Perform repetitive tests such as:

```text
connect
login
LIST
disconnect
```

hundreds of times.

Also repeat:

```text
connect
login
PASV
RETR
disconnect
```

and:

```text
connect
login
PASV
STOR
disconnect
```

Monitor:

```text
heap before
heap after
minimum free heap
open sockets
task count
```

Look specifically for gradual resource leakage.

---

# Failure tests

Test malformed and hostile-but-valid network behavior.

Examples:

```text
command without CRLF
very long command
unknown command
PASV then QUIT
PASV then PASV
PASV without transfer
RETR nonexistent file
STOR invalid path
CWD ../../..
client disconnect during upload
client disconnect during download
data connection never arrives
control connection disappears during transfer
```

None of these may crash the ESP32.

---

# Development process

Work incrementally.

Do NOT attempt to implement every FTP command before testing anything.

Use the following phases.

## Phase 1 — Server skeleton

Implement:

```text
start
stop
listen
accept
220
QUIT
```

Verify repeated connections and disconnects.

---

## Phase 2 — Command parser

Add:

```text
USER
PASS
SYST
FEAT
PWD
CWD
CDUP
NOOP
TYPE
```

Verify stream parsing and authentication.

---

## Phase 3 — Passive data connection

Implement:

```text
PASV
EPSV
```

Test creating, accepting and reliably cleaning up data connections.

Do not proceed until passive connection lifecycle is robust.

---

## Phase 4 — Directory listing

Implement:

```text
LIST
NLST
```

Test with Windows, Linux and macOS clients.

---

## Phase 5 — Download

Implement:

```text
RETR
SIZE
MDTM
REST
```

Test binary integrity and large files.

---

## Phase 6 — Upload

Implement:

```text
STOR
```

Test binary integrity and interrupted uploads.

---

## Phase 7 — Filesystem modification

Implement:

```text
MKD
RMD
DELE
```

and any required compatibility aliases.

---

## Phase 8 — Robustness

Test:

- simultaneous clients;
- repeated connections;
- network interruption;
- aborted transfers;
- resource leakage;
- server stop/start;
- malformed commands.

---

## Phase 9 — Cross-platform compatibility

Explicitly validate:

```text
Windows
Linux
macOS
iOS/iPadOS
```

Record:

- client name;
- client version;
- commands observed;
- success/failure;
- required compatibility workarounds.

---

# Debugging rules

When interoperability fails:

**do not guess.**

First collect evidence.

Log:

```text
FTP command received
FTP response sent
PASV address and port
data connection accepted
transfer start
transfer byte count
socket error / errno
file operation error
transfer completion
```

Use packet captures with Wireshark or tcpdump when necessary.

Compare the actual exchange with a known-good FTP server.

Do not add speculative client-specific hacks without first proving why they are required.

---

# Coding style

Use clear production-quality C.

Formatting:

- Allman brace style
- 2 spaces indentation
- lowerCamelCase for functions and local variables where practical

Example:

```c
static esp_err_t openPassiveSocket(ftp_session_t *session)
{
  if (session == NULL)
  {
    return ESP_ERR_INVALID_ARG;
  }

  ...
}
```

Avoid:

- giant source files;
- giant functions;
- unnecessary macros;
- goto-heavy control flow;
- global mutable session state;
- clever but difficult-to-debug abstractions.

Small cleanup sections using `goto cleanup` are acceptable where this clearly prevents resource leaks.

---

# Documentation

README.md must explain:

- what the component does;
- supported ESP-IDF versions;
- supported filesystems;
- basic integration;
- public API;
- configuration;
- authentication;
- passive port configuration;
- security limitations of FTP;
- tested clients;
- known limitations.

Include a minimal usage example.

---

# Definition of done

The component is not finished merely when it compiles.

It is finished when:

1. it builds cleanly under ESP-IDF;
2. it can expose an externally mounted LittleFS or FATFS VFS;
3. Windows FTP clients can browse, upload and download;
4. Linux FTP clients can browse, upload and download;
5. macOS FTP clients can browse, upload and download;
6. at least one iOS/iPadOS FTP client can browse, upload and download;
7. Passive FTP works reliably;
8. files larger than available RAM transfer correctly;
9. binary files remain byte-for-byte identical;
10. directory creation and deletion work;
11. repeated connections do not leak resources;
12. interrupted transfers do not crash the ESP32;
13. `ftp_server_stop()` releases all resources;
14. the server can be stopped and restarted without rebooting;
15. clients cannot escape the configured VFS root;
16. documentation is sufficient to reuse the component in another ESP-IDF project.

---

# Most important rule

**Prioritize interoperability, simplicity and measured behavior over speculative complexity.**

FTP is an old and well-defined protocol.

If a client disconnects, refuses a directory listing, fails to establish a passive connection or aborts a transfer:

1. inspect the actual protocol exchange;
2. identify the exact command/response or socket behavior causing the problem;
3. compare it with the FTP specification and a known-good server;
4. fix the demonstrated problem;
5. retest all previously working clients.

Do not repeatedly redesign unrelated code based on guesses.

The goal is a small, boring, predictable and robust FTP server.