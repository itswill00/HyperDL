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
#include <dlfcn.h>
#include "embedded_engine.h"

#define STATUS_FILE        "/data/local/tmp/hyperdl_status.json"
#define PID_FILE           "/data/local/tmp/hyperdl.pid"
#define LOG_FILE           "/data/local/tmp/hyperdl_engine.log"
#define CONF_DIR           "/data/adb/hyperdl"
#define ACTIVE_TASK_FILE   "/data/adb/hyperdl/active_task.json"
#define COOKIES_FILE       "/data/adb/hyperdl/cookies.txt"
#define AUTODL_FILE        "/data/adb/hyperdl/autodl.enabled"
#define OUTDIR             "/storage/emulated/0/Download/HyperDL"

static const char *PYTHON_PATHS[] = {
    "/data/adb/modules/hyperdl/runtime/bin/python3",
    "/data/adb/modules_update/hyperdl/runtime/bin/python3",
    "/data/data/com.termux/files/home/HyperDL_Module/runtime/bin/python3",
    "/system/bin/python3",
    "/system/xbin/python3",
    "/data/adb/modules/python/bin/python3",
    "/data/adb/ap/bin/python3",
    "/data/adb/ksu/bin/python3",
    NULL
};

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
    mkdir(OUTDIR, 0777);
    chmod(OUTDIR, 0777);
    mkdir(CONF_DIR, 0777);
    chmod(CONF_DIR, 0777);
    mkdir("/data/local/tmp", 0777);
    chmod("/data/local/tmp", 0777);
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

static void cmd_status(void) {
    char buf[2048] = "";
    int has_status = 0;

    FILE *f = fopen(STATUS_FILE, "r");
    if (f) {
        size_t r = fread(buf, 1, sizeof(buf) - 1, f);
        fclose(f);
        buf[r] = '\0';
        has_status = (r > 0);
    }

    FILE *pf = fopen(PID_FILE, "r");
    pid_t pid = 0;
    int pid_alive = 0;
    if (pf) {
        if (fscanf(pf, "%d", &pid) == 1 && pid > 1) {
            if (kill(pid, 0) == 0) {
                pid_alive = 1;
            }
        }
        fclose(pf);
    }

    if (pid > 1 && !pid_alive) {
        unlink(PID_FILE);
    }

    if (pid_alive && has_status) {
        printf("%s\n", buf);
        return;
    }

    // Process is not running or STATUS_FILE was wiped on reboot.
    // Check persistent ACTIVE_TASK_FILE in /data/adb/hyperdl/active_task.json
    FILE *af = fopen(ACTIVE_TASK_FILE, "r");
    if (af) {
        char abuf[2048];
        size_t ar = fread(abuf, 1, sizeof(abuf) - 1, af);
        fclose(af);
        abuf[ar] = '\0';

        if (strstr(abuf, "\"downloading\"") || strstr(abuf, "\"resolving\"") || strstr(abuf, "\"paused\"")) {
            if (!strstr(abuf, "\"status\":\"paused\"")) {
                char *sp = strstr(abuf, "\"status\":\"downloading\"");
                if (sp) {
                    memcpy(sp, "\"status\":\"paused\"     ", 22);
                } else {
                    sp = strstr(abuf, "\"status\":\"resolving\"");
                    if (sp) {
                        memcpy(sp, "\"status\":\"paused\"   ", 20);
                    }
                }
                FILE *waf = fopen(ACTIVE_TASK_FILE, "w");
                if (waf) { fputs(abuf, waf); fclose(waf); chmod(ACTIVE_TASK_FILE, 0666); }
                FILE *wsf = fopen(STATUS_FILE, "w");
                if (wsf) { fputs(abuf, wsf); fclose(wsf); chmod(STATUS_FILE, 0666); }
            }
            printf("%s\n", abuf);
            return;
        }
    }

    if (has_status && (strstr(buf, "\"completed\"") || strstr(buf, "\"error\"") || strstr(buf, "\"paused\""))) {
        printf("%s\n", buf);
        return;
    }

    printf("{\"status\":\"idle\",\"percent\":0}\n");
}

static void cmd_download(const char *url, const char *fmt, const char *format_id, const char *height) {
    ensure_directories();

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

    const char *bundle_path = NULL;
    if (access("/data/adb/modules/hyperdl/system/bin/hyperdl.bundle", R_OK) == 0) {
        bundle_path = "/data/adb/modules/hyperdl/system/bin/hyperdl.bundle";
    } else if (access("/data/adb/modules_update/hyperdl/system/bin/hyperdl.bundle", R_OK) == 0) {
        bundle_path = "/data/adb/modules_update/hyperdl/system/bin/hyperdl.bundle";
    } else if (access("/data/data/com.termux/files/home/HyperDL_Module/system/bin/hyperdl.bundle", R_OK) == 0) {
        bundle_path = "/data/data/com.termux/files/home/HyperDL_Module/system/bin/hyperdl.bundle";
    }

    FILE *sf = fopen(STATUS_FILE, "w");
    if (sf) {
        fprintf(sf, "{\"status\":\"resolving\",\"percent\":0,\"title\":\"Connecting to platform...\",\"url\":\"%s\",\"fmt\":\"%s\"}\n",
                url ? url : "", fmt ? fmt : "video");
        fclose(sf);
        chmod(STATUS_FILE, 0666);
    }
    FILE *af = fopen(ACTIVE_TASK_FILE, "w");
    if (af) {
        fprintf(af, "{\"status\":\"resolving\",\"percent\":0,\"title\":\"Connecting to platform...\",\"url\":\"%s\",\"fmt\":\"%s\"}\n",
                url ? url : "", fmt ? fmt : "video");
        fclose(af);
        chmod(ACTIVE_TASK_FILE, 0666);
    }

    pid_t pid = fork();
    if (pid < 0) {
        printf("{\"error\":\"fork_failed\"}\n");
        return;
    }

    if (pid == 0) {
        setsid();
        signal(SIGHUP, SIG_IGN);

        // Protect background download from OEM LMK task killers (HyperOS, ColorOS, XOS)
        int oom_fd = open("/proc/self/oom_score_adj", O_WRONLY);
        if (oom_fd >= 0) {
            write(oom_fd, "-900\n", 5);
            close(oom_fd);
        }

        int log_fd = open(LOG_FILE, O_WRONLY | O_CREAT | O_APPEND, 0666);
        if (log_fd >= 0) {
            fchmod(log_fd, 0666);
            dup2(log_fd, STDOUT_FILENO);
            dup2(log_fd, STDERR_FILENO);
            close(log_fd);
        }

        if (strstr(python_bin, "runtime")) {
            char moddir[512];
            const char *p = strstr(python_bin, "/bin/python3");
            if (p) {
                size_t len = p - python_bin;
                snprintf(moddir, sizeof(moddir), "%.*s", (int)len, python_bin);
                char libdir[550], pypath[650], cacert[550], path_env[1024];
                snprintf(libdir, sizeof(libdir), "%s/lib", moddir);
                snprintf(pypath, sizeof(pypath), "%s/lib/python314.zip:%s/lib/python3.14/lib-dynload", moddir, moddir);
                snprintf(cacert, sizeof(cacert), "%s/lib/cacert.pem", moddir);
                snprintf(path_env, sizeof(path_env), "%s/bin:/data/adb/modules/hyperdl/system/bin:/system/bin:/system/xbin", moddir);

                setenv("PATH", path_env, 1);
                setenv("PYTHONHOME", moddir, 1);
                setenv("PYTHONPATH", pypath, 1);
                setenv("LD_LIBRARY_PATH", libdir, 1);
                setenv("SSL_CERT_FILE", cacert, 1);
            }
        } else if (strstr(python_bin, "com.termux")) {
            setenv("PATH", "/data/data/com.termux/files/usr/bin:/system/bin:/system/xbin", 1);
            setenv("LD_LIBRARY_PATH", "/data/data/com.termux/files/usr/lib", 1);
            setenv("HOME", "/data/data/com.termux/files/home", 1);
            setenv("PREFIX", "/data/data/com.termux/files/usr", 1);
        } else if (strstr(python_bin, "py2droid")) {
            setenv("PYTHONHOME", "/data/adb/py2droid/usr", 1);
            setenv("PATH", "/data/adb/py2droid/usr/bin:/system/bin:/system/xbin", 1);
            setenv("LD_LIBRARY_PATH", "/data/adb/py2droid/usr/lib", 1);
            setenv("SSL_CERT_FILE", "/data/adb/py2droid/usr/etc/ssl/cacert.pem", 1);
        }

        char fid_arg[256] = "";
        char ht_arg[64] = "";
        if (format_id && *format_id) {
            snprintf(fid_arg, sizeof(fid_arg), "--format-id=%s", format_id);
        }
        if (height && *height) {
            snprintf(ht_arg, sizeof(ht_arg), "--height=%s", height);
        }

        if (bundle_path) {
            if (fid_arg[0])
                execl(python_bin, python_bin, bundle_path, "download", url, "--format", fmt ? fmt : "video", "--outdir", OUTDIR, fid_arg, (char *)NULL);
            else if (ht_arg[0])
                execl(python_bin, python_bin, bundle_path, "download", url, "--format", fmt ? fmt : "video", "--outdir", OUTDIR, ht_arg, (char *)NULL);
            else
                execl(python_bin, python_bin, bundle_path, "download", url, "--format", fmt ? fmt : "video", "--outdir", OUTDIR, (char *)NULL);
        } else {
            char launcher[sizeof(EMBEDDED_ENGINE_B64) + 128];
            snprintf(launcher, sizeof(launcher),
                     "import zlib,base64;exec(zlib.decompress(base64.b64decode('%s')))",
                     EMBEDDED_ENGINE_B64);
            if (fid_arg[0])
                execl(python_bin, python_bin, "-c", launcher, "download", url, "--format", fmt ? fmt : "video", "--outdir", OUTDIR, fid_arg, (char *)NULL);
            else if (ht_arg[0])
                execl(python_bin, python_bin, "-c", launcher, "download", url, "--format", fmt ? fmt : "video", "--outdir", OUTDIR, ht_arg, (char *)NULL);
            else
                execl(python_bin, python_bin, "-c", launcher, "download", url, "--format", fmt ? fmt : "video", "--outdir", OUTDIR, (char *)NULL);
        }
        fprintf(stderr, "HyperDL child exec failed: %s (%s)\n", strerror(errno), python_bin);
        fflush(stderr);
        _exit(127);
    }

    FILE *npf = fopen(PID_FILE, "w");
    if (npf) {
        fprintf(npf, "%d\n", pid);
        fclose(npf);
        chmod(PID_FILE, 0666);
    }

    printf("{\"status\":\"started\",\"pid\":%d}\n", pid);
}

static void cmd_probe(const char *url) {
    if (!url || !*url) {
        printf("{\"error\":\"missing_url\"}\n");
        return;
    }

    const char *python_bin = find_python();
    if (!python_bin) {
        printf("{\"error\":\"python_not_found\"}\n");
        return;
    }

    const char *bundle_path = NULL;
    if (access("/data/adb/modules/hyperdl/system/bin/hyperdl.bundle", R_OK) == 0) {
        bundle_path = "/data/adb/modules/hyperdl/system/bin/hyperdl.bundle";
    } else if (access("/data/adb/modules_update/hyperdl/system/bin/hyperdl.bundle", R_OK) == 0) {
        bundle_path = "/data/adb/modules_update/hyperdl/system/bin/hyperdl.bundle";
    } else if (access("/data/data/com.termux/files/home/HyperDL_Module/system/bin/hyperdl.bundle", R_OK) == 0) {
        bundle_path = "/data/data/com.termux/files/home/HyperDL_Module/system/bin/hyperdl.bundle";
    }

    if (strstr(python_bin, "runtime")) {
        char moddir[512];
        const char *p = strstr(python_bin, "/bin/python3");
        if (p) {
            size_t len = p - python_bin;
            snprintf(moddir, sizeof(moddir), "%.*s", (int)len, python_bin);
            char libdir[550], pypath[650], cacert[550], path_env[1024];
            snprintf(libdir, sizeof(libdir), "%s/lib", moddir);
            snprintf(pypath, sizeof(pypath), "%s/lib/python314.zip:%s/lib/python3.14/lib-dynload", moddir, moddir);
            snprintf(cacert, sizeof(cacert), "%s/lib/cacert.pem", moddir);
            snprintf(path_env, sizeof(path_env), "%s/bin:/data/adb/modules/hyperdl/system/bin:/system/bin:/system/xbin", moddir);

            setenv("PATH", path_env, 1);
            setenv("PYTHONHOME", moddir, 1);
            setenv("PYTHONPATH", pypath, 1);
            setenv("LD_LIBRARY_PATH", libdir, 1);
            setenv("SSL_CERT_FILE", cacert, 1);
        }
    }

    int pipefd[2];
    if (pipe(pipefd) < 0) {
        printf("{\"error\":\"pipe_failed\"}\n");
        return;
    }

    pid_t pid = fork();
    if (pid < 0) {
        printf("{\"error\":\"fork_failed\"}\n");
        return;
    }

    if (pid == 0) {
        nice(19);
        close(pipefd[0]);
        dup2(pipefd[1], STDOUT_FILENO);
        int dev_null = open("/dev/null", O_WRONLY);
        if (dev_null >= 0) {
            dup2(dev_null, STDERR_FILENO);
            close(dev_null);
        }
        close(pipefd[1]);

        if (bundle_path) {
            execl(python_bin, python_bin, bundle_path, "probe", url, (char *)NULL);
        } else {
            char launcher[sizeof(EMBEDDED_ENGINE_B64) + 128];
            snprintf(launcher, sizeof(launcher),
                     "import zlib,base64;exec(zlib.decompress(base64.b64decode('%s')))",
                     EMBEDDED_ENGINE_B64);
            execl(python_bin, python_bin, "-c", launcher, "probe", url, (char *)NULL);
        }
        _exit(127);
    }

    close(pipefd[1]);

    char output[65536] = "";
    size_t total = 0;
    ssize_t n;
    while (total < sizeof(output) - 1 && (n = read(pipefd[0], output + total, sizeof(output) - total - 1)) > 0) {
        total += n;
    }
    output[total] = '\0';
    close(pipefd[0]);

    int status;
    waitpid(pid, &status, 0);

    if (total > 0) {
        printf("%s\n", output);
    } else {
        printf("{\"resolutions\":[]}\n");
    }
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

static void cmd_delete(int count, char **paths) {
    if (count <= 0) {
        printf("{\"success\":false,\"error\":\"missing_path\"}\n");
        return;
    }
    int deleted = 0;
    for (int i = 0; i < count; i++) {
        const char *path = paths[i];
        if (!path || !*path) continue;
        if (unlink(path) == 0) {
            deleted++;
            char scan_cmd[1024];
            snprintf(scan_cmd, sizeof(scan_cmd),
                     "(content delete --uri content://media/external/file --where \"_data='%s'\" >/dev/null 2>&1; "
                     "am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d \"file://%s\" >/dev/null 2>&1) &",
                     path, path);
            system(scan_cmd);
        }
    }
    if (deleted > 0) {
        printf("{\"success\":true,\"deleted\":%d}\n", deleted);
    } else {
        printf("{\"success\":false,\"error\":\"%s\"}\n", strerror(errno));
    }
}

static void cmd_open_folder(void) {
    ensure_directories();
    system("(am start -a android.intent.action.VIEW -d \"content://com.android.externalstorage.documents/document/primary%3ADownload%2FHyperDL\" -t \"resource/folder\" -f 0x10000000 >/dev/null 2>&1 || am start -a android.intent.action.VIEW -d \"file:///storage/emulated/0/Download/HyperDL\" -t \"resource/folder\" -f 0x10000000 >/dev/null 2>&1) &");
    printf("{\"success\":true}\n");
}

typedef void sqlite3;
typedef void sqlite3_stmt;

typedef int (*fn_open_v2)(const char *, sqlite3 **, int, const char *);
typedef int (*fn_prepare_v2)(sqlite3 *, const char *, int, sqlite3_stmt **, const char **);
typedef int (*fn_bind_text)(sqlite3_stmt *, int, const char *, int, void(*)(void*));
typedef int (*fn_step)(sqlite3_stmt *);
typedef long long (*fn_col_int64)(sqlite3_stmt *, int);
typedef int (*fn_finalize)(sqlite3_stmt *);
typedef int (*fn_close)(sqlite3 *);

static long long query_sqlite_media_id(const char *path) {
    static const char *lib_paths[] = {
        "/system/lib64/libsqlite.so",
        "/system/lib/libsqlite.so",
        "/apex/com.android.runtime/lib64/bionic/libsqlite.so",
        "/apex/com.android.runtime/lib/bionic/libsqlite.so",
        NULL
    };

    void *lib = NULL;
    for (int i = 0; lib_paths[i]; i++) {
        lib = dlopen(lib_paths[i], RTLD_NOW);
        if (lib) break;
    }
    if (!lib) return -1;

    fn_open_v2 s_open = (fn_open_v2)dlsym(lib, "sqlite3_open_v2");
    fn_prepare_v2 s_prep = (fn_prepare_v2)dlsym(lib, "sqlite3_prepare_v2");
    fn_bind_text s_bind = (fn_bind_text)dlsym(lib, "sqlite3_bind_text");
    fn_step s_step = (fn_step)dlsym(lib, "sqlite3_step");
    fn_col_int64 s_col = (fn_col_int64)dlsym(lib, "sqlite3_column_int64");
    fn_finalize s_fin = (fn_finalize)dlsym(lib, "sqlite3_finalize");
    fn_close s_close = (fn_close)dlsym(lib, "sqlite3_close");

    if (!s_open || !s_prep || !s_bind || !s_step || !s_col || !s_fin || !s_close) {
        dlclose(lib);
        return -1;
    }

    static const char *dbs[] = {
        "/data/data/com.google.android.providers.media.module/databases/external.db",
        "/data/data/com.android.providers.media.module/databases/external.db",
        "/data/data/com.android.providers.media/databases/external.db",
        "/data/user_de/0/com.google.android.providers.media.module/databases/external.db",
        "/data/user_de/0/com.android.providers.media.module/databases/external.db",
        NULL
    };

    long long id = -1;
    for (int i = 0; dbs[i]; i++) {
        sqlite3 *db = NULL;
        if (s_open(dbs[i], &db, 0x00000001, NULL) == 0 && db) {
            sqlite3_stmt *stmt = NULL;
            const char *sql = "SELECT _id FROM files WHERE _data = ? LIMIT 1;";
            if (s_prep(db, sql, -1, &stmt, NULL) == 0 && stmt) {
                s_bind(stmt, 1, path, -1, (void*)0);
                if (s_step(stmt) == 100) {
                    id = s_col(stmt, 0);
                }
                s_fin(stmt);
            }
            s_close(db);
            if (id > 0) break;
        }
    }

    dlclose(lib);
    return id;
}

static void cmd_open(const char *path) {
    if (!path || !*path) {
        printf("{\"success\":false,\"error\":\"missing_path\"}\n");
        return;
    }

    struct stat st;
    if (stat(path, &st) != 0) {
        printf("{\"success\":false,\"error\":\"file_not_found\"}\n");
        return;
    }

    if (S_ISDIR(st.st_mode)) {
        cmd_open_folder();
        return;
    }

    chmod(path, 0666);

    const char *mime = "video/*";
    const char *dot = strrchr(path, '.');
    if (dot) {
        if (strcasecmp(dot, ".mp3") == 0 || strcasecmp(dot, ".m4a") == 0 ||
            strcasecmp(dot, ".aac") == 0 || strcasecmp(dot, ".ogg") == 0 ||
            strcasecmp(dot, ".flac") == 0 || strcasecmp(dot, ".wav") == 0) {
            mime = "audio/*";
        } else if (strcasecmp(dot, ".jpg") == 0 || strcasecmp(dot, ".jpeg") == 0 ||
                   strcasecmp(dot, ".png") == 0 || strcasecmp(dot, ".webp") == 0) {
            mime = "image/*";
        }
    }

    long long media_id = query_sqlite_media_id(path);

    char enc_path[1024];
    size_t ei = 0;
    for (size_t i = 0; path[i] && ei < sizeof(enc_path) - 4; i++) {
        unsigned char c = (unsigned char)path[i];
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
            (c >= '0' && c <= '9') || c == '/' || c == '.' || c == '_' || c == '-') {
            enc_path[ei++] = (char)c;
        } else {
            snprintf(&enc_path[ei], 4, "%%%02X", c);
            ei += 3;
        }
    }
    enc_path[ei] = '\0';

    if (media_id <= 0) {
        char scan_cmd[1200];
        snprintf(scan_cmd, sizeof(scan_cmd),
                 "am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d \"file://%s\" >/dev/null 2>&1",
                 enc_path);
        system(scan_cmd);
        media_id = query_sqlite_media_id(path);
    }

    if (media_id <= 0) {
        char sql_path[1024];
        size_t si = 0;
        for (size_t i = 0; path[i] && si < sizeof(sql_path) - 2; i++) {
            if (path[i] == '\'') {
                sql_path[si++] = '\'';
                sql_path[si++] = '\'';
            } else {
                sql_path[si++] = path[i];
            }
        }
        sql_path[si] = '\0';

        char query_cmd[1200];
        snprintf(query_cmd, sizeof(query_cmd),
                 "content query --uri content://media/external/file --projection _id --where \"_data='%s'\" 2>/dev/null",
                 sql_path);

        FILE *qp = popen(query_cmd, "r");
        if (qp) {
            char qbuf[512];
            while (fgets(qbuf, sizeof(qbuf), qp)) {
                char *p = strstr(qbuf, "_id=");
                if (p) {
                    media_id = strtoll(p + 4, NULL, 10);
                    if (media_id > 0) break;
                }
            }
            pclose(qp);
        }
    }

    char start_cmd[1200];
    if (media_id > 0) {
        snprintf(start_cmd, sizeof(start_cmd),
                 "am start -a android.intent.action.VIEW -d \"content://media/external/file/%lld\" -t \"%s\" --grant-read-uri-permission -f 0x10000000 >/dev/null 2>&1 &",
                 media_id, mime);
        system(start_cmd);
        printf("{\"success\":true,\"mode\":\"content\",\"id\":%lld}\n", media_id);
    } else {
        snprintf(start_cmd, sizeof(start_cmd),
                 "am start -a android.intent.action.VIEW -d \"file://%s\" -t \"%s\" --grant-read-uri-permission -f 0x10000000 >/dev/null 2>&1 &",
                 enc_path, mime);
        system(start_cmd);
        printf("{\"success\":true,\"mode\":\"file\"}\n");
    }
}

static void cmd_info(void) {
    char storage_free[32] = "Unknown";
    struct statvfs vfs;
    if (statvfs("/data", &vfs) == 0) {
        double free_gb = (double)(vfs.f_bavail * vfs.f_frsize) / (1024.0 * 1024.0 * 1024.0);
        snprintf(storage_free, sizeof(storage_free), "%.0f GB", free_gb);
    }

    char mod_version[32] = "v1.2.1";
    FILE *mp = fopen("/data/adb/modules/hyperdl/module.prop", "r");
    if (!mp) mp = fopen("/data/data/com.termux/files/home/HyperDL_Module/module.prop", "r");
    if (mp) {
        char line[256];
        while (fgets(line, sizeof(line), mp)) {
            if (strncmp(line, "version=", 8) == 0) {
                char *nl = strchr(line + 8, '\n');
                if (nl) *nl = '\0';
                char *cr = strchr(line + 8, '\r');
                if (cr) *cr = '\0';
                strncpy(mod_version, line + 8, sizeof(mod_version) - 1);
                break;
            }
        }
        fclose(mp);
    }

    const char *python_bin = find_python();
    int has_cookies = (access(COOKIES_FILE, F_OK) == 0);
    int has_ffmpeg = (access("/data/adb/modules/hyperdl/runtime/bin/ffmpeg", X_OK) == 0) ||
                     (access("/data/adb/modules_update/hyperdl/runtime/bin/ffmpeg", X_OK) == 0) ||
                     (access("/data/data/com.termux/files/home/HyperDL_Module/runtime/bin/ffmpeg", X_OK) == 0) ||
                     (access("/system/bin/ffmpeg", X_OK) == 0);

    printf("{\"version\":\"%s\",\"storage_free\":\"%s\",\"outdir\":\"%s\",\"python\":\"%s\",\"has_cookies\":%s,\"has_ffmpeg\":%s}\n",
           mod_version, storage_free, OUTDIR, python_bin ? python_bin : "None", has_cookies ? "true" : "false", has_ffmpeg ? "true" : "false");
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

static void cmd_clear_logs(void) {
    FILE *f = fopen(LOG_FILE, "w");
    if (f) fclose(f);
    printf("{\"success\":true}\n");
}

static void run_daemon_cmd(const char *action) {
    pid_t p = fork();
    if (p == 0) {
        setsid();
        close(STDIN_FILENO);
        close(STDOUT_FILENO);
        close(STDERR_FILENO);
        int devnull = open("/dev/null", O_RDWR);
        if (devnull >= 0) {
            dup2(devnull, STDIN_FILENO);
            dup2(devnull, STDOUT_FILENO);
            dup2(devnull, STDERR_FILENO);
            if (devnull > STDERR_FILENO) close(devnull);
        }
        const char *daemon_paths[] = {
            "/data/adb/modules/hyperdl/system/bin/hyperdl_daemon",
            "/data/adb/modules_update/hyperdl/system/bin/hyperdl_daemon",
            "/data/data/com.termux/files/home/HyperDL_Module/system/bin/hyperdl_daemon",
            "/system/bin/hyperdl_daemon",
            NULL
        };
        for (int i = 0; daemon_paths[i]; i++) {
            if (access(daemon_paths[i], X_OK) == 0) {
                execl("/system/bin/sh", "sh", daemon_paths[i], action, (char *)NULL);
            }
        }
        _exit(0);
    } else if (p > 0) {
        if (strcmp(action, "stop") == 0) {
            waitpid(p, NULL, 0);
        }
    }
}

static void cmd_toggle_autodl(const char *val) {
    ensure_directories();
    if (val && (strcmp(val, "1") == 0 || strcmp(val, "on") == 0)) {
        int fd = open(AUTODL_FILE, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (fd >= 0) close(fd);
        run_daemon_cmd("start");
        printf("{\"autodl\":true}\n");
    } else {
        unlink(AUTODL_FILE);
        run_daemon_cmd("stop");
        printf("{\"autodl\":false}\n");
    }
}

static void cmd_get_autodl(void) {
    int active = (access(AUTODL_FILE, F_OK) == 0);
    if (active) {
        FILE *pf = fopen("/data/local/tmp/hyperdl_clip.pid", "r");
        int running = 0;
        if (pf) {
            pid_t pid = 0;
            if (fscanf(pf, "%d", &pid) == 1 && pid > 1) {
                if (kill(pid, 0) == 0) {
                    running = 1;
                }
            }
            fclose(pf);
        }
        if (!running) {
            run_daemon_cmd("start");
        }
    }
    printf("{\"autodl\":%s}\n", active ? "true" : "false");
}

static void cmd_pause(void) {
    FILE *pf = fopen(PID_FILE, "r");
    pid_t old_pid = 0;
    if (pf) {
        if (fscanf(pf, "%d", &old_pid) == 1 && old_pid > 1) {
            kill(-old_pid, SIGTERM);
            kill(old_pid, SIGTERM);
            usleep(50000);
            if (kill(old_pid, 0) == 0) {
                kill(-old_pid, SIGKILL);
                kill(old_pid, SIGKILL);
            }
        }
        fclose(pf);
        unlink(PID_FILE);
    }

    char buf[2048] = "";
    FILE *f = fopen(STATUS_FILE, "r");
    if (!f) f = fopen(ACTIVE_TASK_FILE, "r");
    if (f) {
        size_t r = fread(buf, 1, sizeof(buf) - 1, f);
        fclose(f);
        buf[r] = '\0';

        char *sp = strstr(buf, "\"status\":\"downloading\"");
        if (sp) {
            memcpy(sp, "\"status\":\"paused\"     ", 22);
        } else {
            sp = strstr(buf, "\"status\":\"resolving\"");
            if (sp) {
                memcpy(sp, "\"status\":\"paused\"   ", 20);
            }
        }

        FILE *sf = fopen(STATUS_FILE, "w");
        if (sf) { fputs(buf, sf); fclose(sf); chmod(STATUS_FILE, 0666); }
        FILE *af = fopen(ACTIVE_TASK_FILE, "w");
        if (af) { fputs(buf, af); fclose(af); chmod(ACTIVE_TASK_FILE, 0666); }
    } else {
        FILE *sf = fopen(STATUS_FILE, "w");
        if (sf) {
            fputs("{\"status\":\"paused\",\"percent\":0,\"title\":\"Download paused\"}\n", sf);
            fclose(sf);
            chmod(STATUS_FILE, 0666);
        }
        FILE *af = fopen(ACTIVE_TASK_FILE, "w");
        if (af) {
            fputs("{\"status\":\"paused\",\"percent\":0,\"title\":\"Download paused\"}\n", af);
            fclose(af);
            chmod(ACTIVE_TASK_FILE, 0666);
        }
    }
    printf("{\"success\":true,\"paused\":true}\n");
}

static void cmd_cancel(void) {
    FILE *pf = fopen(PID_FILE, "r");
    pid_t old_pid = 0;
    if (pf) {
        if (fscanf(pf, "%d", &old_pid) == 1 && old_pid > 1) {
            kill(-old_pid, SIGTERM);
            kill(old_pid, SIGTERM);
            usleep(30000);
            kill(-old_pid, SIGKILL);
            kill(old_pid, SIGKILL);
        }
        fclose(pf);
        unlink(PID_FILE);
    }
    FILE *sf = fopen(STATUS_FILE, "w");
    if (sf) {
        fputs("{\"status\":\"idle\",\"percent\":0,\"title\":\"\",\"speed\":\"\",\"downloaded\":\"\",\"total\":\"\",\"file_path\":\"\",\"error\":\"\"}\n", sf);
        fclose(sf);
        chmod(STATUS_FILE, 0666);
    }
    FILE *af = fopen(ACTIVE_TASK_FILE, "w");
    if (af) {
        fputs("{\"status\":\"idle\",\"percent\":0}\n", af);
        fclose(af);
        chmod(ACTIVE_TASK_FILE, 0666);
    }
    printf("{\"success\":true,\"cancelled\":true}\n");
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
        const char *url = argc > 2 ? argv[2] : "";
        const char *fmt = argc > 3 ? argv[3] : "video";
        const char *format_id = NULL;
        const char *height = NULL;
        for (int i = 4; i < argc; i++) {
            if (strncmp(argv[i], "--format-id=", 12) == 0) format_id = argv[i] + 12;
            else if (strncmp(argv[i], "--height=", 9) == 0) height = argv[i] + 9;
        }
        cmd_download(url, fmt, format_id, height);
    } else if (strcmp(action, "pause") == 0) {
        cmd_pause();
    } else if (strcmp(action, "cancel") == 0) {
        cmd_cancel();
    } else if (strcmp(action, "probe") == 0) {
        cmd_probe(argc > 2 ? argv[2] : "");
    } else if (strcmp(action, "list") == 0) {
        cmd_list();
    } else if (strcmp(action, "delete") == 0) {
        if (argc > 2) {
            cmd_delete(argc - 2, argv + 2);
        } else {
            printf("{\"success\":false,\"error\":\"missing_path\"}\n");
        }
    } else if (strcmp(action, "open") == 0) {
        cmd_open(argc > 2 ? argv[2] : "");
    } else if (strcmp(action, "open_folder") == 0) {
        cmd_open_folder();
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
    } else if (strcmp(action, "clear_logs") == 0) {
        cmd_clear_logs();
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
