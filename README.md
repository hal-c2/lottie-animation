# lottie-animation

The HAL-C2 avatar animations (dance and genie), drawn in Blender Grease Pencil and exported to Lottie.

- `version1/` and `version2/` hold each animation as `.json`, `.lottie`, `.blend` and GIF.
- Lottie 5.5.6, 24 fps, 512×512.

## Getting started

You need [mise](https://mise.jdx.dev). Every task below runs from the repository root.

```sh
mise run setup        # install the pinned Python, then report which optional pieces are present
mise run check        # validate every animation without a GUI
mise run test         # check, then load every animation in Qt's Lottie player off-screen
mise run run          # play version2/hal-c2-dance.json in a window; click to pause
```

- `mise run check` checks each `.json` (Lottie version in `v`, `fr` 24, `w` and `h` 512, `ip` below `op`, at least one layer), that each `.lottie` is a dotLottie archive whose manifest names an animation equal to the sibling `.json`, and that every animation has its `.blend` and preview GIF. A failure names the file and the rule.
- `mise run test` needs Qt 6's `qml` runtime with `Qt.labs.lottieqt` (Ubuntu/Debian: `qml-qt6 qml6-module-qtquick qml6-module-qtquick-window qml6-module-qt-labs-lottieqt`; Arch: `qt6-declarative qt6-lottie`; macOS: `brew install qt`). It loads each `.json`; Qt's player does not read `.lottie` archives, which `check` covers. `mise run test --no-qt` runs `check` alone.
- `mise run run [file] [--qt]` plays any `.json` or `.lottie` with `ljos run` when [`ljos`](https://github.com/hal-c2/ljos-ui) is on `PATH`, otherwise with Qt's `qml`; `--qt` forces Qt. The status line shows the player's state, frame rate and frame range.
- `mise run build <version1|version2> <dance|genie> [out_dir]` rebuilds one animation's `.blend`, `.json` and `.lottie` with Blender headless, into `build/<version>/` unless you name another folder. It needs Blender 4.3 or newer and three things this repository does not hold, given through the environment:
  - `LOTTIE_GP_SCRIPTS`: the folder holding `bx_gp.py`, the Grease Pencil helpers the scripts were written with (not published);
  - `LOTTIE_EXPORT_ADDON_DIR`: the `svg_blender_lottie` folder of [svg-grease-pencil-lottie-workflow](https://gitlab.com/multlabs/svg-grease-pencil-lottie-workflow), which holds the `io_lottie_export` add-on (not needed when Blender already imports it);
  - `HAL_C2_AVATAR_SVG`: [`hal-c2-avatar.svg`](https://github.com/hal-c2/hal-c2/blob/main/assets/brand/hal-c2-avatar.svg).

  Review renders go to `LOTTIE_WORK_DIR` (default: the temp directory). `mise run setup` reports each of these, and `build` names every missing one before it starts Blender.
- `mise run tasks:smoke` runs every task in a quick, non-interactive mode, as CI does.

## Licence

MIT, see [LICENSE](LICENSE).
