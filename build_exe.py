"""Build a one-file executable for the Portfolio Tool using PyInstaller."""

from __future__ import annotations

import os
import platform
import tempfile
from pathlib import Path

import PyInstaller.__main__

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11
    import tomli as tomllib  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parent

HIDDEN_IMPORTS = [
    "pandas._libs.tslibs.timedeltas",
    "pandas._libs.tslibs.nattype",
    "pandas._libs.tslibs.np_datetime",
    "dateutil.tz",
    "zoneinfo",
    "yfinance",
    "yahooquery",
    "sqlalchemy.dialects.sqlite",
]


def read_version() -> str:
    data = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def build_version_file(version: str) -> Path:
    major, minor, patch, *_ = (version.split(".") + ["0", "0"])[:4]
    version_tuple = ", ".join([major, minor, patch, "0"])
    template = f"""
# UTF-8
#
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version_tuple}),
    prodvers=({version_tuple}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        "040904B0",
        [
          StringStruct("CompanyName", "StockTrak"),
          StringStruct("FileDescription", "Portfolio Tool"),
          StringStruct("FileVersion", "{version}"),
          StringStruct("InternalName", "portfolio"),
          StringStruct("OriginalFilename", "portfolio.exe"),
          StringStruct("ProductName", "Portfolio Tool"),
          StringStruct("ProductVersion", "{version}")
        ]
      )
    ]),
    VarFileInfo([VarStruct("Translation", [1033, 1200])])
  ]
)
"""
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt")
    handle.write(template.strip())
    handle.flush()
    handle.close()
    return Path(handle.name)


def find_data_files() -> list[str]:
    entries: list[str] = []
    try:
        import tzdata  # type: ignore
    except ImportError:
        tzdata_path = None
    else:
        tzdata_path = Path(tzdata.__file__).resolve().parent
    if tzdata_path and tzdata_path.exists():
        entries.append(f"{tzdata_path}{os.pathsep}tzdata")
    return entries


def main() -> None:
    version = read_version()
    version_file = build_version_file(version)
    args = ["--clean", "--onefile", "--name", "portfolio"]
    for hidden in HIDDEN_IMPORTS:
        args.extend(["--hidden-import", hidden])
    for data_entry in find_data_files():
        args.extend(["--add-data", data_entry])

    icon_path = PROJECT_ROOT / "ui" / "icon.ico"
    if icon_path.exists():
        args.extend(["--icon", str(icon_path)])

    if platform.system() == "Windows":
        args.extend(["--version-file", str(version_file)])

    args.append(str(PROJECT_ROOT / "entry.py"))
    try:
        PyInstaller.__main__.run(args)
    finally:
        Path(version_file).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
