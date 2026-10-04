"""BidDocumentGenerator — ported from the desktop app's doc_generator.py.

Placeholder replacement, image replacement, table cleanup, and document
generation. Pure document logic, no UI framework dependency — this is why
the port was near-verbatim; only convert_to_pdf was trimmed to the
LibreOffice-only path since the backend container runs Linux (no MS Word /
docx2pdf available there). PDF conversion lives in pdf_service.py (Phase 5).
"""

import logging
import os
import re
import subprocess
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches
from lxml import etree

logger = logging.getLogger(__name__)


class BidDocumentGenerator:
    # Every signature/stamp image slot the master templates may contain (matched by the image's alt text).
    IMAGE_SLOT_KEYS = ("AUTHORISED_SIG",) + tuple(
        f"{prefix}_{suffix}"
        for prefix in ("LEAD", "FIRST", "SECOND")
        for suffix in ("CEO_SIG", "STAMP", "PARTNER_MD1", "PARTNER_MD2", "MD1_SIG", "MD2_SIG")
    )

    def __init__(self, templates_dir: Path, output_dir: Path):
        self.templates_dir = Path(templates_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def is_empty_value(self, value):
        if value is None:
            return True
        return str(value).strip() == ""

    def replace_all_in_paragraph(self, paragraph, placeholders):
        for run in paragraph.runs:
            for key, value in placeholders.items():
                if key in run.text:
                    val = "" if self.is_empty_value(value) else str(value)
                    run.text = run.text.replace(key, val)

        full_text = paragraph.text
        remaining_keys = {k: v for k, v in placeholders.items() if k in full_text}
        if not remaining_keys:
            return

        new_text = full_text
        for key, value in remaining_keys.items():
            val = "" if self.is_empty_value(value) else str(value)
            new_text = new_text.replace(key, val)

        if paragraph.runs:
            first_run = paragraph.runs[0]
            paragraph.clear()
            new_run = paragraph.add_run(new_text)
            new_run.bold = first_run.bold
            new_run.italic = first_run.italic
            if first_run.font.name:
                new_run.font.name = first_run.font.name
            if first_run.font.size:
                new_run.font.size = first_run.font.size

    def _clear_table_cell(self, cell):
        for p in cell.paragraphs:
            for run in p.runs:
                run.text = ""
        for child in list(cell._element):
            tag = etree.QName(child).localname if hasattr(child, "tag") else ""
            if tag not in ("p", "tbl", "tcPr"):
                child.getparent().remove(child)

    def clean_empty_partner_sections(self, doc, bid_data):
        shared_fields = []
        signatory_fields = []
        for prefix in ("LEAD", "FIRST", "SECOND"):
            shared_fields += [f"{prefix}_PARTNER_NAME", f"{prefix}_PARTNER_SHORT", f"{prefix}_ADDRESS"]
            signatory_fields += [f"{prefix}_PARTNER_CEO", f"{prefix}_PARTNER_MD1", f"{prefix}_PARTNER_MD2"]

        empty_shared = [f for f in shared_fields if self.is_empty_value(bid_data.get(f))]
        empty_signatory = {f for f in signatory_fields if self.is_empty_value(bid_data.get(f))}

        if not empty_shared and not empty_signatory:
            return

        shared_placeholders = []
        for field in empty_shared:
            shared_placeholders.extend([f"{{{{{field}}}}}", field])

        all_empty_placeholders = list(shared_placeholders)
        for field in empty_signatory:
            all_empty_placeholders.extend([f"{{{{{field}}}}}", field])

        paragraphs_to_remove = []
        for paragraph in doc.paragraphs:
            for ph in all_empty_placeholders:
                if ph in paragraph.text:
                    paragraphs_to_remove.append(paragraph)
                    break
        for p in paragraphs_to_remove:
            p._element.getparent().remove(p._element)

        for table in doc.tables:
            column_field = {}
            for row in table.rows:
                if len(row.cells) == 1:
                    continue
                for col_idx, cell in enumerate(row.cells):
                    for field in signatory_fields:
                        if f"{{{{{field}}}}}" in cell.text:
                            column_field[col_idx] = field
                            break

            columns_to_clear = {col_idx for col_idx, field in column_field.items() if field in empty_signatory}

            for row in list(table.rows):
                if len(row.cells) == 1:
                    cell_text = row.cells[0].text
                    for ph in all_empty_placeholders:
                        if ph in cell_text:
                            table._element.remove(row._element)
                            break
                    continue

                for col_idx, cell in enumerate(row.cells):
                    if col_idx in columns_to_clear:
                        self._clear_table_cell(cell)
                    elif shared_placeholders:
                        for ph in shared_placeholders:
                            if ph in cell.text:
                                self._clear_table_cell(cell)
                                break

    def _has_page_break(self, paragraph) -> bool:
        """True if the paragraph contains only a page/section break and no visible text."""
        if paragraph.text.strip():
            return False
        xml = paragraph._element.xml if hasattr(paragraph._element, "xml") else ""
        return "w:pageBreak" in xml or "w:sectPr" in xml

    def remove_partner_blocks(self, doc, partner_prefix):
        paragraphs_to_remove = []
        for paragraph in doc.paragraphs:
            text = paragraph.text
            if f"{{{{{partner_prefix}_" in text or f"{partner_prefix}_" in text:
                paragraphs_to_remove.append(paragraph)
        for p in paragraphs_to_remove:
            try:
                p._element.getparent().remove(p._element)
            except Exception:
                pass

        # Remove page-break-only paragraphs that are now stranded (empty body after removal).
        body_paragraphs = doc.paragraphs
        for i, p in enumerate(body_paragraphs):
            if not self._has_page_break(p):
                continue
            # Stranded if the next non-empty paragraph is another page break or there is none.
            rest = [q for q in body_paragraphs[i + 1:] if q.text.strip() or self._has_page_break(q)]
            if not rest or self._has_page_break(rest[0]):
                try:
                    p._element.getparent().remove(p._element)
                except Exception:
                    pass

        for table in doc.tables:
            rows_to_remove = []
            for row in table.rows:
                for cell in row.cells:
                    cell_text = cell.text
                    if f"{{{{{partner_prefix}_" in cell_text or f"{partner_prefix}_" in cell_text:
                        rows_to_remove.append(row)
                        break
            for row in rows_to_remove:
                try:
                    table._element.remove(row._element)
                except Exception:
                    pass

    def _replace_in_header_footer(self, hdr_ftr, placeholders):
        for p in hdr_ftr.paragraphs:
            self.replace_all_in_paragraph(p, placeholders)
        for table in hdr_ftr.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        self.replace_all_in_paragraph(p, placeholders)

    def replace_in_document(self, doc, placeholders):
        for p in doc.paragraphs:
            self.replace_all_in_paragraph(p, placeholders)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        self.replace_all_in_paragraph(p, placeholders)
        for section in doc.sections:
            self._replace_in_header_footer(section.header, placeholders)
            self._replace_in_header_footer(section.footer, placeholders)

    def _all_paragraphs(self, doc):
        yield from doc.paragraphs
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    yield from cell.paragraphs
        for section in doc.sections:
            for hf in (section.header, section.footer):
                yield from hf.paragraphs
                for table in hf.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            yield from cell.paragraphs

    def unresolved_placeholders(self, doc):
        found = set()
        for paragraph in self._all_paragraphs(doc):
            found.update(re.findall(r"\{\{[^{}]+\}\}", paragraph.text))
        return sorted(found)

    _EMBED_ATTR = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"

    def replace_images_batch(self, doc, image_mapping, remove_keys=None):
        replacements = 0
        remove_keys = set(remove_keys or ())

        def process_paragraph(paragraph):
            nonlocal replacements
            part = paragraph.part
            for run in paragraph.runs:
                for drawing in run._element.findall(
                    ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing"
                ):
                    for blip in drawing.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip"):
                        embed = blip.get(self._EMBED_ATTR)
                        if not embed:
                            continue
                        docPr = drawing.find(
                            ".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr"
                        )
                        if docPr is None:
                            continue
                        alt_text = docPr.get("descr") or docPr.get("title") or ""
                        candidate_keys = set(image_mapping).union(remove_keys)
                        matches = [key for key in candidate_keys if key.upper() in alt_text.upper()]
                        if not matches:
                            continue
                        key = max(matches, key=len)
                        if key in remove_keys:
                            drawing_parent = drawing.getparent()
                            if drawing_parent is not None:
                                drawing_parent.remove(drawing)
                                replacements += 1
                            break
                        img_path = image_mapping.get(key)
                        if img_path and os.path.exists(img_path):
                            try:
                                new_rId, _image = part.get_or_add_image(img_path)
                                blip.set(self._EMBED_ATTR, new_rId)
                                replacements += 1
                            except Exception as e:
                                logger.error(f"Failed to replace image {key}: {e}")
                        break

        for p in doc.paragraphs:
            process_paragraph(p)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        process_paragraph(p)
        for section in doc.sections:
            for p in section.header.paragraphs:
                process_paragraph(p)
            for p in section.footer.paragraphs:
                process_paragraph(p)
        return replacements

    def _remove_empty_tables(self, doc):
        """Remove tables whose every cell is empty (image removed, no text left)."""
        for table in list(doc.tables):
            all_empty = all(
                cell.text.strip() == ""
                for row in table.rows
                for cell in row.cells
            )
            if all_empty:
                try:
                    tbl_parent = table._element.getparent()
                    if tbl_parent is not None:
                        tbl_parent.remove(table._element)
                except Exception:
                    pass

    def _compress_empty_paragraphs(self, doc, max_consecutive: int = 2):
        """Remove runs of more than `max_consecutive` blank paragraphs in the body."""
        consecutive = 0
        to_remove = []
        for p in doc.paragraphs:
            xml = etree.tostring(p._element).decode()
            is_sect = "w:sectPr" in xml
            if is_sect:
                consecutive = 0
                continue
            if p.text.strip():
                consecutive = 0
            else:
                consecutive += 1
                if consecutive > max_consecutive:
                    to_remove.append(p)
        for p in to_remove:
            try:
                p._element.getparent().remove(p._element)
            except Exception:
                pass

    def _fix_header_spacing(self, doc):
        """Ensure all sections have consistent header-from-top distance and top margin."""
        for section in doc.sections:
            if section.header_distance == 0 or section.header_distance is None:
                section.header_distance = Inches(0.5)   # 0.5 inch from paper edge to header
            if section.top_margin == 0 or section.top_margin is None:
                section.top_margin = Inches(1.0)

    # Styles that should keep their own alignment and spacing.
    _SKIP_JUSTIFY_STYLES = {"Heading 1", "Heading 2", "Heading 3", "Heading 4", "Title", "Subtitle"}

    def _normalize_paragraph_spacing(self, doc):
        """Enforce consistent single-spacing on all body paragraphs so sections
        don't overflow to an extra page due to inherited theme defaults."""
        from docx.shared import Pt
        from docx.enum.text import WD_LINE_SPACING
        for p in doc.paragraphs:
            style_name = p.style.name if p.style else ""
            if style_name in self._SKIP_JUSTIFY_STYLES:
                continue
            pf = p.paragraph_format
            # Only touch paragraphs where spacing is still inherited (None = theme default)
            if pf.space_after is None:
                pf.space_after = Pt(4)
            if pf.line_spacing is None:
                pf.line_spacing = 1.0
                pf.line_spacing_rule = WD_LINE_SPACING.SINGLE

    def _justify_body_paragraphs(self, doc):
        """Set justify alignment on all body paragraphs that contain visible text."""
        for p in doc.paragraphs:
            if not p.text.strip():
                continue
            style_name = p.style.name if p.style else ""
            if style_name in self._SKIP_JUSTIFY_STYLES:
                continue
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    def determine_partner_count(self, data):
        if data.get("BID_TYPE") == "Single Bidder":
            if self.is_empty_value(data.get("LEAD_PARTNER_NAME", "")):
                raise ValueError("Lead partner name is required for single bidder.")
            return 1
        lead_present = not self.is_empty_value(data.get("LEAD_PARTNER_NAME", ""))
        first_present = not self.is_empty_value(data.get("FIRST_PARTNER_NAME", ""))
        second_present = not self.is_empty_value(data.get("SECOND_PARTNER_NAME", ""))
        if not lead_present:
            raise ValueError("At least the lead partner must be filled to generate the bid.")
        if second_present and not first_present:
            raise ValueError("The first partner must be filled before the second partner.")
        return 3 if second_present else 2 if first_present else 1

    def select_template(self, partner_count):
        if partner_count == 1:
            template_name = "master_template_1.docx"
            if not (self.templates_dir / template_name).exists():
                template_name = "master_template_2.docx"
            return template_name
        elif partner_count == 2:
            return "master_template_2.docx"
        else:
            return "master_template_3.docx"

    def generate(self, data: dict, image_mapping: dict) -> Path:
        partner_count = self.determine_partner_count(data)
        template_name = self.select_template(partner_count)
        template_path = self.templates_dir / template_name

        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        doc = Document(template_path)

        if partner_count == 1:
            self.remove_partner_blocks(doc, "FIRST")
            self.remove_partner_blocks(doc, "SECOND")
        elif partner_count == 2:
            self.remove_partner_blocks(doc, "SECOND")

        self.clean_empty_partner_sections(doc, data)

        placeholders = {f"{{{{{k}}}}}": v for k, v in data.items()}
        self.replace_in_document(doc, placeholders)
        self._remove_empty_tables(doc)
        self._normalize_paragraph_spacing(doc)
        self._justify_body_paragraphs(doc)
        self._compress_empty_paragraphs(doc)
        self._fix_header_spacing(doc)

        image_mapping = {k: v for k, v in (image_mapping or {}).items() if v and os.path.exists(v)}
        # master_template_3 names MD signature slots "<P>_MD1_SIG" instead of the upload key "<P>_PARTNER_MD1".
        for prefix in ("LEAD", "FIRST", "SECOND"):
            for n in ("1", "2"):
                uploaded = image_mapping.get(f"{prefix}_PARTNER_MD{n}")
                if uploaded:
                    image_mapping.setdefault(f"{prefix}_MD{n}_SIG", uploaded)

        remove_image_keys = set()
        for prefix in ("LEAD", "FIRST", "SECOND"):
            for suffix in ("PARTNER_MD1", "PARTNER_MD2"):
                key = f"{prefix}_{suffix}"
                if self.is_empty_value(data.get(key)):
                    remove_image_keys.add(key)
        # Signatures/stamps are optional: a slot with no uploaded image is removed rather than
        # left showing the template's sample picture.
        remove_image_keys.update(key for key in self.IMAGE_SLOT_KEYS if key not in image_mapping)
        self.replace_images_batch(doc, image_mapping, remove_keys=remove_image_keys)

        unresolved = self.unresolved_placeholders(doc)
        if unresolved:
            raise ValueError("The selected template contains unresolved placeholders: " + ", ".join(unresolved))

        jv_name = data.get("JV_NAME", "bid")
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", jv_name)[:50].strip("_") or "bid"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"generated_bid_{safe_name}_{timestamp}.docx"
        output_path = self.output_dir / output_filename

        with tempfile.NamedTemporaryFile(prefix=".bid_", suffix=".docx", dir=self.output_dir, delete=False) as tmp:
            temp_path = Path(tmp.name)
        try:
            doc.save(str(temp_path))
            temp_path.replace(output_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

        return output_path

    def convert_to_pdf(self, docx_path: Path) -> Path:
        """LibreOffice-headless conversion (the backend container has no MS
        Word, so the desktop app's docx2pdf branch does not apply here)."""
        docx_path = Path(docx_path)
        pdf_path = docx_path.with_suffix(".pdf")

        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            raise RuntimeError("LibreOffice is not installed in this environment.")

        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(docx_path.parent), str(docx_path)],
            check=True,
            timeout=120,
        )
        if not pdf_path.exists():
            raise RuntimeError("PDF conversion did not produce an output file.")
        return pdf_path
