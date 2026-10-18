#!/usr/bin/env bash
# Serves one code tour folder on 127.0.0.1 only. Browsers block the tour page as a file:// URL.
#   bash serve.sh start <tour-dir> [port]    default: the first free port from 8765 to 8785
#   bash serve.sh stop  <tour-dir>
# The last line of start is the tour URL. When it is not port 8765, set KT_TOUR_URL to it for the take
# (another project's tour may hold 8765 on the same computer).
set -euo pipefail

cmd="${1:?usage: serve.sh start|stop <tour-dir> [port]}"
DIR="${2:?tour-dir}"
PIDFILE="$DIR/.server.pid"
busy() { python3 -c 'import socket,sys; s=socket.socket(); sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)' "$1"; }

case "$cmd" in
  start)
    # Already serving this folder: reuse it, so a second start never orphans the first server.
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null && [ -f "$DIR/.server.port" ]; then
      PORT="$(cat "$DIR/.server.port")"
      echo "already serving $DIR"
      [ "$PORT" = 8765 ] || echo "export KT_TOUR_URL=http://127.0.0.1:$PORT/ide.html for the take"
      echo "http://127.0.0.1:$PORT/ide.html"
      exit 0
    fi
    if [ -n "${3:-}" ]; then
      PORT="$3"
      if busy "$PORT"; then echo "port $PORT is busy"; exit 1; fi
    else
      PORT=""
      for p in $(seq 8765 8785); do busy "$p" || { PORT="$p"; break; }; done
      [ -n "$PORT" ] || { echo "ports 8765 to 8785 are all busy"; exit 1; }
    fi
    python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$DIR" >/dev/null 2>&1 &
    echo $! > "$PIDFILE"
    echo "$PORT" > "$DIR/.server.port"
    for _ in $(seq 1 20); do
      if curl -s -o /dev/null "http://127.0.0.1:$PORT/ide.html"; then
        echo "serving $DIR"
        [ "$PORT" = 8765 ] || echo "port 8765 was busy: export KT_TOUR_URL=http://127.0.0.1:$PORT/ide.html for the take"
        echo "http://127.0.0.1:$PORT/ide.html"
        exit 0
      fi
      sleep 0.3
    done
    echo "server did not start"; exit 1
    ;;
  stop)
    if [ -f "$PIDFILE" ]; then kill "$(cat "$PIDFILE")" 2>/dev/null || true; rm -f "$PIDFILE" "$DIR/.server.port"; fi
    echo "stopped server for $DIR"
    ;;
  *) echo "unknown command: $cmd"; exit 1 ;;
esac
