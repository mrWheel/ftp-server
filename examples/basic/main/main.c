#include "esp_littlefs.h"
#include "esp_log.h"
#include "esp_vfs_fat.h"
#include "ftp_server.h"
#include "wifi_provisioner.h"
#include "wear_levelling.h"
#include "mdns.h"

static const char *TAG = "ftp_basic";
#if !CONFIG_EXAMPLE_FILESYSTEM_LITTLEFS
static wl_handle_t s_wl_handle = WL_INVALID_HANDLE;
#endif

static esp_err_t mount_storage(void)
{
#if CONFIG_EXAMPLE_FILESYSTEM_LITTLEFS
    const esp_vfs_littlefs_conf_t config = {
        .base_path = "/storage",
        .partition_label = "storage",
        .format_if_mount_failed = true,
        .dont_mount = false,
    };
    return esp_vfs_littlefs_register(&config);
#else
    const esp_vfs_fat_mount_config_t config = {
        .format_if_mount_failed = true,
        .max_files = 8,
        .allocation_unit_size = CONFIG_WL_SECTOR_SIZE,
    };
    return esp_vfs_fat_spiflash_mount_rw_wl(
        "/storage", "storage", &config, &s_wl_handle);
#endif
}

static void start_mdns(void)
{
    ESP_ERROR_CHECK(mdns_init());
    ESP_ERROR_CHECK(mdns_hostname_set(CONFIG_EXAMPLE_DEVICE_HOSTNAME));
    ESP_ERROR_CHECK(mdns_instance_name_set("ESP32 FTP server"));
    ESP_ERROR_CHECK(mdns_service_add("FTP server", "_ftp", "_tcp",
                                     CONFIG_EXAMPLE_FTP_PORT, NULL, 0));
}

void app_main(void)
{
    ESP_ERROR_CHECK(mount_storage());

    //-- The provisioner initializes the ESP-IDF network stack and either connects
    //-- with saved credentials or opens its captive provisioning portal.
    wifi_prov_config_t wifi_config = WIFI_PROV_DEFAULT_CONFIG();
    wifi_config.ap_ssid = "FTP-Server-Setup";
    ESP_ERROR_CHECK(wifi_prov_start(&wifi_config));
    wifi_prov_wait_for_connection(portMAX_DELAY);

    start_mdns();

    //-- ftp_server only needs an already-mounted VFS path and a working network.
    ftp_server_config_t ftp_config = FTP_SERVER_DEFAULT_CONFIG();
    ftp_config.base_path = "/storage";
    ftp_config.control_port = CONFIG_EXAMPLE_FTP_PORT;
    ftp_config.max_clients = CONFIG_FTP_SERVER_MAX_CLIENTS;
    ESP_ERROR_CHECK(ftp_server_start(&ftp_config));

    ESP_LOGI(TAG, "FTP server ready at ftp://%s.local:%d/",
             CONFIG_EXAMPLE_DEVICE_HOSTNAME, CONFIG_EXAMPLE_FTP_PORT);
}
