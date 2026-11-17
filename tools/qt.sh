# shellcheck shell=bash
# Sourced by the mise tasks that play animations in Qt's Lottie player.

# shellcheck disable=SC2034 # read by the tasks that source this file
QT_LOTTIE_HELP="install Qt 6 with its Lottie module (Ubuntu/Debian: apt install qml-qt6 qml6-module-qtquick qml6-module-qtquick-window qml6-module-qtqml-workerscript qml6-module-qt-labs-lottieqt; Arch: pacman -S qt6-declarative qt6-lottie; macOS: brew install qt), or set QML to Qt 6's qml binary"

# Prints the path of Qt 6's qml runtime. Distributions name it differently:
# qml6 on Arch and Fedora, /usr/lib/qt6/bin/qml (off PATH) on Debian/Ubuntu,
# plain qml with Homebrew.
find_qml() {
  local c
  if [ -n "${QML:-}" ]; then
    command -v "$QML" && return 0
    return 1
  fi
  for c in qml6 /usr/lib/qt6/bin/qml; do
    command -v "$c" && return 0
  done
  if command -v qml >/dev/null 2>&1 && qml --version 2>&1 | grep -q 'qml 6\.'; then
    command -v qml
    return 0
  fi
  return 1
}

# Off-screen and headless: no window, no display, and no platform theme. A
# desktop's QT_QPA_PLATFORMTHEME=gtk3 makes Qt die with "cannot open display"
# when there is none, and journald-built Qt would swallow console output.
qt_offscreen_env() {
  unset WAYLAND_DISPLAY DISPLAY QT_QPA_PLATFORMTHEME
  export QT_QPA_PLATFORM=offscreen QT_FORCE_STDERR_LOGGING=1
}

# Prints why qml ($1) cannot import Qt.labs.lottieqt (Qt's own error line),
# or nothing when it can. Runs in a subshell so the off-screen settings stay
# out of the caller.
qt_lottie_problem() (
  qt_offscreen_env
  dir="$(mktemp -d)"
  trap 'rm -r "$dir"' EXIT
  printf 'import QtQuick\nimport Qt.labs.lottieqt\nItem { Component.onCompleted: Qt.quit() }\n' > "$dir/probe.qml"
  if ! bounded 30 "$1" "$dir/probe.qml" >"$dir/out" 2>&1; then
    # Qt names the missing module on a line like
    # 'file:///…/probe.qml: module "QtQml.WorkerScript" is not installed'.
    why="$(grep -m1 -E 'module|plugin|error|rror:' "$dir/out" | sed 's|^file://[^:]*: ||')"
    [ -n "$why" ] || why="$(tail -n1 "$dir/out")"
    printf '%s cannot import Qt.labs.lottieqt (%s)\n' "$1" "${why:-exited non-zero with no output}"
  fi
)

# Runs a command for at most $1 seconds. macOS has no timeout(1) unless
# coreutils is installed, so fall back to a watchdog there.
bounded() {
  local secs="$1" pid watchdog rc=0
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "$secs" "$@" || rc=$?
    return "$rc"
  fi
  "$@" &
  pid=$!
  (sleep "$secs" && kill "$pid" 2>/dev/null) &
  watchdog=$!
  wait "$pid" || rc=$?
  kill "$watchdog" 2>/dev/null || true
  return "$rc"
}
