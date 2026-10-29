"""Extract PHI Aeneid lines in the order printed by the Diogenes TEI export."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from lxml import etree

from .config import REPO_ROOT
from .stage1_latin import EXPORT_DIR, _line_text


def extract(xml_path: Path, author: str, work: str, expected: str) -> dict:
    raw = xml_path.read_bytes()
    tree = etree.fromstring(raw)
    source = " ".join(_line_text(node) for node in tree.xpath(".//*[local-name()='sourceDesc']"))
    if re.sub(r"\s+", " ", expected).strip() not in source:
        raise ValueError(f"sourceDesc mismatch in {xml_path}: {source!r}")
    books = []
    for div in tree.xpath(".//*[local-name()='div' and @type='book']"):
        n = div.get("n")
        if n == "t":
            continue
        if not n or not n.isdigit():
            raise ValueError(f"non-digit book number: {n!r}")
        rows, seen = [], set()
        for line in div.xpath(".//*[local-name()='l']"):
            line_n = line.get("n")
            if line_n == "t":
                continue
            if not line_n or line_n in seen:
                raise ValueError(f"duplicate or missing line number in book {n}: {line_n!r}")
            seen.add(line_n)
            value = _line_text(line)
            if not value:
                raise ValueError(f"empty text in book {n}, line {line_n}")
            rows.append({"n": line_n, "text": value})
        books.append({"book": int(n), "rows": rows})
    if [book["book"] for book in books] != list(range(1, len(books) + 1)) or not books:
        raise ValueError("books must be exactly 1..N in document order")
    return {"source": {"corpus": "phi", "author": author, "work": work,
                       "sourcedesc": source, "xml_sha256": hashlib.sha256(raw).hexdigest()},
            "books": books}


def export(author: str, work: str, phi_dir: Path) -> Path:
    output = EXPORT_DIR / "Diogenes-Resources" / "xml" / "phi" / f"phi{author}{work}.xml"
    if output.exists():
        return output
    config = REPO_ROOT / "build" / "diogenes-scratch"
    config.mkdir(parents=True, exist_ok=True)
    (config / "diogenes.prefs").write_text(f'phi_dir "{phi_dir}"\n', encoding="utf-8")
    server = Path("/Applications/Diogenes.app/Contents/server")
    command = ["perl", "-I", str(server), "-I", str(server.parent / "dependencies" / "CPAN"),
               str(server / "xml-export.pl"), "-c", "phi", "-n", author, "-y", "-o", str(EXPORT_DIR)]
    subprocess.run(command, cwd=server, env={"Diogenes_Config_Dir": str(config), "PATH": "/usr/bin:/bin"},
                   check=True)
    if not output.exists():
        raise FileNotFoundError(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phi-author", required=True)
    parser.add_argument("--phi-work", required=True)
    parser.add_argument("--expect-sourcedesc", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--xml", type=Path)
    parser.add_argument("--phi-dir", type=Path)
    args = parser.parse_args()
    phi_dir = args.phi_dir or os.environ.get("PHI_DIR")
    if not args.xml and not phi_dir:
        tlg_dir = os.environ.get("TLG_DIR")
        if not tlg_dir:
            parser.error("set --phi-dir, PHI_DIR, or TLG_DIR when --xml is absent")
        phi_dir = Path(tlg_dir) / ".." / "PHI"
    xml = args.xml or export(args.phi_author, args.phi_work, Path(phi_dir).resolve())
    result = extract(xml, args.phi_author, args.phi_work, args.expect_sourcedesc)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PHI: {sum(len(book['rows']) for book in result['books'])} lines in {len(result['books'])} books")


if __name__ == "__main__":
    main()
