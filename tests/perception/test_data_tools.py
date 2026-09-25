import tempfile
from pathlib import Path
import pytest

from perception.data_tools.voc_to_yolo import voc_bbox_to_yolo_xywh, convert_voc_to_yolo
from perception.data_tools.label_merger import merge_person_pseudo_labels


def test_voc_bbox_to_yolo_xywh():
    size = (1000, 500)
    # Box: x1=100, y1=100, x2=300, y2=400
    # width=200, height=300, cx=200, cy=250
    # normalized: cx=0.2, cy=0.5, w=0.2, h=0.6
    box = [100.0, 100.0, 300.0, 400.0]
    yolo_box = voc_bbox_to_yolo_xywh(size, box)

    assert pytest.approx(yolo_box[0], 1e-4) == 0.2
    assert pytest.approx(yolo_box[1], 1e-4) == 0.5
    assert pytest.approx(yolo_box[2], 1e-4) == 0.2
    assert pytest.approx(yolo_box[3], 1e-4) == 0.6


def test_voc_xml_conversion_and_merge():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        xml_dir = tmp_path / "xmls"
        txt_dir = tmp_path / "labels"
        pseudo_dir = tmp_path / "pseudo"
        xml_dir.mkdir()
        txt_dir.mkdir()
        pseudo_dir.mkdir()

        # Create dummy VOC XML
        sample_xml = xml_dir / "0001.xml"
        sample_xml.write_text(
            """<annotation>
    <size>
        <width>640</width>
        <height>480</height>
    </size>
    <object>
        <name>hat</name>
        <bndbox>
            <xmin>100</xmin>
            <ymin>50</ymin>
            <xmax>150</xmax>
            <ymax>100</ymax>
        </bndbox>
    </object>
</annotation>""",
            encoding="utf-8",
        )

        # 1. Convert VOC to YOLO
        count = convert_voc_to_yolo(xml_dir, txt_dir)
        assert count == 1
        label_file = txt_dir / "0001.txt"
        assert label_file.is_file()
        content = label_file.read_text(encoding="utf-8")
        assert content.startswith("2 ")  # Class 2 is helmet/hat

        # 2. Simulate pseudo label for person (Class 0)
        pseudo_file = pseudo_dir / "0001.txt"
        pseudo_file.write_text("0 0.500000 0.500000 0.300000 0.800000\n", encoding="utf-8")

        # 3. Merge pseudo label
        merged = merge_person_pseudo_labels(pseudo_dir, txt_dir)
        assert merged == 1

        final_content = label_file.read_text(encoding="utf-8")
        lines = [line.strip() for line in final_content.splitlines() if line.strip()]
        assert len(lines) == 2
        assert lines[0].startswith("2 ")
        assert lines[1].startswith("0 ")
