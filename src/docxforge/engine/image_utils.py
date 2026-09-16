# -*- coding: utf-8 -*-
"""Image insertion utilities for .docx templates.

Reads image files, creates drawing XML (wp:inline),
and updates .docx relationships for embedded images.
"""

import os
import mimetypes
from typing import Tuple

from lxml import etree


# Default image dimensions in EMU (1 cm = 360000 EMU)
DEFAULT_WIDTH_EMU = 360000 * 3   # 3 cm
DEFAULT_HEIGHT_EMU = 360000 * 2  # 2 cm


def get_image_content_type(path: str) -> str:
    """Return MIME type for image file."""
    ct, _ = mimetypes.guess_type(path)
    return ct or "image/png"


def read_image_file(path: str) -> Tuple[bytes, str]:
    """Read an image file and return (data, content_type)."""
    with open(path, "rb") as f_img:
        data = f_img.read()
    ct = get_image_content_type(path)
    return data, ct


def build_drawing_xml(r_id: str,
                      width_emu: int = DEFAULT_WIDTH_EMU,
                      height_emu: int = DEFAULT_HEIGHT_EMU,
                      name: str = "Image") -> bytes:
    """Build a complete w:drawing element as XML bytes.

    Creates an inline image (wp:inline) with proper namespaces.
    """
    xml_str = (
        '<w:drawing xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<wp:inline distT="0" distB="0" distL="0" distR="0">'
        '<wp:extent cx="{width}" cy="{height}"/>'
        '<wp:docPr id="0" name="{name}"/>'
        '<a:graphic>'
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:nvPicPr>'
        '<pic:cNvPr id="0" name="{name}"/>'
        '<pic:cNvPicPr/>'
        '</pic:nvPicPr>'
        '<pic:blipFill>'
        '<a:blip r:embed="{r_id}"/>'
        '<a:stretch><a:fillRect/></a:stretch>'
        '</pic:blipFill>'
        '<pic:spPr>'
        '<a:xfrm><a:off x="0" y="0"/>'
        '<a:ext cx="{width}" cy="{height}"/>'
        '</a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        '</pic:spPr>'
        '</a:graphicData>'
        '</a:graphic>'
        '</wp:inline>'
        '</w:drawing>'
    ).format(r_id=r_id, width=width_emu, height=height_emu, name=name)
    return xml_str.encode("utf-8")


def add_image_to_zdata(zdata: dict, image_path: str,
                       image_index: int) -> Tuple[str, str]:
    """Add an image file to the zdata dict.

    Also registers the image content type in [Content_Types].xml
    (Override for the new part), unless a matching Default exists.

    Returns:
        (media_path, content_type) - the zip path and MIME type.
    """
    data, ct = read_image_file(image_path)
    ext = os.path.splitext(image_path)[1] or ".png"
    media_path = "word/media/image{:d}{}".format(image_index, ext)
    zdata[media_path] = data
    _ensure_image_content_type(zdata, media_path, ext, ct)
    return media_path, ct


def _ensure_image_content_type(zdata: dict, media_path: str,
                               ext: str, content_type: str) -> None:
    """Add an Override for the image part to [Content_Types].xml if needed."""
    ct_path = "[Content_Types].xml"
    if ct_path not in zdata:
        return
    CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
    root = etree.fromstring(zdata[ct_path])
    ext_no_dot = ext.lstrip(".").lower()
    for el in root:
        if el.tag == "{%s}Default" % CT_NS:
            if (el.get("Extension") or "").lower() == ext_no_dot:
                return
        elif el.tag == "{%s}Override" % CT_NS:
            if el.get("PartName") == "/" + media_path:
                return
    override = etree.SubElement(root, "{%s}Override" % CT_NS)
    override.set("PartName", "/" + media_path)
    override.set("ContentType", content_type)
    zdata[ct_path] = etree.tostring(root, xml_declaration=True,
                                    encoding="UTF-8", standalone=True)


def add_image_relationship(zdata: dict, r_id: str,
                           media_path: str) -> None:
    """Add or update a relationship entry for an image.

    Updates word/_rels/document.xml.rels in zdata.
    """
    rels_path = "word/_rels/document.xml.rels"
    RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

    if rels_path in zdata:
        root = etree.fromstring(zdata[rels_path])
    else:
        root = etree.Element("{%s}Relationships" % RELS_NS)
        root.set("xmlns", RELS_NS)

    rel = etree.SubElement(root, "{%s}Relationship" % RELS_NS)
    rel.set("Id", r_id)
    rel.set("Type",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image")
    rel.set("Target", media_path.replace("word/", ""))

    zdata[rels_path] = etree.tostring(root, xml_declaration=True,
                                      encoding="UTF-8", standalone=True)


def insert_image_in_paragraph(paragraph, r_id: str,
                               width_emu: int = DEFAULT_WIDTH_EMU,
                               height_emu: int = DEFAULT_HEIGHT_EMU,
                               name: str = "Image") -> None:
    """Replace a paragraph with an inline image drawing.

    Removes all existing runs and adds a single run
    containing a w:drawing element with the image.
    """
    W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    for run in paragraph.findall(W_NS + "r"):
        paragraph.remove(run)

    append_image_run(paragraph, r_id, width_emu, height_emu, name)


def append_image_run(paragraph, r_id: str,
                     width_emu: int = DEFAULT_WIDTH_EMU,
                     height_emu: int = DEFAULT_HEIGHT_EMU,
                     name: str = "Image"):
    """Append a run with an inline image drawing without touching other runs."""
    W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    new_run = etree.SubElement(paragraph, W_NS + "r")
    drawing_xml = build_drawing_xml(r_id, width_emu, height_emu, name)
    drawing_el = etree.fromstring(drawing_xml)
    new_run.append(drawing_el)
    return new_run
