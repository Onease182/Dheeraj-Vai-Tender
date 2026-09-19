from pathlib import Path

import pytest
from docx import Document

from app.services.doc_generator import BidDocumentGenerator


def _generator(tmp_path):
    templates_dir = tmp_path / "templates"
    output_dir = tmp_path / "output"
    templates_dir.mkdir()
    return BidDocumentGenerator(templates_dir=templates_dir, output_dir=output_dir)


def test_output_dir_created(tmp_path):
    generator = _generator(tmp_path)
    assert generator.output_dir.is_dir()


def test_partner_count_rejects_missing_middle_partner(tmp_path):
    generator = _generator(tmp_path)
    with pytest.raises(ValueError, match="first partner"):
        generator.determine_partner_count(
            {
                "LEAD_PARTNER_NAME": "Lead Co",
                "FIRST_PARTNER_NAME": "",
                "SECOND_PARTNER_NAME": "Second Co",
            }
        )


def test_partner_count_supports_one_two_and_three_partners(tmp_path):
    generator = _generator(tmp_path)
    assert generator.determine_partner_count({"LEAD_PARTNER_NAME": "Lead"}) == 1
    assert generator.determine_partner_count({"LEAD_PARTNER_NAME": "Lead", "FIRST_PARTNER_NAME": "First"}) == 2
    assert (
        generator.determine_partner_count(
            {"LEAD_PARTNER_NAME": "Lead", "FIRST_PARTNER_NAME": "First", "SECOND_PARTNER_NAME": "Second"}
        )
        == 3
    )


def test_unresolved_placeholder_detection(tmp_path):
    generator = _generator(tmp_path)
    document = Document()
    document.add_paragraph("Hello {{KNOWN}} and {{MISSING}}")
    generator.replace_in_document(document, {"{{KNOWN}}": "World"})
    assert generator.unresolved_placeholders(document) == ["{{MISSING}}"]


def test_select_template_by_partner_count(tmp_path):
    generator = _generator(tmp_path)
    (generator.templates_dir / "master_template_1.docx").touch()
    (generator.templates_dir / "master_template_2.docx").touch()
    (generator.templates_dir / "master_template_3.docx").touch()
    assert generator.select_template(1) == "master_template_1.docx"
    assert generator.select_template(2) == "master_template_2.docx"
    assert generator.select_template(3) == "master_template_3.docx"


def test_select_template_falls_back_when_template_1_missing(tmp_path):
    generator = _generator(tmp_path)
    (generator.templates_dir / "master_template_2.docx").touch()
    assert generator.select_template(1) == "master_template_2.docx"
