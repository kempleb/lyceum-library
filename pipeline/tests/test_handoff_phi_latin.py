from pathlib import Path

import pytest

from reader_pipeline.handoff_phi_latin import extract


def test_document_order_titles_and_inline_text(tmp_path: Path):
    xml = tmp_path / "test.xml"
    xml.write_text('''<TEI><teiHeader><sourceDesc> Test   edition </sourceDesc></teiHeader><text><body>
      <div type="book" n="t"><l n="t">Title</l></div>
      <div type="book" n="1"><l n="t">Heading</l><l n="3">Third<pb/> line</l>
      <l n="2">Second <space quantity="7"/> <hi rend="small-caps">word</hi></l></div>
      </body></text></TEI>''')
    result = extract(xml, "0690", "003", "Test edition")
    assert result["books"] == [{"book": 1, "rows": [
        {"n": "3", "text": "Third line"}, {"n": "2", "text": "Second word"}]}]
    assert len(result["source"]["xml_sha256"]) == 64
    with pytest.raises(ValueError, match="sourceDesc mismatch"):
        extract(xml, "0690", "003", "Wrong edition")


def test_duplicate_line_fails(tmp_path: Path):
    xml = tmp_path / "test.xml"
    xml.write_text('<TEI><sourceDesc>Edition</sourceDesc><div type="book" n="1"><l n="1">a</l><l n="1">b</l></div></TEI>')
    with pytest.raises(ValueError, match="duplicate"):
        extract(xml, "0690", "003", "Edition")
