import re

class DoblonTxt:
    def __init__(self, txtfile: str):
        lines = []
        line = []
        with open(txtfile, 'r') as f:
            for syl in f:
                start, stop, text = syl.rstrip("\n").split('-', maxsplit=2)
                while text.startswith("\\n"):
                    lines.append(line)
                    line = []
                    text = text[2:]
                line.append((self.time_to_ms(start),self.time_to_ms(stop),text))
                while text.endswith("\\n"):
                    text = text[:-2]
                    line[-1]=(self.time_to_ms(start), self.time_to_ms(stop), text)
                    lines.append(line)
                    line = []
        self.lines = lines

    @staticmethod
    def time_to_ms(timestamp: str) -> int:
        r = re.match(r'(\d+:)?(\d+)\.(\d+)', timestamp)
        return int(r.group(3)) + 1000 * int(r.group(2)) + (60 * 1000 * int(r.group(1)[:-1]) if r.group(1) else 0)
