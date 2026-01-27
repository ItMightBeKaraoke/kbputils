from . import validators

class Dimension(tuple):
    @validators.validated_types(coerce_types=False)
    def __new__(cls, x: str|int, y: str|int):
        return super().__new__(cls, (int(x), int(y)))

    def width(self) -> int:
        return self[0]

    def height(self) -> int:
        return self[1]

    def __repr__(self) -> str:
        return f"{self[0]}x{self[1]}"

