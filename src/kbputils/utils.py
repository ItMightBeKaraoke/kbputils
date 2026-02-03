import collections
import typing
import pathlib
import os
from . import validators

class Dimension(collections.namedtuple("Dimension", ('width', 'height'))):
    __annotations__  = {'width': int, 'height': int}

    @validators.validated_types(coerce_types=False)
    def __new__(cls, x: str|int, y: str|int|None = None):
        if y is None:
            (x,y) = x.split("x")
        return super().__new__(cls, int(x), int(y))

    def __repr__(self) -> str:
        return f"{self[0]}x{self[1]}"

    @validators.validated_types(coerce_types=False)
    def __add__(self, other: typing.Self | int) -> typing.Self:
        if isinstance(other, int):
            return Dimension(*(x + other for x in self))
        else:
            return Dimension(self[0] + other[0], self[1] + other[1])

    def __neg__(self) -> typing.Self:
        return Dimension(*(-x for x in self))

    def __sub__(self, other: typing.Self | int) -> typing.Self:
        return self + -other

if os.name == "nt":
    def abspath(path: str) -> pathlib.Path:
        return pathlib.Path(path).absolute()

else:
    import subprocess
    def abspath(path: str) -> pathlib.Path:
        wpath = pathlib.PureWindowsPath(path)
        if wpath.is_absolute():
            return pathlib.Path(subprocess.run(["winepath", "-u", path], capture_output=True, check=True).stdout)
        return pathlib.Path(wpath).absolute()
