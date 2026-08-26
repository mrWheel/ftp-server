# Basic FTP server example

This ESP-IDF example mounts `/storage`, provisions Wi-Fi, starts the reusable
`ftp_server` component.

The archive is intended to be merged into the root of the `ftp-server` project:

```text
ftp-server/
├── components/ftp_server/
└── examples/basic/
```

The local dependency in `main/idf_component.yml` deliberately resolves
`../../../components/ftp_server`.

## Build and flash

From the `ftp-server` project root:

```bash
idf.py -C examples/basic set-target esp32
idf.py -C examples/basic build
idf.py -C examples/basic flash monitor
```

Use `esp32s3` instead of `esp32` for an ESP32-S3.

On first boot, connect to the `FTP-Server-Setup` access point and complete the
captive portal. Afterwards connect in passive mode to `ftp-server.local`; no
username or password is required.

Hostname, filesystem and FTP port are configurable with:

```bash
idf.py -C examples/basic menuconfig
```

## FATFS

Select **FTP server basic example > FATFS with wear levelling**, then set the
custom partition filename to `partitions_fatfs.csv`. Clean and rebuild. To return
to LittleFS, select LittleFS and `partitions_littlefs.csv`.

FTP is an unencrypted development service. Use it only on a trusted LAN.
