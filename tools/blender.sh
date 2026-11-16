# shellcheck shell=bash
# Sourced by the mise tasks that need Blender and the build scripts' helpers.
# Each check prints nothing when the piece is there, else one line saying
# what is missing and how to get it.

# The Grease Pencil drawing API the build scripts use (drawing.add_strokes,
# per-stroke attributes) arrived with Blender 4.3.
BLENDER_MIN_MAJOR=4
BLENDER_MIN_MINOR=3

# Prints Blender's executable. macOS installs it as an app bundle, off PATH.
find_blender() {
  local c
  for c in "${BLENDER:-blender}" /Applications/Blender.app/Contents/MacOS/Blender; do
    command -v "$c" && return 0
  done
  return 1
}

# Prints a PATH under which Blender's Python finds its own standard library.
# A distribution's Blender uses the system Python and locates its home through
# PATH, so another python3.X of the same version earlier on PATH (uv's, or
# mise's for this repo) gives it a standard library without the C modules it
# expects; the system directories alone fix that.
blender_python_path() {
  local p
  for p in "$PATH" "/usr/local/bin:/usr/bin:/bin"; do
    if PATH="$p" "$1" -b --factory-startup --python-exit-code 1 --python-expr "import math" >/dev/null 2>&1; then
      echo "$p"
      return 0
    fi
  done
  return 1
}

check_blender() {
  local blender version major minor
  if ! blender="$(find_blender)"; then
    echo "blender not found: install Blender ${BLENDER_MIN_MAJOR}.${BLENDER_MIN_MINOR} or newer (https://www.blender.org/download/) or set BLENDER to its executable"
    return
  fi
  version="$("$blender" --version 2>/dev/null | sed -n 's/^Blender \([0-9][0-9]*\)\.\([0-9][0-9]*\).*/\1.\2/p' | head -n 1)"
  major="${version%%.*}"
  minor="${version#*.}"
  if [ -z "$version" ]; then
    echo "blender: $blender did not report its version; set BLENDER to Blender's executable"
  elif [ "$major" -lt "$BLENDER_MIN_MAJOR" ] || { [ "$major" -eq "$BLENDER_MIN_MAJOR" ] && [ "$minor" -lt "$BLENDER_MIN_MINOR" ]; }; then
    echo "blender: $blender is $version; the build scripts need ${BLENDER_MIN_MAJOR}.${BLENDER_MIN_MINOR} or newer (https://www.blender.org/download/)"
  elif ! blender_python_path "$blender" >/dev/null; then
    echo "blender: $blender's Python cannot import its standard library; install Blender from https://www.blender.org/download/ (it bundles its own Python)"
  fi
}

check_bx_gp() {
  local dir="${LOTTIE_GP_SCRIPTS:-}"
  if [ -z "$dir" ]; then
    echo "bx_gp not found: set LOTTIE_GP_SCRIPTS to the folder holding bx_gp.py (the Grease Pencil helpers the scripts were written with; ask the animation's author, they are not published)"
  elif [ ! -f "$dir/bx_gp.py" ] && [ ! -f "$dir/bx_gp/__init__.py" ]; then
    echo "bx_gp not found: LOTTIE_GP_SCRIPTS=$dir holds no bx_gp.py"
  fi
}

check_lottie_addon() {
  local dir="${LOTTIE_EXPORT_ADDON_DIR:-}" blender path
  if [ -n "$dir" ]; then
    [ -f "$dir/io_lottie_export/__init__.py" ] && return
    echo "io_lottie_export not found: LOTTIE_EXPORT_ADDON_DIR=$dir holds no io_lottie_export/ (use the svg_blender_lottie folder of https://gitlab.com/multlabs/svg-grease-pencil-lottie-workflow)"
    return
  fi
  # Without the variable the add-on can still be on Blender's own module path.
  if blender="$(find_blender)" && path="$(blender_python_path "$blender")" \
    && PATH="$path" "$blender" -b --factory-startup --python-exit-code 1 --python-expr "import io_lottie_export" >/dev/null 2>&1; then
    return
  fi
  echo "io_lottie_export not found: clone https://gitlab.com/multlabs/svg-grease-pencil-lottie-workflow and set LOTTIE_EXPORT_ADDON_DIR to its svg_blender_lottie folder"
}

check_avatar_svg() {
  local svg="${HAL_C2_AVATAR_SVG:-}"
  if [ -z "$svg" ]; then
    echo "avatar SVG not set: download https://github.com/hal-c2/hal-c2/blob/main/assets/brand/hal-c2-avatar.svg and set HAL_C2_AVATAR_SVG to it"
  elif [ ! -f "$svg" ]; then
    echo "avatar SVG not found: HAL_C2_AVATAR_SVG=$svg is not a file (get it from https://github.com/hal-c2/hal-c2/blob/main/assets/brand/hal-c2-avatar.svg)"
  fi
}
