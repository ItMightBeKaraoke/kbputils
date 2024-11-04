import re
import charset_normalizer


class LRC:
    def __init__(self, lrcfile: str):
        self.lines = []
        self.tags = {}
        self.is_midico = False

        # Detect MidiCo format
        with open(lrcfile, "r", encoding='utf-8-sig') as f:
            first_line = f.readline().strip()
            if first_line == "[re:MidiCo]":
                self.is_midico = True

        # TODO: look into only opening the file once
        with open(lrcfile, "r", encoding='utf-8-sig') as f:
            current_line = []
            for lrcline in f:
                lrcline = lrcline.rstrip("\r\n")

                if self.is_midico:
                    self.process_midico_line(lrcline, current_line)
                else:
                    self.process_enhanced_lrc_line(lrcline)

        # Process any remaining syllables in the current line for MidiCo format
        if self.is_midico and current_line:
            self.lines.append(current_line)

        if "offset" in self.tags:
            offset = int(self.tags.pop("offset"))
            for line in self.lines:
                for i in range(len(line)):
                    line[i] = (line[i][0] - offset, line[i][1] - offset, line[i][2])

    def process_midico_line(self, lrcline, current_line):
        if res := re.match(r"\[(\d{2}):(\d{2}).(\d{2,3})\](\d+):/(.*)", lrcline):
            # New line starts
            if current_line:
                self.lines.append(current_line)
                current_line.clear()
            m, s, ms, _, lyric = res.groups()
            start_time = self.time_to_ms(m, s, ms)
            current_line.append((start_time, start_time, lyric.strip()))
        elif res := re.match(r"\[(\d{2}):(\d{2}).(\d{2,3})\](\d+):(.*)", lrcline):
            m, s, ms, _, lyric = res.groups()
            start_time = self.time_to_ms(m, s, ms)
            if current_line:
                current_line[-1] = (current_line[-1][0], start_time, current_line[-1][2])
            current_line.append((start_time, start_time, lyric.strip()))
        elif res := re.match(r"\[([^\[\]]+)\s*:([^\[\]]+)\]", lrcline):
            self.tags[res.group(1)] = res.group(2)

    def process_enhanced_lrc_line(self, lrcline):
        if re.fullmatch(r"\[\d{2}:\d{2}.\d{2}\]\s+(<\d{2}:\d{2}.\d{2}>[^<>]*)+<\d{2}:\d{2}.\d{2}>", lrcline):
            # Ignore the line start times for now - they aren't usually going to be helpful when redoing
            # layout anyway and some programs don't set them to good values (e.g. KBS LRC export)
            syls = re.findall(r"<(\d{2}):(\d{2}).(\d{2})>([^<>]*)", lrcline)
            self.lines.append(
                [(self.time_to_ms(*syls[i][:3]), self.time_to_ms(*syls[i + 1][:3]), syls[i][3]) for i in range(len(syls) - 1)]
            )
        # For some reason karlyriceditor does [..:..:..]WORD <..:..:..>WORD <..:..:..>
        elif re.fullmatch(r"\[\d{2}:\d{2}.\d{2}\]([^<>]*<\d{2}:\d{2}.\d{2}>)+", lrcline):
            syls = re.findall(r"[<\[](\d{2}):(\d{2}).(\d{2})[>\]]([^<>]*)", lrcline)
            self.lines.append(
                [(self.time_to_ms(*syls[i][:3]), self.time_to_ms(*syls[i + 1][:3]), syls[i][3]) for i in range(len(syls) - 1)]
            )
        elif res := re.fullmatch(r"\[([^\[\]]+)\s*:([^\[\]]+)\]", lrcline):
            self.tags[res.group(1)] = res.group(2)
        elif res := re.fullmatch(r"\[(.+):(.*)\]", lrcline):
            self.tags[res.group(1)] = res.group(2)
        # I don't think this is standard, but it seems to be used as a page break some places
        elif lrcline == "":
            if self.lines and self.lines[-1] != []:
                self.lines.append([])
        else:
            raise ValueError(f"Invalid LRC line encountered:\n{lrcline}")

    @staticmethod
    def time_to_ms(m: str, s: str, ms: str) -> int:
        return int(ms.ljust(3, "0")[:3]) + 1000 * int(s) + 60 * 1000 * int(m)
