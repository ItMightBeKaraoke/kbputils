import re
import charset_normalizer

__all__ = ['LRC', 'MLRCLine']

class LRC:
    def __init__(self, lrcfile: str):
        self.lines = []
        self.tags = {}
        midico = False
        # TODO: look into only opening the file once
        with open(lrcfile, 'rb') as f:
            # Use this instead of from_path because it returns UTF-8-SIG if there's a BOM, where .best().encoding doesn't
            encoding = charset_normalizer.detect(f.read())['encoding']
        with open(lrcfile, 'r', encoding=encoding) as f:
            for lrcline in f:
                lrcline = lrcline.rstrip("\r\n")

                if not midico and lrcline == '[re:MidiCo]':
                    # MidiCo uses a totally different format, so bail out and start again
                    self.parse_midico(f)
                    return

                if re.fullmatch(r'\[\d{2}:\d{2}.\d{2}\]\s+(<\d{2}:\d{2}.\d{2}>[^<>]*)+<\d{2}:\d{2}.\d{2}>', lrcline):
                    # Ignore the line start times for now - they aren't usually going to be helpful when redoing
                    # layout anyway and some programs don't set them to good values (e.g. KBS LRC export)
                    syls = re.findall(r'<(\d{2}):(\d{2}).(\d{2})>([^<>]*)', lrcline)
                    self.lines.append([(self.time_to_ms(*syls[i][:3]), self.time_to_ms(*syls[i+1][:3]), syls[i][3]) for i in range(len(syls)-1)])
                # For some reason karlyriceditor does [..:..:..]WORD <..:..:..>WORD <..:..:..>
                elif re.fullmatch(r'\[\d{2}:\d{2}.\d{2}\]([^<>]*<\d{2}:\d{2}.\d{2}>)+', lrcline):
                    syls = re.findall(r'[<\[](\d{2}):(\d{2}).(\d{2})[>\]]([^<>]*)', lrcline)
                    self.lines.append([(self.time_to_ms(*syls[i][:3]), self.time_to_ms(*syls[i+1][:3]), syls[i][3]) for i in range(len(syls)-1)])
                elif res := re.fullmatch(r'\[([^\[\]]+)\s*:([^\[\]]*)\]', lrcline):
                    self.tags[res.group(1)] = res.group(2)
                # I don't think this is standard, but it seems to be used as a page break some places
                elif lrcline == '':
                    if self.lines and self.lines[-1] != []:
                        self.lines.append([])
                else:
                    raise ValueError(f"Invalid Enhanced LRC line encountered:\n{lrcline}")
            if 'offset' in self.tags:
                offset = int(self.tags.pop('offset'))
                for line in self.lines:
                    for i in range(len(line)):
                        line[i] = (line[i][0] - offset, line[i][1] - offset, line[i][2])

    def parse_midico(self, f):
        parted_syls = {}
        for sylline in f:
            sylline = sylline.rstrip("\r\n")

            if sylline == '[re:MidiCo]':
                continue
            elif (matches := re.fullmatch(r'\[(\d{2}):(\d{2}).(\d+)\](\d+):(/?)(.*)', sylline)):
                start = self.time_to_ms(*matches.groups()[:3])
                part = int(matches.group(4))
                newline = bool(matches.group(5))
                syl = matches.group(6)
                if newline and part in parted_syls:
                    self.midico_ordered_insert(MLRCLine(parted_syls.pop(part), part=part))
                # Temporarily fill in end of syllable timing as start + 1s
                parted_syls[part] = (parted_syls[part] if part in parted_syls else []) + [(start, start + 1000, syl)]
                # Fill in time for previous syllable with the start of current if there is one
                if len(parted_syls[part]) > 1:
                    parted_syls[part][-2] = (parted_syls[part][-2][0], start - 10, parted_syls[part][-2][2])
            else:
                raise ValueError(f"Invalid midiCo LRC line:\n{sylline}")

        # Add in remaining lines
        for part in list(parted_syls.keys()):
            self.midico_ordered_insert(MLRCLine(parted_syls.pop(part), part=part))

    def midico_ordered_insert(self, line):
        # Most of the time the line will need to go near the end, so this should be better than binary search
        for i in range(len(self.lines)-1, -1, -1):
            if self.lines[i][0][0] < line[0][0]:
                self.lines.insert(i+1, line)
                if 0 < self.lines[i][-1][1] - line[0][0] < 1000:
                    self.lines[i][-1] = (self.lines[i][-1][0], line[0][0] - 10, self.lines[i][-1][2])
                return
        self.lines.insert(0, line)

    @staticmethod
    def time_to_ms(m: str, s: str, decimal: str) -> int:
        return int(decimal) * 10**(3-len(decimal)) + 1000*int(s) + 60*1000*int(m)

# Behave entirely like a normal list of syllables, but have a part attribute for the MidiCo duet parts
class MLRCLine(list):
    def __init__(self, *args, part: int = 1, **kwargs):
        super().__init__(*args, **kwargs)
        self.part = part

    def __repr__(self):
        return f"{self.part}: {super().__repr__()}"
