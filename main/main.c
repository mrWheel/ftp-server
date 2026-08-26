#include <stdio.h>
#include "esp_check.h"
#include "esp_littlefs.h"
#include "esp_log.h"
#include "esp_vfs_fat.h"
#include "ftp_server.h"
#include "wifi_provisioner.h"
#include "wear_levelling.h"

static const char *TAG = "ftp_example";
static wl_handle_t wl_handle = WL_INVALID_HANDLE;

static esp_err_t mount_storage(void)
{
#if CONFIG_APP_FILESYSTEM_LITTLEFS
    esp_vfs_littlefs_conf_t conf = {
        .base_path = "/storage", .partition_label = "storage",
        .format_if_mount_failed = true, .dont_mount = false,
    };
    return esp_vfs_littlefs_register(&conf);
#else
    const esp_vfs_fat_mount_config_t conf = {
        .format_if_mount_failed = true, .max_files = 8,
        .allocation_unit_size = CONFIG_WL_SECTOR_SIZE,
    };
    return esp_vfs_fat_spiflash_mount_rw_wl("/storage", "storage", &conf, &wl_handle);
#endif
}

void app_main(void)
{
    ESP_ERROR_CHECK(mount_storage());

    wifi_prov_config_t wifi = WIFI_PROV_DEFAULT_CONFIG();
    wifi.ap_ssid = "FTP-Server-Setup";
    ESP_ERROR_CHECK(wifi_prov_start(&wifi));
    wifi_prov_wait_for_connection(portMAX_DELAY);

    ftp_server_config_t ftp = FTP_SERVER_DEFAULT_CONFIG();
    ftp.base_path = "/storage";
    ftp.user = CONFIG_APP_FTP_USER;
    ftp.password = CONFIG_APP_FTP_PASSWORD;
    ftp.control_port = CONFIG_APP_FTP_PORT;
    ESP_ERROR_CHECK(ftp_server_start(&ftp));

    ESP_LOGI(TAG, "FTP ready: ftp://%s.local:%d/", CONFIG_APP_DEVICE_HOSTNAME,
             CONFIG_APP_FTP_PORT);
}
