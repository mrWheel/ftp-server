# ESP-IDF FTP server example

Complete VSCode/ESP-IDF project containing a reusable native C FTP server. The
component shares an already-mounted VFS directory; it does not own Wi-Fi or the
filesystem. The example application uses LittleFS, Wi-Fi provisioning and local
network OTA upload.

## Build

```bash
idf.py set-target esp32
idf.py build
idf.py flash monitor
```

On first boot, join `FTP-Server-Setup` and use the captive portal. Then connect
with FileZilla to `ftp-server.local` in passive mode. The server does not
require a username or password.

## Switch to FATFS

1. Open `idf.py menuconfig` and select **FTP server example > FATFS**.
2. Set **Partition Table > Custom partition CSV file** to
   `partitions_fatfs.csv`.
3. Clean and rebuild. The FTP component and its `/storage` configuration do not
   change.

To switch back, select LittleFS and `partitions_littlefs.csv`.

## FTP commands

USER, PASS, SYST, FEAT, PWD/XPWD, CWD, CDUP, TYPE, PASV, EPSV, LIST, NLST,
SIZE, MDTM, REST, RETR, STOR, MKD/XMKD, RMD/XRMD, DELE, RNFR/RNTO, OPTS,
ABOR, NOOP and QUIT.

Paths are normalized in a per-session virtual working directory and are always
resolved below the configured root. File transfers stream through a fixed-size
buffer. Each filesystem operation checks its real result before replying.

## Notes

- FTP is unencrypted. Use it only on a trusted LAN.
- Port 21 can require elevated privileges on desktop-hosted tests; use 2121 there.
- The included partitions require at least 4 MB flash slot.
- `ftp_server_stop()` stops accepting connections. Existing sessions observe the
  stop flag and close; the current public API is designed for restartability.
