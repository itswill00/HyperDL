/*
 * HyperDL Native IPC & Engine Bridge (libhyperdl.so)
 * High-performance C executable replacing legacy shell wrappers.
 *
 * Copyright (C) 2026 @itswill00
 * Licensed under the GNU General Public License v3.0
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <dirent.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/statvfs.h>
#include <sys/wait.h>
#include <errno.h>

#define STATUS_FILE    "/data/local/tmp/hyperdl_status.json"
#define PID_FILE       "/data/local/tmp/hyperdl.pid"
#define CLIP_PID_FILE  "/data/local/tmp/hyperdl_clip.pid"
#define LOG_FILE       "/data/local/tmp/hyperdl_engine.log"
#define CONF_DIR       "/data/adb/hyperdl"
#define COOKIES_FILE   "/data/adb/hyperdl/cookies.txt"
#define AUTODL_FILE    "/data/adb/hyperdl/autodl.enabled"
#define OUTDIR         "/storage/emulated/0/Download/HyperDL"

static const char *PYTHON_PATHS[] = {
    "/data/data/com.termux/files/usr/bin/python3",
    "/system/bin/python3",
    "/system/xbin/python3",
    "/data/adb/modules/python/bin/python3",
    "/data/adb/ap/bin/python3",
    "/data/adb/ksu/bin/python3",
    NULL
};

/* Base64 Encoding Table */
static const char b64_table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

static char *base64_encode(const unsigned char *data, size_t input_len) {
    size_t output_len = 4 * ((input_len + 2) / 3);
    char *encoded = malloc(output_len + 1);
    if (!encoded) return NULL;

    size_t i, j;
    for (i = 0, j = 0; i < input_len;) {
        uint32_t octet_a = i < input_len ? data[i++] : 0;
        uint32_t octet_b = i < input_len ? data[i++] : 0;
        uint32_t octet_c = i < input_len ? data[i++] : 0;
        uint32_t triple = (octet_a << 16) + (octet_b << 8) + octet_c;

        encoded[j++] = b64_table[(triple >> 18) & 0x3F];
        encoded[j++] = b64_table[(triple >> 12) & 0x3F];
        encoded[j++] = (i > input_len + 1) ? '=' : b64_table[(triple >> 6) & 0x3F];
        encoded[j++] = (i > input_len) ? '=' : b64_table[triple & 0x3F];
    }
    encoded[output_len] = '\0';
    return encoded;
}

static unsigned char *base64_decode(const char *data, size_t input_len, size_t *output_len) {
    if (input_len % 4 != 0) return NULL;

    size_t out_len = input_len / 4 * 3;
    if (input_len > 0 && data[input_len - 1] == '=') out_len--;
    if (input_len > 1 && data[input_len - 2] == '=') out_len--;

    unsigned char *decoded = malloc(out_len + 1);
    if (!decoded) return NULL;

    int dtable[256];
    memset(dtable, 0x80, 256);
    for (int i = 0; i < 64; i++) dtable[(unsigned char)b64_table[i]] = i;
    dtable['='] = 0;

    size_t i, j;
    for (i = 0, j = 0; i < input_len;) {
        uint32_t a = data[i] == '=' ? 0 : dtable[(unsigned char)data[i]]; i++;
        uint32_t b = data[i] == '=' ? 0 : dtable[(unsigned char)data[i]]; i++;
        uint32_t c = data[i] == '=' ? 0 : dtable[(unsigned char)data[i]]; i++;
        uint32_t d = data[i] == '=' ? 0 : dtable[(unsigned char)data[i]]; i++;
        uint32_t triple = (a << 18) + (b << 12) + (c << 6) + d;

        if (j < out_len) decoded[j++] = (triple >> 16) & 0xFF;
        if (j < out_len) decoded[j++] = (triple >> 8) & 0xFF;
        if (j < out_len) decoded[j++] = triple & 0xFF;
    }
    decoded[out_len] = '\0';
    *output_len = out_len;
    return decoded;
}

static const char *find_python(void) {
    for (int i = 0; PYTHON_PATHS[i] != NULL; i++) {
        if (access(PYTHON_PATHS[i], X_OK) == 0) {
            return PYTHON_PATHS[i];
        }
    }
    return NULL;
}

static void ensure_directories(void) {
    mkdir(OUTDIR, 0755);
    mkdir(CONF_DIR, 0755);
    mkdir("/data/local/tmp", 0777);
}

static void format_file_size(off_t bytes, char *buf, size_t buf_len) {
    if (bytes >= 1024 * 1024 * 1024) {
        snprintf(buf, buf_len, "%.1f GB", (double)bytes / (1024 * 1024 * 1024));
    } else if (bytes >= 1024 * 1024) {
        snprintf(buf, buf_len, "%.1f MB", (double)bytes / (1024 * 1024));
    } else if (bytes >= 1024) {
        snprintf(buf, buf_len, "%.0f KB", (double)bytes / 1024);
    } else {
        snprintf(buf, buf_len, "%ld B", (long)bytes);
    }
}

/* Actions */

static void cmd_status(void) {
    FILE *f = fopen(STATUS_FILE, "r");
    if (!f) {
        printf("{\"status\":\"idle\",\"percent\":0}\n");
        return;
    }
    char buf[1024];
    size_t r = fread(buf, 1, sizeof(buf) - 1, f);
    fclose(f);
    buf[r] = '\0';
    printf("%s\n", buf);
}

static void cmd_download(const char *url, const char *fmt) {
    ensure_directories();

    /* Kill previous running download instance */
    FILE *pf = fopen(PID_FILE, "r");
    if (pf) {
        pid_t old_pid = 0;
        if (fscanf(pf, "%d", &old_pid) == 1 && old_pid > 1) {
            kill(old_pid, SIGKILL);
        }
        fclose(pf);
        unlink(PID_FILE);
    }

    const char *python_bin = find_python();
    if (!python_bin) {
        FILE *sf = fopen(STATUS_FILE, "w");
        if (sf) {
            fputs("{\"status\":\"error\",\"error\":\"Python 3 runtime not found on system\"}\n", sf);
            fclose(sf);
        }
        printf("{\"error\":\"python_not_found\"}\n");
        return;
    }

    /* Resolve path to downloader.py */
    char engine_py[512];
    if (access("/data/adb/modules/hyperdl/engine/downloader.py", R_OK) == 0) {
        snprintf(engine_py, sizeof(engine_py), "/data/adb/modules/hyperdl/engine/downloader.py");
    } else {
        snprintf(engine_py, sizeof(engine_py), "/data/data/com.termux/files/home/HyperDL_Module/engine/downloader.py");
    }

    /* Set resolving status */
    FILE *sf = fopen(STATUS_FILE, "w");
    if (sf) {
        fputs("{\"status\":\"resolving\",\"percent\":0,\"title\":\"Connecting to platform...\"}\n", sf);
        fclose(sf);
    }

    pid_t pid = fork();
    if (pid < 0) {
        printf("{\"error\":\"fork_failed\"}\n");
        return;
    }

    if (pid == 0) {
        /* Child Process */
        int log_fd = open(LOG_FILE, O_WRONLY | O_CREAT | O_APPEND, 0644);
        if (log_fd >= 0) {
            dup2(log_fd, STDOUT_FILENO);
            dup2(log_fd, STDERR_FILENO);
            close(log_fd);
        }

        /* Export clean runtime environment */
        if (strstr(python_bin, "com.termux")) {
            setenv("PATH", "/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin", 1);
            setenv("LD_LIBRARY_PATH", "/data/data/com.termux/files/usr/lib", 1);
            setenv("HOME", "/data/data/com.termux/files/home", 1);
            setenv("PREFIX", "/data/data/com.termux/files/usr", 1);
        }

        execl(python_bin, "python3", engine_py, url, "--format", fmt ? fmt : "video", "--outdir", OUTDIR, (char *)NULL);
        _exit(127);
    }

    /* Parent Process */
    FILE *npf = fopen(PID_FILE, "w");
    if (npf) {
        fprintf(npf, "%d\n", pid);
        fclose(npf);
    }

    printf("{\"status\":\"started\",\"pid\":%d}\n", pid);
}

static void cmd_list(void) {
    DIR *d = opendir(OUTDIR);
    if (!d) {
        printf("[]\n");
        return;
    }

    printf("[\n");
    struct dirent *entry;
    int first = 1;
    char full_path[1024];
    struct stat st;
    char size_str[32];

    while ((entry = readdir(d)) != NULL) {
        if (entry->d_name[0] == '.') continue;

        snprintf(full_path, sizeof(full_path), "%s/%s", OUTDIR, entry->d_name);
        if (stat(full_path, &st) == 0 && S_ISREG(st.st_mode)) {
            format_file_size(st.st_size, size_str, sizeof(size_str));
            const char *dot = strrchr(entry->d_name, '.');
            const char *ext = dot ? dot + 1 : "";

            if (!first) printf(",\n");
            first = 0;

            printf("  {\"name\":\"%s\",\"size\":\"%s\",\"ext\":\"%s\",\"path\":\"%s\"}",
                   entry->d_name, size_str, ext, full_path);
        }
    }
    printf("\n]\n");
    closedir(d);
}

static void cmd_delete(const char *path) {
    if (!path || !*path) {
        printf("{\"success\":false,\"error\":\"missing_path\"}\n");
        return;
    }
    if (unlink(path) == 0) {
        printf("{\"success\":true}\n");
    } else {
        printf("{\"success\":false,\"error\":\"%s\"}\n", strerror(errno));
    }
}

static void cmd_info(void) {
    char storage_free[32] = "Unknown";
    struct statvfs vfs;
    if (statvfs("/data", &vfs) == 0) {
        double free_gb = (double)(vfs.f_bavail * vfs.f_frsize) / (1024.0 * 1024.0 * 1024.0);
        snprintf(storage_free, sizeof(storage_free), "%.0f GB", free_gb);
    }

    const char *python_bin = find_python();
    int has_cookies = (access(COOKIES_FILE, F_OK) == 0);

    printf("{\"storage_free\":\"%s\",\"outdir\":\"%s\",\"python\":\"%s\",\"has_cookies\":%s}\n",
           storage_free, OUTDIR, python_bin ? python_bin : "None", has_cookies ? "true" : "false");
}

static void cmd_get_cookies(void) {
    FILE *f = fopen(COOKIES_FILE, "rb");
    if (!f) {
        printf("{\"exists\":false,\"lines\":0,\"content_b64\":\"\"}\n");
        return;
    }

    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (sz <= 0) {
        fclose(f);
        printf("{\"exists\":false,\"lines\":0,\"content_b64\":\"\"}\n");
        return;
    }

    unsigned char *buf = malloc(sz);
    if (!buf) {
        fclose(f);
        printf("{\"exists\":false,\"lines\":0,\"content_b64\":\"\"}\n");
        return;
    }

    size_t read_bytes = fread(buf, 1, sz, f);
    fclose(f);

    int lines = 0;
    for (size_t i = 0; i < read_bytes; i++) {
        if (buf[i] == '\n') lines++;
    }

    char *b64 = base64_encode(buf, read_bytes);
    free(buf);

    if (b64) {
        printf("{\"exists\":true,\"lines\":%d,\"content_b64\":\"%s\"}\n", lines, b64);
        free(b64);
    } else {
        printf("{\"exists\":false,\"lines\":0,\"content_b64\":\"\"}\n");
    }
}

static void cmd_save_cookies(const char *b64_data) {
    ensure_directories();

    if (!b64_data || !*b64_data) {
        unlink(COOKIES_FILE);
        printf("{\"success\":true,\"lines\":0}\n");
        return;
    }

    size_t out_len = 0;
    unsigned char *decoded = base64_decode(b64_data, strlen(b64_data), &out_len);
    if (!decoded) {
        printf("{\"success\":false,\"error\":\"decode_failed\"}\n");
        return;
    }

    FILE *f = fopen(COOKIES_FILE, "wb");
    if (!f) {
        free(decoded);
        printf("{\"success\":false,\"error\":\"open_failed\"}\n");
        return;
    }

    fwrite(decoded, 1, out_len, f);
    fclose(f);
    chmod(COOKIES_FILE, 0600);

    int lines = 0;
    for (size_t i = 0; i < out_len; i++) {
        if (decoded[i] == '\n') lines++;
    }
    free(decoded);

    printf("{\"success\":true,\"lines\":%d}\n", lines);
}

static void cmd_clear_cookies(void) {
    unlink(COOKIES_FILE);
    printf("{\"success\":true}\n");
}

static void cmd_get_logs(void) {
    FILE *f = fopen(LOG_FILE, "r");
    if (!f) {
        printf("No log entries recorded yet.\n");
        return;
    }

    /* Print tail 60 lines */
    char line[1024];
    char ring[60][1024];
    int count = 0;

    while (fgets(line, sizeof(line), f)) {
        strncpy(ring[count % 60], line, sizeof(ring[0]));
        count++;
    }
    fclose(f);

    int start = count > 60 ? count % 60 : 0;
    int total = count > 60 ? 60 : count;

    for (int i = 0; i < total; i++) {
        fputs(ring[(start + i) % 60], stdout);
    }
}

static void cmd_toggle_autodl(const char *val) {
    ensure_directories();
    if (val && (strcmp(val, "1") == 0 || strcmp(val, "on") == 0)) {
        int fd = open(AUTODL_FILE, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (fd >= 0) close(fd);
        printf("{\"autodl\":true}\n");
    } else {
        unlink(AUTODL_FILE);
        printf("{\"autodl\":false}\n");
    }
}

static void cmd_get_autodl(void) {
    int active = (access(AUTODL_FILE, F_OK) == 0);
    printf("{\"autodl\":%s}\n", active ? "true" : "false");
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        printf("Usage: %s <action> [args...]\n", argv[0]);
        return 1;
    }

    const char *action = argv[1];

    if (strcmp(action, "status") == 0) {
        cmd_status();
    } else if (strcmp(action, "download") == 0) {
        cmd_download(argc > 2 ? argv[2] : "", argc > 3 ? argv[3] : "video");
    } else if (strcmp(action, "list") == 0) {
        cmd_list();
    } else if (strcmp(action, "delete") == 0) {
        cmd_delete(argc > 2 ? argv[2] : "");
    } else if (strcmp(action, "info") == 0) {
        cmd_info();
    } else if (strcmp(action, "get_cookies") == 0) {
        cmd_get_cookies();
    } else if (strcmp(action, "save_cookies") == 0) {
        cmd_save_cookies(argc > 2 ? argv[2] : "");
    } else if (strcmp(action, "clear_cookies") == 0) {
        cmd_clear_cookies();
    } else if (strcmp(action, "get_logs") == 0) {
        cmd_get_logs();
    } else if (strcmp(action, "toggle_autodl") == 0) {
        cmd_toggle_autodl(argc > 2 ? argv[2] : "0");
    } else if (strcmp(action, "get_autodl") == 0) {
        cmd_get_autodl();
    } else {
        printf("{\"error\":\"unknown_action\"}\n");
        return 1;
    }

    return 0;
}
