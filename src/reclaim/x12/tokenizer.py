class X12ParseError(Exception):
    pass


class Segment:
    __slots__ = ("id", "elements")

    def __init__(self, id_: str, elements: list[str]):
        self.id = id_
        self.elements = elements

    def el(self, index: int, default: str = "") -> str:
        return self.elements[index] if index < len(self.elements) else default

    def __repr__(self) -> str:
        return f"Segment({self.id!r}, {self.elements!r})"


def tokenize(text: str) -> list[Segment]:
    """Tokenize raw X12 text into segments, reading delimiters from ISA.

    ISA is a fixed-width segment: element separator is text[3], segment
    terminator is the character right after the 105-char ISA content
    (i.e. text[105]), component separator is ISA16 (text[104]).
    """
    if len(text) < 106:
        raise X12ParseError("truncated ISA segment: input shorter than 106 characters")
    if not text.startswith("ISA"):
        raise X12ParseError("input does not start with ISA")

    element_sep = text[3]
    segment_term = text[105]

    body = text.replace("\r\n", "").replace("\n", "")
    raw_segments = [s for s in body.split(segment_term) if s.strip() != ""]

    segments: list[Segment] = []
    for raw in raw_segments:
        raw = raw.strip()
        if not raw:
            continue
        elements = raw.split(element_sep)
        segments.append(Segment(elements[0], elements[1:]))
    if not segments or segments[0].id != "ISA":
        raise X12ParseError("truncated ISA segment: could not parse ISA")
    return segments
