from __future__ import annotations

from dataclasses import dataclass
import importlib
import os
from pathlib import Path
import sys
from typing import Callable, Mapping


class QtRuntimeError(RuntimeError):
    """Raised when the bundled PyQt5 Windows runtime is incomplete."""


@dataclass(frozen=True)
class QtRuntimeInfo:
    pyqt_root: Path
    plugin_root: Path
    platform_dir: Path
    bin_dir: Path | None
    environment: Mapping[str, str]


_DLL_HANDLES: list[object] = []


def _resolve_pyqt_root(pyqt_root: Path | None) -> Path:
    if pyqt_root is not None:
        return Path(pyqt_root).resolve()
    package = importlib.import_module("PyQt5")
    package_file = getattr(package, "__file__", None)
    if not package_file:
        raise QtRuntimeError("PyQt5 package location could not be determined")
    return Path(package_file).resolve().parent


def _find_windows_plugin(pyqt_root: Path) -> tuple[Path, Path]:
    plugin_roots = (
        pyqt_root / "Qt5" / "plugins",
        pyqt_root / "Qt" / "plugins",
        pyqt_root / "plugins",
    )
    for plugin_root in plugin_roots:
        platform_dir = plugin_root / "platforms"
        if (platform_dir / "qwindows.dll").is_file():
            return plugin_root, platform_dir
    searched = ", ".join(str(root / "platforms" / "qwindows.dll") for root in plugin_roots)
    raise QtRuntimeError(f"qwindows.dll was not found. Searched: {searched}")


def _find_qt_bin(pyqt_root: Path) -> Path | None:
    candidates = (
        pyqt_root / "Qt5" / "bin",
        pyqt_root / "Qt" / "bin",
        pyqt_root,
    )
    return next((path for path in candidates if path.is_dir()), None)


def configure_qt_runtime(
    *,
    pyqt_root: Path | None = None,
    platform: str | None = None,
    add_dll_directory: Callable[[str], object] | None = None,
) -> QtRuntimeInfo | None:
    """Configure the PyQt5 plugin and DLL search paths before QApplication.

    On Windows this deliberately ignores any inherited QT_PLUGIN_PATH because a
    global Qt installation can make a venv-backed PyQt5 load the wrong plugins.
    """

    active_platform = sys.platform if platform is None else platform
    if not active_platform.startswith("win"):
        return None

    root = _resolve_pyqt_root(pyqt_root)
    plugin_root, platform_dir = _find_windows_plugin(root)
    bin_dir = _find_qt_bin(root)

    os.environ.pop("QT_PLUGIN_PATH", None)
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platform_dir)
    os.environ["QT_QPA_PLATFORM"] = "windows"
    # Prefer Windows' software renderer. This avoids native 0xC0000005 crashes
    # caused by incompatible OpenGL/GPU drivers on workshop PCs.
    os.environ.setdefault("QT_OPENGL", "software")
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    os.environ.setdefault("QT_ANGLE_PLATFORM", "warp")

    if bin_dir is not None:
        current_path = os.environ.get("PATH", "")
        parts = [part for part in current_path.split(";") if part]
        if str(bin_dir).lower() not in {part.lower() for part in parts}:
            os.environ["PATH"] = str(bin_dir) + (";" + current_path if current_path else "")

        dll_adder = add_dll_directory
        if dll_adder is None and hasattr(os, "add_dll_directory"):
            dll_adder = os.add_dll_directory
        if dll_adder is not None:
            try:
                _DLL_HANDLES.append(dll_adder(str(bin_dir)))
            except (FileNotFoundError, OSError):
                # PATH remains a fallback and PyQt5 has its own DLL bootstrap.
                pass

    return QtRuntimeInfo(
        pyqt_root=root,
        plugin_root=plugin_root,
        platform_dir=platform_dir,
        bin_dir=bin_dir,
        environment=dict(os.environ),
    )
