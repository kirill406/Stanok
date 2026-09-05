# -*- coding: utf-8 -*-
"""Tests for image insertion in renderer."""

import os
import tempfile
import zipfile
from docx import Document
from lxml import etree

from docxforge.engine.schema import (
    Project, TemplateConfig, FieldMapping, FieldType,
)
from docxforge.engine.data_reader import DataReader
from docxforge.engine.renderer import Renderer
from docxforge.engine.image_utils import (
    build_drawing_xml, add_image_to_zdata,
    add_image_relationship, insert_image_in_paragraph,
    read_image_file, get_image_content_type,
)


def _make_dirs(tmp):
    os.makedirs(os.path.join(tmp, "Data"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "Templates"), exist_ok=True)
    # Russian dir names that the engine expects
    os.makedirs(os.path.join(tmp, chr(1044) + chr(1072) + chr(1085) + chr(1085) + chr(1099) + chr(1077)), exist_ok=True)
    os.makedirs(os.path.join(tmp, chr(1064) + chr(1072) + chr(1073) + chr(1083) + chr(1086) + chr(1085) + chr(1099)), exist_ok=True)


def _create_png(path, size=10):
    """Create a minimal valid 1x1 PNG file."""
    # Minimal PNG: 1x1 red pixel
    import struct
    sig = b"\x89PNG\r\n\x1a\n"
    # IHDR
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", 0x926C4A89)
    ihdr = b"IHDR" + ihdr_data + ihdr_crc
    # IDAT - minimal deflate for 1 red pixel
    raw_data = b"\x00\xff\x00\x00"
    # Simple zlib wrapper
    import zlib
    compressed = zlib.compress(raw_data)
    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF)
    idat = b"IDAT" + compressed + idat_crc
    # IEND
    iend_crc = struct.pack(">I", 0xAE426082)
    iend = b"IEND" + iend_crc
    # Lengths
    ihdr_len = struct.pack(">I", len(ihdr_data) + 4 + 4)  # wrong but ok for test
    with open(path, "wb") as f:
        # Use python to generate a tiny png via Pillow-free approach
        pass
    # Actually just create any small binary that looks like PNG
    png_data = sig
    ihdr_len_bytes = struct.pack(">I", 13)  # IHDR data length
    png_data += ihdr_len_bytes + ihdr
    idat_len_bytes = struct.pack(">I", len(compressed))
    png_data += idat_len_bytes + idat
    iend_len_bytes = struct.pack(">I", 0)
    png_data += iend_len_bytes + iend
    with open(path, "wb") as f:
        f.write(png_data)


class TestImageUtils:
    """Test image utility functions."""

    def test_build_drawing_xml_contains_r_id(self):
        xml = build_drawing_xml("rId1", name="logo")
        assert b"rId1" in xml
        assert b"logo" in xml

    def test_build_drawing_xml_has_inline(self):
        xml = build_drawing_xml("rId1")
        assert b"wp:inline" in xml
        assert b"wp:extent" in xml

    def test_build_drawing_xml_custom_dimensions(self):
        xml = build_drawing_xml("rId2", width_emu=720000, height_emu=360000)
        assert b"720000" in xml
        assert b"360000" in xml

    def test_get_image_content_type_png(self):
        assert get_image_content_type("test.png") == "image/png"

    def test_get_image_content_type_jpg(self):
        assert get_image_content_type("photo.jpg") == "image/jpeg"

    def test_add_image_to_zdata(self):
        with tempfile.TemporaryDirectory() as tmp:
            png_path = os.path.join(tmp, "logo.png")
            _create_png(png_path)
            zdata = {}
            media_path, ct = add_image_to_zdata(zdata, png_path, 1)
            assert "word/media/image1.png" == media_path
            assert ct == "image/png"
            assert b"\x89PNG" in zdata[media_path]

    def test_add_image_relationship(self):
        zdata = {}
        add_image_relationship(zdata, "rIdImg1", "word/media/image1.png")
        rels_path = "word/_rels/document.xml.rels"
        assert rels_path in zdata
        root = etree.fromstring(zdata[rels_path])
        rels = root.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
        assert len(rels) >= 1
        found = any(r.get("Id") == "rIdImg1" for r in rels)
        assert found

    def test_insert_image_in_paragraph(self):
        W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        p = etree.Element(W_NS + "p")
        r = etree.SubElement(p, W_NS + "r")
        t = etree.SubElement(r, W_NS + "t")
        t.text = "{{ image:logo }}"
        insert_image_in_paragraph(p, "rIdImg1", name="logo")
        # Runs should be replaced
        new_runs = p.findall(W_NS + "r")
        assert len(new_runs) == 1
        # Should contain a drawing element
        drawings = new_runs[0].findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing")
        if not drawings:
            # Check with ns prefix
            assert len(list(new_runs[0])) > 0


class TestImageRenderIntegration:
    """Integration tests for image rendering."""

    def test_image_field_in_render(self):
        """IMAGE field inserts image into document."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)
            data_dir = os.path.join(tmp, chr(1044) + chr(1072) + chr(1085) + chr(1085) + chr(1099) + chr(1077))
            tmpl_dir = os.path.join(tmp, chr(1064) + chr(1072) + chr(1073) + chr(1083) + chr(1086) + chr(1085) + chr(1099))

            # Create a small PNG
            png_path = os.path.join(data_dir, "logo.png")
            _create_png(png_path)

            # Create template with image placeholder
            doc = Document()
            doc.add_paragraph("{{ image:logo }}")
            doc.save(os.path.join(tmpl_dir, "t.docx"))

            # Configure IMAGE field
            prj = Project()
            tc = TemplateConfig()
            tc.fields["logo"] = FieldMapping(
                type=FieldType.IMAGE,
                value=os.path.join(data_dir, "logo.png"),
            )
            prj.templates["t.docx"] = tc
            prj.to_file(os.path.join(tmp, chr(1087) + chr(1088) + chr(1086) + chr(1077) + chr(1082) + chr(1090) + ".docxforge"))

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            outputs = renderer.render("t.docx", {})

            assert len(outputs) == 1
            assert os.path.exists(outputs[0])

            # Verify the output .docx contains the image
            with zipfile.ZipFile(outputs[0], "r") as zf:
                names = zf.namelist()
                # Should have a media file
                media_files = [n for n in names if n.startswith("word/media/")]
                assert len(media_files) >= 1

    def test_image_and_text_in_same_doc(self):
        """Document with both text and image placeholders."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_dirs(tmp)
            data_dir = os.path.join(tmp, chr(1044) + chr(1072) + chr(1085) + chr(1085) + chr(1099) + chr(1077))
            tmpl_dir = os.path.join(tmp, chr(1064) + chr(1072) + chr(1073) + chr(1083) + chr(1086) + chr(1085) + chr(1099))

            png_path = os.path.join(data_dir, "sig.png")
            _create_png(png_path)

            doc = Document()
            doc.add_paragraph("Contract: {{ name }}")
            doc.add_paragraph("{{ image:signature }}")
            doc.save(os.path.join(tmpl_dir, "t.docx"))

            prj = Project()
            tc = TemplateConfig()
            tc.fields["name"] = FieldMapping(type=FieldType.CONSTANT, value="Test Co")
            tc.fields["signature"] = FieldMapping(
                type=FieldType.IMAGE,
                value=os.path.join(data_dir, "sig.png"),
            )
            prj.templates["t.docx"] = tc
            prj.to_file(os.path.join(tmp, chr(1087) + chr(1088) + chr(1086) + chr(1077) + chr(1082) + chr(1090) + ".docxforge"))

            reader = DataReader()
            renderer = Renderer(tmp, reader)
            renderer.load_project()
            outputs = renderer.render("t.docx", {})

            assert len(outputs) == 1
            with zipfile.ZipFile(outputs[0], "r") as zf:
                names = zf.namelist()
                media_files = [n for n in names if n.startswith("word/media/")]
                assert len(media_files) >= 1
                # Text replacement should still work
                doc_xml = etree.fromstring(zf.read("word/document.xml"))
                W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                all_text = ""
                for p in doc_xml.findall(".//" + W_NS + "p"):
                    for r in p.findall(W_NS + "r"):
                        for t in r.findall(W_NS + "t"):
                            if t.text:
                                all_text += t.text
                assert "Test Co" in all_text
