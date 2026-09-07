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
        has_status = (r > 0 && strstr(buf, "\"status\"") != NULL);
    }

    FILE *pf = fopen(PID_FILE, "r");
    pid_t pid = 0;
    int pid_alive = 0;
    if (pf) {
        if (fscanf(pf, "%d", &pid) == 1 && pid > 1) {
            char proc_path[64];
            snprintf(proc_path, sizeof(proc_path), "/proc/%d", pid);
            if ((kill(pid, 0) == 0 || errno == EPERM) && access(proc_path, F_OK) == 0) {
                pid_alive = 1;
            }
        }
        fclose(pf);
    }

    if (pid > 1 && !pid_alive) {
        unlink(PID_FILE);
    }

    // Process is actively running in background - NEVER mutate to paused
    if (pid_alive) {
        if (has_status) {
            printf("%s\n", buf);
        } else {
            // Process is alive, but STATUS_FILE is still being initialized
            FILE *af = fopen(ACTIVE_TASK_FILE, "r");
            if (af) {
                char abuf[2048];
                size_t ar = fread(abuf, 1, sizeof(abuf) - 1, af);
                fclose(af);
                abuf[ar] = '\0';
                if (ar > 0 && strstr(abuf, "\"status\"") != NULL) {
                    printf("%s\n", abuf);
                    return;
                }
            }
            printf("{\"status\":\"resolving\",\"percent\":0}\n");
        }
        return;
    }

    // Process is NOT running.
    // If STATUS_FILE has a completed or error result, report it.
    if (has_status && (strstr(buf, "\"completed\"") || strstr(buf, "\"error\""))) {
        printf("%s\n", buf);
        return;
    }

    // Device reboot or crash recovery: check persistent ACTIVE_TASK_FILE
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

    if (has_status && strstr(buf, "\"paused\"")) {
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


static int is_junk_filename(const char *name) {
    if (!name || !*name) return 0;
    if (strncmp(name, ".tmp", 4) == 0 || strncmp(name, ".trashed", 8) == 0) return 1;
    size_t len = strlen(name);
    if (len > 4 && strcmp(name + len - 4, ".tmp") == 0) return 1;
    if (len > 5 && strcmp(name + len - 5, ".part") == 0) return 1;
    if (len > 5 && strcmp(name + len - 5, ".ytdl") == 0) return 1;
    if (len > 4 && strcmp(name + len - 4, ".raw") == 0) return 1;
    return 0;
}

static void scan_dir_recursive(const char *base_dir, const char *rel_prefix, int *first, int depth) {
    if (depth > 4) return;
    DIR *d = opendir(base_dir);
    if (!d) return;

    struct dirent *entry;
    char full_path[1024];
    struct stat st;
    char size_str[32];

    while ((entry = readdir(d)) != NULL) {
        if (entry->d_name[0] == '.') continue;

        snprintf(full_path, sizeof(full_path), "%s/%s", base_dir, entry->d_name);
        if (stat(full_path, &st) != 0) continue;

        if (S_ISDIR(st.st_mode)) {
            char next_rel[512];
            if (rel_prefix && *rel_prefix) {
                snprintf(next_rel, sizeof(next_rel), "%s/%s", rel_prefix, entry->d_name);
            } else {
                snprintf(next_rel, sizeof(next_rel), "%s", entry->d_name);
            }
            scan_dir_recursive(full_path, next_rel, first, depth + 1);
        } else if (S_ISREG(st.st_mode)) {
            if (is_junk_filename(entry->d_name)) continue;

            format_file_size(st.st_size, size_str, sizeof(size_str));
            const char *dot = strrchr(entry->d_name, '.');
            const char *ext = dot ? dot + 1 : "";

            if (!*first) printf(",\n");
            *first = 0;

            printf("  {\"name\":\"%s\",\"folder\":\"%s\",\"size\":\"%s\",\"ext\":\"%s\",\"path\":\"%s\",\"mtime\":%ld,\"bytes\":%lld}",
                   entry->d_name, rel_prefix ? rel_prefix : "", size_str, ext, full_path, (long)st.st_mtime, (long long)st.st_size);
        }
    }
    closedir(d);
}

static void cmd_list(const char *sub) {
    ensure_directories();
    printf("[\n");
    int first = 1;
    if (sub && strcmp(sub, "vault") == 0) {
        char vault_path[512];
        snprintf(vault_path, sizeof(vault_path), "%s/.vault", OUTDIR);
        scan_dir_recursive(vault_path, "Vault", &first, 0);
    } else {
        scan_dir_recursive(OUTDIR, "", &first, 0);
    }
    printf("\n]\n");
}

static void count_storage_recursive(const char *dir_path, long long *media_count, long long *media_bytes,
                                   long long *junk_count, long long *junk_bytes, int depth) {
    if (depth > 4) return;
    DIR *d = opendir(dir_path);
    if (!d) return;

    struct dirent *entry;
    char full_path[1024];
    struct stat st;

    while ((entry = readdir(d)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) continue;

        snprintf(full_path, sizeof(full_path), "%s/%s", dir_path, entry->d_name);
        if (stat(full_path, &st) != 0) continue;

        if (S_ISDIR(st.st_mode)) {
            if (entry->d_name[0] != '.') {
                count_storage_recursive(full_path, media_count, media_bytes, junk_count, junk_bytes, depth + 1);
            }
        } else if (S_ISREG(st.st_mode)) {
            if (is_junk_filename(entry->d_name)) {
                (*junk_count)++;
                (*junk_bytes) += st.st_size;
            } else if (entry->d_name[0] != '.') {
                (*media_count)++;
                (*media_bytes) += st.st_size;
            }
        }
    }
    closedir(d);
}

static void cmd_storage_info(void) {
    ensure_directories();

    long long media_count = 0;
    long long media_bytes = 0;
    long long junk_count = 0;
    long long junk_bytes = 0;

    count_storage_recursive(OUTDIR, &media_count, &media_bytes, &junk_count, &junk_bytes, 0);

    struct statvfs sv;
    unsigned long long free_bytes = 0;
    unsigned long long total_bytes = 0;
    if (statvfs(OUTDIR, &sv) == 0) {
        free_bytes = (unsigned long long)sv.f_bavail * sv.f_frsize;
        total_bytes = (unsigned long long)sv.f_blocks * sv.f_frsize;
    } else if (statvfs("/data", &sv) == 0) {
        free_bytes = (unsigned long long)sv.f_bavail * sv.f_frsize;
        total_bytes = (unsigned long long)sv.f_blocks * sv.f_frsize;
    }

    char media_sz[32], junk_sz[32], free_sz[32], total_sz[32];
    format_file_size(media_bytes, media_sz, sizeof(media_sz));
    format_file_size(junk_bytes, junk_sz, sizeof(junk_sz));
    format_file_size(free_bytes, free_sz, sizeof(free_sz));
    format_file_size(total_bytes, total_sz, sizeof(total_sz));

    printf("{\"media_count\":%lld,\"media_bytes\":%lld,\"media_size\":\"%s\","
           "\"junk_count\":%lld,\"junk_bytes\":%lld,\"junk_size\":\"%s\","
           "\"free_bytes\":%llu,\"free_size\":\"%s\","
           "\"total_bytes\":%llu,\"total_size\":\"%s\"}\n",
           media_count, media_bytes, media_sz,
           junk_count, junk_bytes, junk_sz,
           free_bytes, free_sz,
           total_bytes, total_sz);
}

static void clean_junk_recursive(const char *dir_path, int *deleted, long long *freed_bytes, int depth) {
    if (depth > 4) return;
    DIR *d = opendir(dir_path);
    if (!d) return;

    struct dirent *entry;
    char full_path[1024];
    struct stat st;

    while ((entry = readdir(d)) != NULL) {
        if (strcmp(entry->d_name, ".") == 0 || strcmp(entry->d_name, "..") == 0) continue;

        snprintf(full_path, sizeof(full_path), "%s/%s", dir_path, entry->d_name);
        if (stat(full_path, &st) != 0) continue;

        if (S_ISDIR(st.st_mode)) {
            if (entry->d_name[0] != '.') {
                clean_junk_recursive(full_path, deleted, freed_bytes, depth + 1);
                rmdir(full_path);
            }
        } else if (S_ISREG(st.st_mode)) {
            if (is_junk_filename(entry->d_name)) {
                off_t fsz = st.st_size;
                if (unlink(full_path) == 0) {
                    (*deleted)++;
                    (*freed_bytes) += fsz;
                }
            }
        }
    }
    closedir(d);
}

static void cmd_clean_junk(void) {
    ensure_directories();

    int deleted = 0;
    long long freed_bytes = 0;

    clean_junk_recursive(OUTDIR, &deleted, &freed_bytes, 0);

    char freed_sz[32];
    format_file_size(freed_bytes, freed_sz, sizeof(freed_sz));
    printf("{\"success\":true,\"deleted\":%d,\"freed_bytes\":%lld,\"freed_size\":\"%s\"}\n",
           deleted, freed_bytes, freed_sz);
}

static void cmd_preview(const char *path) {
    if (!path || !*path) {
        printf("{\"success\":false,\"error\":\"missing_path\"}\n");
        return;
    }

    struct stat st;
    if (stat(path, &st) != 0 || !S_ISREG(st.st_mode)) {
        printf("{\"success\":false,\"error\":\"not_found\"}\n");
        return;
    }

    const char *dot = strrchr(path, '.');
    const char *ext = dot ? dot + 1 : "";
    const char *mime = "application/octet-stream";
    const char *type = "other";

    if (strcasecmp(ext, "jpg") == 0 || strcasecmp(ext, "jpeg") == 0) {
        mime = "image/jpeg"; type = "image";
    } else if (strcasecmp(ext, "png") == 0) {
        mime = "image/png"; type = "image";
    } else if (strcasecmp(ext, "webp") == 0) {
        mime = "image/webp"; type = "image";
    } else if (strcasecmp(ext, "gif") == 0) {
        mime = "image/gif"; type = "image";
    } else if (strcasecmp(ext, "mp4") == 0 || strcasecmp(ext, "mkv") == 0 || strcasecmp(ext, "webm") == 0) {
        mime = "video/mp4"; type = "video";
    } else if (strcasecmp(ext, "mp3") == 0) {
        mime = "audio/mpeg"; type = "audio";
    } else if (strcasecmp(ext, "m4a") == 0 || strcasecmp(ext, "aac") == 0) {
        mime = "audio/mp4"; type = "audio";
    }

    char sz_str[32];
    format_file_size(st.st_size, sz_str, sizeof(sz_str));

    if (strcmp(type, "image") != 0) {
        printf("{\"success\":true,\"type\":\"%s\",\"mime\":\"%s\",\"size\":\"%s\",\"data\":\"\"}\n",
               type, mime, sz_str);
        return;
    }

    if ((size_t)st.st_size > (6 * 1024 * 1024)) {
        printf("{\"success\":false,\"type\":\"image\",\"error\":\"too_large\",\"size\":\"%s\"}\n", sz_str);
        return;
    }

    FILE *f = fopen(path, "rb");
    if (!f) {
        printf("{\"success\":false,\"error\":\"open_failed\"}\n");
        return;
    }

    unsigned char *buf = malloc(st.st_size);
    if (!buf) {
        fclose(f);
        printf("{\"success\":false,\"error\":\"out_of_memory\"}\n");
        return;
    }

    size_t rd = fread(buf, 1, st.st_size, f);
    fclose(f);

    char *b64 = base64_encode(buf, rd);
    free(buf);

    if (!b64) {
        printf("{\"success\":false,\"error\":\"encode_failed\"}\n");
        return;
    }

    printf("{\"success\":true,\"type\":\"%s\",\"mime\":\"%s\",\"size\":\"%s\",\"data\":\"data:%s;base64,%s\"}\n",
           type, mime, sz_str, mime, b64);
    free(b64);
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

    char start_cmd[1400];
    if (media_id > 0) {
        snprintf(start_cmd, sizeof(start_cmd),
                 "am start -a android.intent.action.VIEW -d \"content://media/external/file/%lld\" -t \"%s\" --grant-read-uri-permission -f 0x10000000 >/dev/null 2>&1 &",
                 media_id, mime);
        system(start_cmd);
        printf("{\"success\":true,\"mode\":\"content\",\"id\":%lld}\n", media_id);
    } else {
        snprintf(start_cmd, sizeof(start_cmd),
                 "(am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d \"file://%s\" >/dev/null 2>&1; "
                 "am start -a android.intent.action.VIEW -d \"file://%s\" -t \"%s\" --grant-read-uri-permission -f 0x10000000 >/dev/null 2>&1) &",
                 enc_path, enc_path, mime);
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

    char mod_version[32] = "v1.3.9";
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
    chmod(COOKIES_FILE, 0666);

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

static void cmd_get_clipboard(void) {
    const char *jar = NULL;
    const char *jar_candidates[] = {
        "/data/adb/modules/hyperdl/system/bin/clip.jar",
        "/data/adb/modules_update/hyperdl/system/bin/clip.jar",
        "/data/adb/hyperdl/clip.jar",
        "/system/bin/clip.jar",
        "/data/data/com.termux/files/home/HyperDL_Module/system/bin/clip.jar",
        NULL
    };
    for (int i = 0; jar_candidates[i]; i++) {
        if (access(jar_candidates[i], R_OK) == 0) {
            jar = jar_candidates[i];
            break;
        }
    }
    if (!jar) {
        printf("{\"clipboard\":\"\"}\n");
        return;
    }

    char cmd[512];
    snprintf(cmd, sizeof(cmd), "ANDROID_ROOT=/system ANDROID_DATA=/data CLASSPATH=\"%s\" app_process /system/bin Clip 2>/dev/null", jar);
    FILE *fp = popen(cmd, "r");
    if (!fp) {
        printf("{\"clipboard\":\"\"}\n");
        return;
    }

    char buf[4096] = {0};
    size_t n = fread(buf, 1, sizeof(buf) - 1, fp);
    pclose(fp);

    while (n > 0 && (buf[n - 1] == '\r' || buf[n - 1] == '\n')) {
        buf[--n] = '\0';
    }

    char *b64 = base64_encode((const unsigned char *)buf, n);
    if (b64) {
        printf("{\"clipboard_b64\":\"%s\"}\n", b64);
        free(b64);
    } else {
        printf("{\"clipboard\":\"\"}\n");
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

static void cmd_get_vault_status(void) {
    int active = (access("/data/adb/hyperdl/vault.enabled", F_OK) == 0);
    printf("{\"vault_enabled\":%s}\n", active ? "true" : "false");
}

static void cmd_toggle_vault(const char *val) {
    ensure_directories();
    const char *flag_path = "/data/adb/hyperdl/vault.enabled";
    int target = -1;
    if (val && *val) {
        if (strcmp(val, "1") == 0 || strcmp(val, "on") == 0 || strcasecmp(val, "true") == 0) target = 1;
        else if (strcmp(val, "0") == 0 || strcmp(val, "off") == 0 || strcasecmp(val, "false") == 0) target = 0;
    }
    if (target == -1) {
        target = (access(flag_path, F_OK) != 0);
    }

    if (target) {
        int fd = open(flag_path, O_WRONLY | O_CREAT | O_TRUNC, 0666);
        if (fd >= 0) close(fd);
        chmod(flag_path, 0666);

        char vault_dir[512];
        char nomedia[512];
        snprintf(vault_dir, sizeof(vault_dir), "%s/.vault", OUTDIR);
        snprintf(nomedia, sizeof(nomedia), "%s/.vault/.nomedia", OUTDIR);
        mkdir(vault_dir, 0777);
        chmod(vault_dir, 0777);

        int nfd = open(nomedia, O_WRONLY | O_CREAT | O_TRUNC, 0666);
        if (nfd >= 0) close(nfd);
        chmod(nomedia, 0666);

        const char *conf_path = "/data/adb/hyperdl/vault_domains.conf";
        if (access(conf_path, F_OK) != 0) {
            FILE *cf = fopen(conf_path, "w");
            if (cf) {
                static const char b64_domains[] = "cG9ybmh1Yi5jb20KeG54eC5jb20KeHZpZGVvcy5jb20KcmVkdHViZS5jb20KeGhhbXN0ZXIuY29tCmVwb3JuZXIuY29tCnlvdXBvcm4uY29tCnZqYXYuY29tCmphcGFuaGR2LmNvbQpqYXBhbmVzZXBvcm4ueHh4Cnhoc29jaWFsLmNvbQpiZHNtc3RyZWFrLmNvbQo=";
                size_t out_len = 0;
                unsigned char *dec = base64_decode(b64_domains, strlen(b64_domains), &out_len);
                if (dec) {
                    fwrite(dec, 1, out_len, cf);
                    free(dec);
                }
                fclose(cf);
                chmod(conf_path, 0666);
            }
        }
        printf("{\"success\":true,\"vault_enabled\":true}\n");
    } else {
        unlink(flag_path);
        printf("{\"success\":true,\"vault_enabled\":false}\n");
    }
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
        cmd_list(argc > 2 ? argv[2] : NULL);
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
    } else if (strcmp(action, "toggle_vault") == 0) {
        cmd_toggle_vault(argc > 2 ? argv[2] : "");
    } else if (strcmp(action, "get_vault_status") == 0) {
        cmd_get_vault_status();
    } else if (strcmp(action, "get_clipboard") == 0) {
        cmd_get_clipboard();
    } else if (strcmp(action, "storage_info") == 0) {
        cmd_storage_info();
    } else if (strcmp(action, "clean_junk") == 0) {
        cmd_clean_junk();
    } else if (strcmp(action, "preview") == 0) {
        cmd_preview(argc > 2 ? argv[2] : "");
    } else {
        printf("{\"error\":\"unknown_action\"}\n");
        return 1;
    }

    return 0;
}
