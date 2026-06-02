import pathlib
import os
import sys

if os.name == "nt":
    def abspath(path: str, cwd: str | pathlib.Path | None = None) -> pathlib.Path:
        if cwd is None:
            return pathlib.Path(path).absolute()
        else:
            cwd = pathlib.Path(cwd)
            if not cwd.is_dir():
                cwd = cwd.parent
            return pathlib.Path(cwd, path).absolute()

else:
    import subprocess
    def abspath(path: str, cwd: str | pathlib.Path | None = None) -> pathlib.Path:
        wpath = pathlib.PureWindowsPath(path)
        if wpath.is_absolute():
            print("Using workaround for Windows absolute path (requires winepath)", file=sys.stderr)
            return pathlib.Path(subprocess.run(
                ["winepath", "-u", path],
                capture_output=True,
                check=True
            ).stdout.decode('utf-8').rstrip('\n'))
        if cwd is None:
            return pathlib.Path(wpath).absolute()
        else:
            cwd = pathlib.Path(cwd)
            if not cwd.is_dir():
                cwd = cwd.parent
            return pathlib.Path(cwd, wpath).absolute()
