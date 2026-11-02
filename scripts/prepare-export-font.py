"""Build the bundled static OFL font from NotoSansSC-VF.ttf using fonttools 4.60.1."""

import argparse
from copy import deepcopy
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont


def build_font(source: Path, output: Path) -> None:
    """Preserve outlines and Unicode aliases; refuse overwriting any existing output."""
    if output.exists():
        raise FileExistsError("Choose a new output path; compare before replacing the bundled font")
    font = TTFont(source)
    instantiateVariableFont(font, {"wght": 400}, inplace=True)
    order = list(font.getGlyphOrder())
    seen: dict[str, int] = {}
    mapping: dict[int, str] = {}
    for code_point, glyph in sorted(font.getBestCmap().items()):
        if glyph in seen and seen[glyph] != code_point:
            name = f"uniExport{code_point:X}"
            font["glyf"][name] = deepcopy(font["glyf"][glyph])
            font["hmtx"][name] = font["hmtx"][glyph]
            if "vmtx" in font:
                font["vmtx"][name] = font["vmtx"][glyph]
            order.append(name)
            mapping[code_point] = name
        else:
            seen[glyph] = code_point
    # PDFBox's reverse glyph lookup otherwise maps some ordinary Chinese
    # characters to equivalent radical code points during text extraction.
    for table in font["cmap"].tables:
        if table.isUnicode() and table.format != 14:
            for code_point, name in mapping.items():
                if code_point in table.cmap:
                    table.cmap[code_point] = name
    font.setGlyphOrder(order)
    font["glyf"].glyphOrder = order
    font.save(output)
    font.close()


def main() -> None:
    """Read an explicitly supplied upstream font and write a new static font file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build_font(args.input, args.output)


if __name__ == "__main__":
    main()
