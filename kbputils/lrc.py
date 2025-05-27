import re
import charset_normalizer

class LRC:
    def __init__(self, lrcfile: str):
        self.lines = []
        self.tags = {}
        # TODO: look into only opening the file once
        with open(lrcfile, 'rb') as f:
            # Use this instead of from_path because it returns UTF-8-SIG if there's a BOM, where .best().encoding doesn't
            encoding = charset_normalizer.detect(f.read())['encoding']
        with open(lrcfile, 'r', encoding=encoding) as f:
            for lrcline in f:
                lrcline = lrcline.rstrip("\r\n")
                if re.fullmatch(r'\[\d{2}:\d{2}.\d{2}\]\s+(<\d{2}:\d{2}.\d{2}>[^<>]*)+<\d{2}:\d{2}.\d{2}>', lrcline):
                    # Ignore the line start times for now - they aren't usually going to be helpful when redoing
                    # layout anyway and some programs don't set them to good values (e.g. KBS LRC export)
                    syls = re.findall(r'<(\d{2}):(\d{2}).(\d{2})>([^<>]*)', lrcline)
                    self.lines.append([(self.time_to_ms(*syls[i][:3]), self.time_to_ms(*syls[i+1][:3]), syls[i][3]) for i in range(len(syls)-1)])
                # For some reason karlyriceditor does [..:..:..]WORD <..:..:..>WORD <..:..:..>
                elif re.fullmatch(r'\[\d{2}:\d{2}.\d{2}\]([^<>]*<\d{2}:\d{2}.\d{2}>)+', lrcline):
                    syls = re.findall(r'[<\[](\d{2}):(\d{2}).(\d{2})[>\]]([^<>]*)', lrcline)
                    self.lines.append([(self.time_to_ms(*syls[i][:3]), self.time_to_ms(*syls[i+1][:3]), syls[i][3]) for i in range(len(syls)-1)])
                elif res := re.fullmatch(r'\[([^\[\]]+)\s*:([^\[\]]+)\]', lrcline):
                    self.tags[res.group(1)] = res.group(2)
                # I don't think this is standard, but it seems to be used as a page break some places
                elif lrcline == '':
                    if self.lines[-1] != []:
                        self.lines.append([])
                else:
                    raise ValueError(f"Invalid LRC line encountered:\n{lrcline}")
            if 'offset' in self.tags:
                offset = int(self.tags.pop('offset'))
                for line in self.lines:
                    for i in range(len(line)):
                        line[i] = (line[i][0] - offset, line[i][1] - offset, line[i][2])

    @staticmethod
    def time_to_ms(m: str, s: str, cs: str) -> int:
        return int(cs)*10 + 1000*int(s) + 60*1000*int(m)
