# nginx file-descriptor limit (main server)

## Symptom

Intermittent "connect, then no internet" outages and sporadic `502` on the
subscription endpoint. `/var/log/nginx/error.log` showed thousands of:

```
accept4() failed (24: Too many open files)
socket() failed (24: Too many open files) while connecting to upstream 127.0.0.1:10443
```

(6264 occurrences in a single day). When nginx runs out of file descriptors it
cannot accept new TLS connections or open sockets to the Reality upstream
(`127.0.0.1:10443`), so clients complete the handshake but get no data.

## Cause

nginx did not set `worker_rlimit_nofile`, so each worker inherited the default
soft limit of **1024** open files (even though the systemd unit allows
`LimitNOFILE=524288`). nginx only raises its own soft limit when
`worker_rlimit_nofile` is set.

## Fix (applied to `/etc/nginx/nginx.conf`)

```nginx
worker_processes auto;
worker_rlimit_nofile 262144;   # added — lets workers use the FDs systemd allows

events {
    worker_connections 16384;  # raised from 4096
}
```

Then `nginx -t && systemctl reload nginx`. Verify with:

```
for p in $(pgrep -P $(cat /run/nginx.pid)); do grep "Max open files" /proc/$p/limits; done
# -> 262144 (soft) / 262144 (hard)
```
