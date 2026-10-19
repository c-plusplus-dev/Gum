"""
Extension discovery/loading for Gum.

An "extension" is native C++/Obj-C++ code that a specific widget needs
(hardware access, codecs, anything not appropriate for the general-purpose
gum-builtins.hpp) that gumc pulls into the compiled widget binary when the
widget's .gum source does `import <extension_name>`.

Extensions live at:

    ~/Library/Application Support/Widgies/extensions/<WidgetName>/extension.toml

The extension folder name MUST match the widget's own folder name (i.e. the
grandparent directory of the .gum file being compiled, since widgets are
laid out as <WidgetName>/src/main.gum). This keeps extensions scoped to the
widget that owns them -- no shared/global extension namespace to manage.

extension.toml layout:

    name = "cpu_codec"          # must match the `import <name>` in the .gum file
    headers = ["GumExtension.hpp"]
    sources = ["CpuCodec.cpp"]  # additional .cpp/.mm files to compile in
    frameworks = []             # e.g. ["Cocoa", "CoreGraphics"] if needed

    [functions.decodeCpuUsages]
    params = ["str"]
    return = "List<int>"        # raw C++ type as it should appear in generated code
"""

import tomllib
from pathlib import Path

EXTENSIONS_ROOT = Path.home() / "Library" / "Application Support" / "Widgies" / "extensions"


def _widget_name_for(gum_filepath: str) -> str | None:
    """Widgets are laid out as <WidgetName>/src/<file>.gum -- the widget
    name is the grandparent directory of the .gum file being compiled."""
    if not gum_filepath:
        return None
    try:
        return Path(gum_filepath).resolve().parent.parent.name
    except Exception:
        return None


def load_extension(gum_filepath: str, module_name: str) -> dict | None:
    """Attempts to resolve `import module_name` (as seen inside
    gum_filepath) to an extension manifest. Returns None if no matching
    extension exists, in which case the caller should fall back to
    treating the import as a plain .gum file import."""
    widget_name = _widget_name_for(gum_filepath)
    if not widget_name:
        return None

    ext_dir = EXTENSIONS_ROOT / widget_name
    manifest_path = ext_dir / "extension.toml"
    if not manifest_path.is_file():
        return None

    with open(manifest_path, "rb") as f:
        manifest = tomllib.load(f)

    if manifest.get("name") != module_name:
        return None

    # Headers are referenced in generated code by basename only (gumc adds
    # -I <ext_dir> to the compile command), so #include stays portable.
    header_names = [Path(h).name for h in manifest.get("headers", [])]
    sources = [ext_dir / s for s in manifest.get("sources", [])]

    return {
        "name": module_name,
        "widget_name": widget_name,
        "dir": ext_dir,
        "headers": header_names,
        "sources": sources,
        "frameworks": manifest.get("frameworks", []),
        "functions": manifest.get("functions", {}),
    }
