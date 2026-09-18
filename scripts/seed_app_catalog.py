#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Seed 100+ OSS apps for the compiler farm (skips existing rich app trees)."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "apps"
CATALOG = ROOT / "configs" / "app_catalog.json"

# type, name, display, langs, build_system, default_version, url, ref, test_cmd, workload, desc
# Linguistic type folders; names A–Z within type.
RAW: list[tuple] = [
    # --- compression ---
    ("compression", "brotli", "Brotli", ["c"], "cmake", "1.1.0", "https://github.com/google/brotli.git", "v1.1.0", ["./brotli", "--version"], ["./brotli", "--version"], "Google Brotli compression"),
    ("compression", "bzip2", "bzip2", ["c"], "make", "1.0.8", "https://gitlab.com/bzip2/bzip2.git", "bzip2-1.0.8", ["./bzip2", "--help"], ["./bzip2", "--help"], "bzip2 compressor"),
    ("compression", "lz4", "LZ4", ["c"], "make", "1.10.0", "https://github.com/lz4/lz4.git", "v1.10.0", ["./lz4", "--version"], ["./lz4", "--version"], "LZ4 fast compression"),
    ("compression", "snappy", "Snappy", ["c++"], "cmake", "1.2.1", "https://github.com/google/snappy.git", "1.2.1", ["ctest", "--test-dir", "build", "--output-on-failure"], ["ctest", "--test-dir", "build"], "Google Snappy"),
    ("compression", "xz", "XZ Utils", ["c"], "configure", "5.6.2", "https://github.com/tukaani-project/xz.git", "v5.6.2", ["./src/xz/xz", "--version"], ["./src/xz/xz", "--version"], "XZ / liblzma"),
    ("compression", "zlib", "zlib", ["c"], "configure", "1.3.1", "https://github.com/madler/zlib.git", "v1.3.1", ["make", "check"], ["./minigzip"], "zlib compression library"),
    ("compression", "zstd", "Zstandard", ["c"], "make", "1.5.6", "https://github.com/facebook/zstd.git", "v1.5.6", ["./zstd", "--version"], ["./zstd", "--version"], "Facebook Zstandard"),
    # --- crypto ---
    ("crypto", "libsodium", "libsodium", ["c"], "configure", "1.0.20", "https://github.com/jedisct1/libsodium.git", "1.0.20-RELEASE", ["make", "check"], ["make", "check"], "Sodium crypto library"),
    ("crypto", "mbedtls", "Mbed TLS", ["c"], "cmake", "3.6.2", "https://github.com/Mbed-TLS/mbedtls.git", "v3.6.2", ["ctest", "--output-on-failure"], ["ctest"], "Mbed TLS"),
    ("crypto", "openssl", "OpenSSL", ["c"], "custom", "3.4.0", "https://github.com/openssl/openssl.git", "openssl-3.4.0", ["./apps/openssl", "version"], ["./apps/openssl", "version"], "OpenSSL toolkit"),
    ("crypto", "wolfssl", "wolfSSL", ["c"], "configure", "5.7.4", "https://github.com/wolfSSL/wolfssl.git", "v5.7.4-stable", ["make", "check"], ["make", "check"], "wolfSSL"),
    # --- database (extras; rich ones already exist) ---
    ("database", "duckdb", "DuckDB", ["c++"], "make", "1.1.3", "https://github.com/duckdb/duckdb.git", "v1.1.3", ["./build/release/duckdb", "-c", "select 1"], ["./build/release/duckdb", "-c", "select 1"], "in-process OLAP DB"),
    ("database", "leveldb", "LevelDB", ["c++"], "cmake", "1.23", "https://github.com/google/leveldb.git", "1.23", ["ctest", "--output-on-failure"], ["ctest"], "Google LevelDB"),
    ("database", "lmdb", "LMDB", ["c"], "make", "0.9.31", "https://github.com/LMDB/lmdb.git", "LMDB_0.9.31", ["make", "test"], ["./mdb_stat", "-V"], "Lightning Memory-Mapped DB"),
    ("database", "mariadb", "MariaDB", ["c", "c++"], "cmake", "11.4.4", "https://github.com/MariaDB/server.git", "mariadb-11.4.4", ["./sql/mariadbd", "--version"], ["./sql/mariadbd", "--version"], "MariaDB server"),
    ("database", "mongodb", "MongoDB", ["c++"], "custom", "8.3", "https://github.com/mongodb/mongo.git", "r8.3.0", ["./build/install/bin/mongod", "--version"], ["./build/install/bin/mongod", "--version"], "MongoDB (rich versions preseeded)"),
    ("database", "mysql", "MySQL", ["c", "c++"], "cmake", "9.7", "https://github.com/mysql/mysql-server.git", "mysql-9.7.2", ["./runtime_output_directory/mysqld", "--version"], ["./runtime_output_directory/mysqld", "--version"], "MySQL (rich versions preseeded)"),
    ("database", "postgres", "PostgreSQL", ["c"], "configure", "18", "https://github.com/postgres/postgres.git", "REL_18_STABLE", ["./src/backend/postgres", "--version"], ["./src/backend/postgres", "--version"], "PostgreSQL (rich versions preseeded)"),
    ("database", "rocksdb", "RocksDB", ["c++"], "make", "9.7.3", "https://github.com/facebook/rocksdb.git", "v9.7.3", ["./db_bench", "--benchmarks=fillseq", "--num=1000"], ["./db_bench", "--benchmarks=fillseq", "--num=1000"], "Facebook RocksDB"),
    ("database", "sqlite", "SQLite", ["c"], "configure", "3.53", "https://github.com/sqlite/sqlite.git", "version-3.53.4", ["./sqlite3", ":memory:", "select 1;"], ["./sqlite3", ":memory:", "select 1;"], "SQLite (rich versions preseeded)"),
    # --- editors ---
    ("editors", "neovim", "Neovim", ["c"], "cmake", "0.10.2", "https://github.com/neovim/neovim.git", "v0.10.2", ["./build/bin/nvim", "--version"], ["./build/bin/nvim", "--version"], "Neovim editor"),
    ("editors", "tmux", "tmux", ["c"], "configure", "3.5a", "https://github.com/tmux/tmux.git", "3.5a", ["./tmux", "-V"], ["./tmux", "-V"], "terminal multiplexer"),
    ("editors", "vim", "Vim", ["c"], "configure", "9.1.0", "https://github.com/vim/vim.git", "v9.1.0", ["./src/vim", "--version"], ["./src/vim", "--version"], "Vim editor"),
    # --- graphics ---
    ("graphics", "cairo", "Cairo", ["c"], "meson", "1.18.2", "https://gitlab.freedesktop.org/cairo/cairo.git", "1.18.2", ["meson", "test", "-C", "build"], ["meson", "test", "-C", "build"], "2D graphics library"),
    ("graphics", "freetype", "FreeType", ["c"], "configure", "2.13.3", "https://gitlab.freedesktop.org/freetype/freetype.git", "VER-2-13-3", ["make", "check"], ["make", "check"], "font rendering"),
    ("graphics", "harfbuzz", "HarfBuzz", ["c++"], "meson", "10.0.1", "https://github.com/harfbuzz/harfbuzz.git", "10.0.1", ["meson", "test", "-C", "build"], ["meson", "test", "-C", "build"], "text shaping"),
    ("graphics", "libpng", "libpng", ["c"], "configure", "1.6.44", "https://github.com/pnggroup/libpng.git", "v1.6.44", ["make", "check"], ["make", "check"], "PNG library"),
    ("graphics", "libjpeg_turbo", "libjpeg-turbo", ["c"], "cmake", "3.0.4", "https://github.com/libjpeg-turbo/libjpeg-turbo.git", "3.0.4", ["ctest", "--output-on-failure"], ["ctest"], "JPEG library"),
    ("graphics", "pixman", "Pixman", ["c"], "meson", "0.43.4", "https://gitlab.freedesktop.org/pixman/pixman.git", "pixman-0.43.4", ["meson", "test", "-C", "build"], ["meson", "test", "-C", "build"], "pixel manipulation"),
    ("graphics", "sdl2", "SDL2", ["c"], "cmake", "2.30.9", "https://github.com/libsdl-org/SDL.git", "release-2.30.9", ["./build/test/testversion"], ["./build/test/testversion"], "Simple DirectMedia Layer 2"),
    # --- hpc ---
    ("hpc", "fftw", "FFTW", ["c"], "configure", "3.3.10", "https://github.com/FFTW/fftw3.git", "fftw-3.3.10", ["make", "check"], ["make", "check"], "Fastest Fourier Transform"),
    ("hpc", "gsl", "GSL", ["c"], "configure", "2.8", "https://github.com/ampl/gsl.git", "v2.8", ["make", "check"], ["make", "check"], "GNU Scientific Library"),
    ("hpc", "hdf5", "HDF5", ["c"], "cmake", "1.14.5", "https://github.com/HDFGroup/hdf5.git", "hdf5_1.14.5", ["ctest", "--output-on-failure"], ["ctest"], "Hierarchical Data Format"),
    ("hpc", "openblas", "OpenBLAS", ["c", "fortran"], "make", "0.3.28", "https://github.com/OpenMathLib/OpenBLAS.git", "v0.3.28", ["make", "tests"], ["./test/openblas_utest"], "optimized BLAS"),
    # --- languages ---
    ("languages", "lua", "Lua", ["c"], "make", "5.4.7", "https://github.com/lua/lua.git", "v5.4.7", ["./lua", "-v"], ["./lua", "-e", "print(1+1)"], "Lua language"),
    ("languages", "luajit", "LuaJIT", ["c"], "make", "2.1", "https://github.com/LuaJIT/LuaJIT.git", "v2.1", ["./src/luajit", "-v"], ["./src/luajit", "-e", "print(1)"], "LuaJIT"),
    ("languages", "micropython", "MicroPython", ["c"], "make", "1.24.1", "https://github.com/micropython/micropython.git", "v1.24.1", ["./ports/unix/build-standard/micropython", "-c", "print(1)"], ["./ports/unix/build-standard/micropython", "-c", "print(1)"], "MicroPython"),
    ("languages", "php", "PHP", ["c"], "configure", "8.3.14", "https://github.com/php/php-src.git", "php-8.3.14", ["./sapi/cli/php", "-v"], ["./sapi/cli/php", "-r", "echo 1;"], "PHP interpreter"),
    ("languages", "ruby", "Ruby", ["c"], "configure", "3.3.6", "https://github.com/ruby/ruby.git", "v3_3_6", ["./ruby", "-v"], ["./ruby", "-e", "puts 1"], "Ruby language"),
    ("languages", "tcl", "Tcl", ["c"], "configure", "8.6.15", "https://github.com/tcltk/tcl.git", "core-8-6-15", ["./unix/tclsh", "<<<", "puts 1"], ["./unix/tclsh"], "Tcl language"),
    # --- libraries ---
    ("libraries", "cjson", "cJSON", ["c"], "cmake", "1.7.18", "https://github.com/DaveGamble/cJSON.git", "v1.7.18", ["ctest", "--output-on-failure"], ["ctest"], "Ultralightweight JSON"),
    ("libraries", "fmt", "fmt", ["c++"], "cmake", "11.0.2", "https://github.com/fmtlib/fmt.git", "11.0.2", ["ctest", "--output-on-failure"], ["ctest"], "{fmt} library"),
    ("libraries", "jansson", "Jansson", ["c"], "configure", "2.14", "https://github.com/akheron/jansson.git", "v2.14", ["make", "check"], ["make", "check"], "C JSON library"),
    ("libraries", "libarchive", "libarchive", ["c"], "cmake", "3.7.7", "https://github.com/libarchive/libarchive.git", "v3.7.7", ["ctest", "--output-on-failure"], ["ctest"], "multi-format archive"),
    ("libraries", "libevent", "libevent", ["c"], "cmake", "2.1.12", "https://github.com/libevent/libevent.git", "release-2.1.12-stable", ["ctest", "--output-on-failure"], ["ctest"], "event notification"),
    ("libraries", "libuv", "libuv", ["c"], "cmake", "1.49.2", "https://github.com/libuv/libuv.git", "v1.49.2", ["ctest", "--output-on-failure"], ["ctest"], "async I/O"),
    ("libraries", "libxml2", "libxml2", ["c"], "configure", "2.13.5", "https://gitlab.gnome.org/GNOME/libxml2.git", "v2.13.5", ["make", "check"], ["make", "check"], "XML C parser"),
    ("libraries", "libyaml", "libyaml", ["c"], "configure", "0.2.5", "https://github.com/yaml/libyaml.git", "0.2.5", ["make", "check"], ["make", "check"], "YAML C library"),
    ("libraries", "msgpack_c", "msgpack-c", ["c"], "cmake", "6.1.0", "https://github.com/msgpack/msgpack-c.git", "c-6.1.0", ["ctest", "--output-on-failure"], ["ctest"], "MessagePack C"),
    ("libraries", "protobuf", "Protocol Buffers", ["c++"], "cmake", "28.3", "https://github.com/protocolbuffers/protobuf.git", "v28.3", ["ctest", "--output-on-failure"], ["ctest"], "Google protobuf"),
    ("libraries", "rapidjson", "RapidJSON", ["c++"], "cmake", "1.1.0", "https://github.com/Tencent/rapidjson.git", "v1.1.0", ["ctest", "--output-on-failure"], ["ctest"], "JSON parser"),
    ("libraries", "re2", "RE2", ["c++"], "cmake", "2024-07-02", "https://github.com/google/re2.git", "2024-07-02", ["ctest", "--output-on-failure"], ["ctest"], "Google RE2 regex"),
    ("libraries", "spdlog", "spdlog", ["c++"], "cmake", "1.15.0", "https://github.com/gabime/spdlog.git", "v1.15.0", ["ctest", "--output-on-failure"], ["ctest"], "C++ logging"),
    ("libraries", "sqlite_amalgamation", "SQLite amalgamation helper", ["c"], "make", "3.53", "https://github.com/sqlite/sqlite.git", "version-3.53.4", ["./sqlite3", ":memory:", "select 1;"], ["./sqlite3", ":memory:", "select 1;"], "alias-style sqlite pin"),
    # --- media ---
    ("media", "aom", "libaom", ["c"], "cmake", "3.11.0", "https://aomedia.googlesource.com/aom", "v3.11.0", ["./build/aomenc", "--help"], ["./build/aomenc", "--help"], "AV1 codec"),
    ("media", "dav1d", "dav1d", ["c"], "meson", "1.5.0", "https://code.videolan.org/videolan/dav1d.git", "1.5.0", ["meson", "test", "-C", "build"], ["meson", "test", "-C", "build"], "AV1 decoder"),
    ("media", "ffmpeg", "FFmpeg", ["c"], "configure", "9.0", "https://github.com/FFmpeg/FFmpeg.git", "n9.0.1", ["./ffmpeg", "-version"], ["./ffmpeg", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10", "-f", "null", "-"], "FFmpeg (rich versions preseeded)"),
    ("media", "flac", "FLAC", ["c"], "configure", "1.4.3", "https://github.com/xiph/flac.git", "1.4.3", ["make", "check"], ["make", "check"], "Free Lossless Audio Codec"),
    ("media", "imagemagick", "ImageMagick", ["c"], "configure", "7.1.1-41", "https://github.com/ImageMagick/ImageMagick.git", "7.1.1-41", ["./utilities/magick", "-version"], ["./utilities/magick", "-version"], "ImageMagick"),
    ("media", "libogg", "libogg", ["c"], "configure", "1.3.5", "https://github.com/xiph/ogg.git", "v1.3.5", ["make", "check"], ["make", "check"], "Ogg container"),
    ("media", "libvorbis", "libvorbis", ["c"], "configure", "1.3.7", "https://github.com/xiph/vorbis.git", "v1.3.7", ["make", "check"], ["make", "check"], "Vorbis audio"),
    ("media", "libvpx", "libvpx", ["c"], "configure", "1.15.0", "https://chromium.googlesource.com/webm/libvpx", "v1.15.0", ["./vpxenc", "--help"], ["./vpxenc", "--help"], "VP8/VP9 codec"),
    ("media", "opus", "Opus", ["c"], "configure", "1.5.2", "https://github.com/xiph/opus.git", "v1.5.2", ["make", "check"], ["make", "check"], "Opus audio codec"),
    ("media", "x264", "x264", ["c"], "configure", "stable", "https://code.videolan.org/videolan/x264.git", "stable", ["./x264", "--version"], ["./x264", "--version"], "H.264 encoder"),
    ("media", "x265", "x265", ["c++"], "cmake", "4.0", "https://bitbucket.org/multicoreware/x265_git.git", "4.0", ["./build/linux/x265", "--version"], ["./build/linux/x265", "--version"], "H.265 encoder"),
    # --- networking ---
    ("networking", "c_ares", "c-ares", ["c"], "cmake", "1.34.3", "https://github.com/c-ares/c-ares.git", "v1.34.3", ["ctest", "--output-on-failure"], ["ctest"], "async DNS"),
    ("networking", "curl", "curl", ["c"], "configure", "8.11.1", "https://github.com/curl/curl.git", "curl-8_11_1", ["./src/curl", "--version"], ["./src/curl", "--version"], "curl transfer tool"),
    ("networking", "haproxy", "HAProxy", ["c"], "make", "3.0.6", "https://github.com/haproxy/haproxy.git", "v3.0.6", ["./haproxy", "-v"], ["./haproxy", "-v"], "load balancer"),
    ("networking", "libssh2", "libssh2", ["c"], "cmake", "1.11.1", "https://github.com/libssh2/libssh2.git", "libssh2-1.11.1", ["ctest", "--output-on-failure"], ["ctest"], "SSH2 client lib"),
    ("networking", "nghttp2", "nghttp2", ["c"], "cmake", "1.64.0", "https://github.com/nghttp2/nghttp2.git", "v1.64.0", ["ctest", "--output-on-failure"], ["ctest"], "HTTP/2 C library"),
    ("networking", "nginx", "nginx", ["c"], "configure", "1.27.3", "https://github.com/nginx/nginx.git", "release-1.27.3", ["./objs/nginx", "-v"], ["./objs/nginx", "-v"], "nginx web server"),
    ("networking", "unbound", "Unbound", ["c"], "configure", "1.22.0", "https://github.com/NLnetLabs/unbound.git", "release-1.22.0", ["./unbound", "-V"], ["./unbound", "-V"], "validating DNS resolver"),
    # --- security ---
    ("security", "openssh", "OpenSSH", ["c"], "configure", "9.9p1", "https://github.com/openssh/openssh-portable.git", "V_9_9_P1", ["./ssh", "-V"], ["./ssh", "-V"], "OpenSSH portable"),
    ("security", "sudo", "Sudo", ["c"], "configure", "1.9.16p2", "https://github.com/sudo-project/sudo.git", "SUDO_1_9_16p2", ["./src/sudo", "-V"], ["./src/sudo", "-V"], "sudo"),
    # --- systems ---
    ("systems", "bash", "Bash", ["c"], "configure", "5.2.37", "https://git.savannah.gnu.org/git/bash.git", "bash-5.2.37", ["./bash", "--version"], ["./bash", "-c", "echo ok"], "GNU Bash"),
    ("systems", "busybox", "BusyBox", ["c"], "make", "1.37.0", "https://github.com/mirror/busybox.git", "1_37_0", ["./busybox", "--help"], ["./busybox", "echo", "ok"], "BusyBox utilities"),
    ("systems", "coreutils", "GNU coreutils", ["c"], "configure", "9.5", "https://github.com/coreutils/coreutils.git", "v9.5", ["./src/uname", "-a"], ["./src/uname", "-a"], "GNU coreutils"),
    ("systems", "gawk", "Gawk", ["c"], "configure", "5.3.1", "https://git.savannah.gnu.org/git/gawk.git", "gawk-5.3.1", ["./gawk", "--version"], ["./gawk", "--version"], "GNU Awk"),
    ("systems", "git", "Git", ["c"], "make", "2.47.1", "https://github.com/git/git.git", "v2.47.1", ["./git", "--version"], ["./git", "--version"], "Git VCS"),
    ("systems", "grep", "GNU grep", ["c"], "configure", "3.11", "https://git.savannah.gnu.org/git/grep.git", "v3.11", ["./src/grep", "--version"], ["./src/grep", "--version"], "GNU grep"),
    ("systems", "jq", "jq", ["c"], "configure", "1.7.1", "https://github.com/jqlang/jq.git", "jq-1.7.1", ["./jq", "--version"], ["./jq", "-n", "1+1"], "jq JSON processor"),
    ("systems", "less", "less", ["c"], "configure", "668", "https://github.com/gwsw/less.git", "v668", ["./less", "--version"], ["./less", "--version"], "less pager"),
    ("systems", "make", "GNU Make", ["c"], "configure", "4.4.1", "https://git.savannah.gnu.org/git/make.git", "4.4.1", ["./make", "--version"], ["./make", "--version"], "GNU Make"),
    ("systems", "nano", "nano", ["c"], "configure", "8.2", "https://git.savannah.gnu.org/git/nano.git", "v8.2", ["./src/nano", "--version"], ["./src/nano", "--version"], "GNU nano"),
    ("systems", "redis", "Redis", ["c"], "make", "8.10", "https://github.com/redis/redis.git", "8.10.1", ["./src/redis-server", "--version"], ["./src/redis-benchmark", "-n", "1000", "-q"], "Redis (rich versions preseeded)"),
    ("systems", "rsync", "rsync", ["c"], "configure", "3.3.0", "https://github.com/RsyncProject/rsync.git", "v3.3.0", ["./rsync", "--version"], ["./rsync", "--version"], "rsync"),
    ("systems", "sed", "GNU sed", ["c"], "configure", "4.9", "https://git.savannah.gnu.org/git/sed.git", "v4.9", ["./sed/sed", "--version"], ["./sed/sed", "--version"], "GNU sed"),
    ("systems", "tar", "GNU tar", ["c"], "configure", "1.35", "https://git.savannah.gnu.org/git/tar.git", "release_1_35", ["./src/tar", "--version"], ["./src/tar", "--version"], "GNU tar"),
    ("systems", "wget", "GNU Wget", ["c"], "configure", "1.25.0", "https://git.savannah.gnu.org/git/wget.git", "v1.25.0", ["./src/wget", "--version"], ["./src/wget", "--version"], "GNU Wget"),
    ("systems", "zsh", "Zsh", ["c"], "configure", "5.9", "https://github.com/zsh-users/zsh.git", "zsh-5.9", ["./Src/zsh", "--version"], ["./Src/zsh", "--version"], "Z shell"),
    # --- tools ---
    ("tools", "cmake", "CMake", ["c++"], "custom", "3.31.2", "https://github.com/Kitware/CMake.git", "v3.31.2", ["./bootstrap", "--parallel=4"], ["./bin/cmake", "--version"], "CMake build system"),
    ("tools", "ninja", "Ninja", ["c++"], "cmake", "1.12.1", "https://github.com/ninja-build/ninja.git", "v1.12.1", ["./ninja", "--version"], ["./ninja", "--version"], "Ninja build"),
    ("tools", "pkgconf", "pkgconf", ["c"], "configure", "2.3.0", "https://github.com/pkgconf/pkgconf.git", "pkgconf-2.3.0", ["./pkgconf", "--version"], ["./pkgconf", "--version"], "pkg-config implementation"),
    ("tools", "strace", "strace", ["c"], "configure", "6.12", "https://github.com/strace/strace.git", "v6.12", ["./src/strace", "-V"], ["./src/strace", "-V"], "strace"),
    # --- more libraries / systems to cross 100 ---
    ("libraries", "abseil", "Abseil", ["c++"], "cmake", "20240722.0", "https://github.com/abseil/abseil-cpp.git", "20240722.0", ["ctest", "--output-on-failure"], ["ctest"], "Abseil C++"),
    ("libraries", "benchmark", "Google Benchmark", ["c++"], "cmake", "1.9.0", "https://github.com/google/benchmark.git", "v1.9.0", ["ctest", "--output-on-failure"], ["ctest"], "microbenchmark framework"),
    ("libraries", "double_conversion", "double-conversion", ["c++"], "cmake", "3.3.0", "https://github.com/google/double-conversion.git", "v3.3.0", ["ctest", "--output-on-failure"], ["ctest"], "binary-decimal conversion"),
    ("libraries", "flatbuffers", "FlatBuffers", ["c++"], "cmake", "24.12.23", "https://github.com/google/flatbuffers.git", "v24.12.23", ["ctest", "--output-on-failure"], ["ctest"], "FlatBuffers"),
    ("libraries", "gflags", "gflags", ["c++"], "cmake", "2.2.2", "https://github.com/gflags/gflags.git", "v2.2.2", ["ctest", "--output-on-failure"], ["ctest"], "commandline flags"),
    ("libraries", "glog", "glog", ["c++"], "cmake", "0.7.1", "https://github.com/google/glog.git", "v0.7.1", ["ctest", "--output-on-failure"], ["ctest"], "Google logging"),
    ("libraries", "googletest", "GoogleTest", ["c++"], "cmake", "1.15.2", "https://github.com/google/googletest.git", "v1.15.2", ["ctest", "--output-on-failure"], ["ctest"], "GoogleTest / gmock"),
    ("libraries", "icu", "ICU", ["c", "c++"], "configure", "76.1", "https://github.com/unicode-org/icu.git", "release-76-1", ["make", "check"], ["make", "check"], "International Components for Unicode"),
    ("libraries", "jsoncpp", "JsonCpp", ["c++"], "cmake", "1.9.6", "https://github.com/open-source-parsers/jsoncpp.git", "1.9.6", ["ctest", "--output-on-failure"], ["ctest"], "JsonCpp"),
    ("libraries", "libffi", "libffi", ["c"], "configure", "3.4.6", "https://github.com/libffi/libffi.git", "v3.4.6", ["make", "check"], ["make", "check"], "Foreign Function Interface"),
    ("libraries", "pcre2", "PCRE2", ["c"], "configure", "10.44", "https://github.com/PCRE2Project/pcre2.git", "pcre2-10.44", ["make", "check"], ["make", "check"], "Perl Compatible Regex"),
    ("libraries", "utf8proc", "utf8proc", ["c"], "make", "2.9.0", "https://github.com/JuliaStrings/utf8proc.git", "v2.9.0", ["make", "check"], ["make", "check"], "UTF-8 processing"),
    ("networking", "lighttpd", "lighttpd", ["c"], "cmake", "1.4.76", "https://github.com/lighttpd/lighttpd1.4.git", "lighttpd-1.4.76", ["./build/build/lighttpd", "-v"], ["./build/build/lighttpd", "-v"], "lighttpd web server"),
    ("networking", "mosquitto", "Eclipse Mosquitto", ["c"], "cmake", "2.0.20", "https://github.com/eclipse-mosquitto/mosquitto.git", "v2.0.20", ["./src/mosquitto", "-h"], ["./src/mosquitto", "-h"], "MQTT broker"),
    ("systems", "findutils", "GNU findutils", ["c"], "configure", "4.10.0", "https://git.savannah.gnu.org/git/findutils.git", "v4.10.0", ["./find/find", "--version"], ["./find/find", "--version"], "GNU findutils"),
    ("systems", "gmp", "GMP", ["c"], "configure", "6.3.0", "https://github.com/alisw/GMP.git", "v6.3.0", ["make", "check"], ["make", "check"], "GNU MP arithmetic"),
    ("systems", "htop", "htop", ["c"], "configure", "3.3.0", "https://github.com/htop-dev/htop.git", "3.3.0", ["./htop", "--version"], ["./htop", "--version"], "htop process viewer"),
    ("systems", "nettle", "Nettle", ["c"], "configure", "3.10", "https://git.lysator.liu.se/nettle/nettle.git", "nettle_3.10_release_20240607", ["make", "check"], ["make", "check"], "low-level crypto library"),
    ("tools", "bison", "Bison", ["c"], "configure", "3.8.2", "https://git.savannah.gnu.org/git/bison.git", "v3.8.2", ["./src/bison", "--version"], ["./src/bison", "--version"], "GNU Bison"),
    ("tools", "flex", "flex", ["c"], "configure", "2.6.4", "https://github.com/westes/flex.git", "v2.6.4", ["./src/flex", "--version"], ["./src/flex", "--version"], "fast lexical analyzer"),
    ("tools", "patch", "GNU patch", ["c"], "configure", "2.7.6", "https://git.savannah.gnu.org/git/patch.git", "v2.7.6", ["./src/patch", "--version"], ["./src/patch", "--version"], "GNU patch"),
]


def dump_yaml(data: dict) -> str:
    def emit(obj: object, indent: int = 0) -> list[str]:
        sp = "  " * indent
        lines: list[str] = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"{sp}{k}:")
                    lines.extend(emit(v, indent + 1))
                elif isinstance(v, bool):
                    lines.append(f"{sp}{k}: {'true' if v else 'false'}")
                elif v is None:
                    lines.append(f"{sp}{k}: null")
                else:
                    s = str(v)
                    if any(c in s for c in ":#{}[]&*|>'\"%@`\n"):
                        lines.append(f'{sp}{k}: "{s}"')
                    else:
                        lines.append(f"{sp}{k}: {s}")
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, (dict, list)):
                    lines.append(f"{sp}-")
                    lines.extend(emit(item, indent + 1))
                else:
                    s = str(item)
                    lines.append(f'{sp}- "{s}"' if any(c in s for c in ":#") else f"{sp}- {s}")
        return lines

    return "\n".join(emit(data)) + "\n"


def recipe_for(build: str, version: str, url: str, ref: str, test: list[str], workload: list[str]) -> dict:
    if build == "custom" and "openssl" in url:
        build_spec = {
            "system": "custom",
            "commands": [["./Configure", "linux-x86_64"], ["make", "-j4"]],
        }
    elif build == "custom" and "cmake" in url.lower():
        build_spec = {
            "system": "custom",
            "commands": [["./bootstrap", "--parallel=4"], ["make", "-j4"]],
        }
    elif build == "meson":
        # treat meson as custom command sequence for runner MVP
        build_spec = {
            "system": "custom",
            "commands": [
                ["meson", "setup", "build", "--buildtype=release"],
                ["meson", "compile", "-C", "build"],
            ],
        }
    else:
        build_spec = {"system": build if build != "meson" else "custom", "args": []}

    return {
        "version": version,
        "source": {"url": url, "ref": ref},
        "toolchain": {"cc": "${CC}", "cxx": "${CXX}", "cflags": [], "cxxflags": [], "ldflags": []},
        "build": build_spec,
        "test": {"command": test, "timeout_sec": 1800},
        "perf": {
            "csperf": {
                "enabled": True,
                "backend": "cpu",
                "warmup_runs": 1,
                "repeat_runs": 3,
                "workload": workload,
            }
        },
    }


def generic_deps(version: str, name: str) -> dict:
    return {
        "version": version,
        "summary": f"Generic build deps for {name} (refine per distro as needed)",
        "compiler_notes": "Use farm toolchains.enabled (clang/gcc). Tags/refs are best-effort pins.",
        "references": [],
        "os": {
            "linux": {
                "common": {
                    "build": ["gcc/g++ or clang", "make", "cmake or meson as required", "git", "pkg-config"],
                    "runtime": [],
                },
                "distros": {
                    "arch": {
                        "releases": ["rolling"],
                        "packages": {"build": ["base-devel", "git", "cmake", "meson"], "runtime": []},
                        "install": {
                            "build": "sudo pacman -Syu --needed base-devel git cmake meson",
                            "runtime": "true",
                        },
                    },
                    "debian": {
                        "releases": ["12", "13"],
                        "packages": {
                            "build": ["build-essential", "git", "cmake", "meson", "pkg-config"],
                            "runtime": [],
                        },
                        "install": {
                            "build": "sudo apt-get update && sudo apt-get install -y build-essential git cmake meson pkg-config",
                            "runtime": "true",
                        },
                    },
                    "fedora": {
                        "releases": ["40", "41", "42"],
                        "packages": {"build": ["gcc", "gcc-c++", "git", "cmake", "meson"], "runtime": []},
                        "install": {
                            "build": "sudo dnf install -y gcc gcc-c++ git cmake meson",
                            "runtime": "true",
                        },
                    },
                    "rhel": {
                        "releases": ["8", "9"],
                        "packages": {"build": ["gcc", "gcc-c++", "git", "cmake"], "runtime": []},
                        "install": {
                            "build": "sudo dnf install -y gcc gcc-c++ git cmake",
                            "runtime": "true",
                        },
                    },
                    "ubuntu": {
                        "releases": ["22.04", "24.04"],
                        "packages": {
                            "build": ["build-essential", "git", "cmake", "meson", "pkg-config"],
                            "runtime": [],
                        },
                        "install": {
                            "build": "sudo apt-get update && sudo apt-get install -y build-essential git cmake meson pkg-config",
                            "runtime": "true",
                        },
                    },
                },
            },
            "macos": {"notes": "Secondary; prefer Linux farm hosts."},
            "windows": {"notes": "Use WSL2."},
        },
    }


def write_app(entry: tuple, *, force: bool = False) -> str:
    typ, name, display, langs, build, ver, url, ref, test, workload, desc = entry
    app_dir = APPS / typ / name
    app_json = app_dir / "app.json"
    if app_json.is_file() and not force:
        # keep rich trees (mongodb/mysql/...) — only ensure at least one version exists
        versions = app_dir / "versions"
        if versions.is_dir() and any(versions.iterdir()):
            return "skip"
    app_dir.mkdir(parents=True, exist_ok=True)
    identity = {
        "id": f"{typ}/{name}",
        "type": typ,
        "name": name,
        "display_name": display,
        "languages": langs,
        "build_systems": [build],
        "default_version": ver,
        "correctness": "smoke",
        "perf_backend": "cpu",
        "description": desc,
        "flags": {"cflags": [], "cxxflags": [], "ldflags": []},
    }
    app_json.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")

    vdir = app_dir / "versions" / ver
    if vdir.is_dir() and not force and (vdir / "recipe.json").is_file():
        return "exists"
    vdir.mkdir(parents=True, exist_ok=True)
    life = {
        "version": ver,
        "channel": "stable",
        "released": None,
        "security_support_ends": None,
        "support_ended": None,
        "status": "unknown",
        "source": "catalog-seed",
        "notes": "Best-effort pin from app_catalog; refine via endoflife.date as needed.",
    }
    (vdir / "lifecycle.json").write_text(json.dumps(life, indent=2) + "\n", encoding="utf-8")
    (vdir / "dependencies.yaml").write_text(dump_yaml(generic_deps(ver, name)), encoding="utf-8")
    (vdir / "recipe.json").write_text(
        json.dumps(recipe_for(build, ver, url, ref, test, workload), indent=2) + "\n",
        encoding="utf-8",
    )
    (vdir / "README.md").write_text(
        textwrap.dedent(
            f"""\
            # {display} {ver}

            Catalog-seeded compiler-farm app. Refine lifecycle/deps as needed.

            - Source: `{url}` @ `{ref}`
            - Build: `{build}`
            """
        ),
        encoding="utf-8",
    )
    return "added"


def main() -> None:
    force = "--force" in __import__("sys").argv
    # persist catalog
    catalog = []
    for e in RAW:
        typ, name, display, langs, build, ver, url, ref, test, workload, desc = e
        catalog.append(
            {
                "id": f"{typ}/{name}",
                "type": typ,
                "name": name,
                "display_name": display,
                "languages": langs,
                "build": build,
                "default_version": ver,
                "source": {"url": url, "ref": ref},
                "description": desc,
            }
        )
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    CATALOG.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

    counts = {"added": 0, "skip": 0, "exists": 0}
    for e in sorted(RAW, key=lambda x: (x[0], x[1])):
        status = write_app(e, force=force)
        counts[status] = counts.get(status, 0) + 1

    total = len(list(APPS.glob("*/*/app.json")))
    print(f"catalog entries: {len(RAW)}")
    print(f"write: {counts}")
    print(f"apps on disk: {total}")
    print(f"catalog file: {CATALOG}")


if __name__ == "__main__":
    main()
