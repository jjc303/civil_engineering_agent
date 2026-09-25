from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple, Union
from xml.dom.minidom import parse
import numpy as np


def voc_bbox_to_yolo_xywh(size: Tuple[int, int], box: List[float]) -> List[float]:
    """
    Converts VOC [xmin, ymin, xmax, ymax] absolute pixel coordinates
    to normalized YOLO format [x_center, y_center, width, height] in [0, 1].
    :param size: (image_width, image_height)
    :param box: [x1, y1, x2, y2]
    :return: [x_center, y_center, width, height] normalized
    """
    w_img, h_img = size[0], size[1]
    if w_img <= 0 or h_img <= 0:
        raise ValueError(f"Invalid image dimensions: {size}")

    x1, y1, x2, y2 = float(box[0]), float(box[1]), float(box[2]), float(box[3])

    dw = 1.0 / float(w_img)
    dh = 1.0 / float(h_img)

    w = x2 - x1
    h = y2 - y1
    x_center = x1 + (w / 2.0)
    y_center = y1 + (h / 2.0)

    return [
        float(x_center * dw),
        float(y_center * dh),
        float(w * dw),
        float(h * dh),
    ]


def parse_voc_xml(xml_path: Union[str, Path]) -> Tuple[Tuple[int, int], List[Tuple[str, List[float]]]]:
    """
    Parses a VOC XML annotation file.
    :return: ((width, height), list of (class_name, [x1, y1, x2, y2]))
    """
    dom = parse(str(xml_path))
    root = dom.documentElement

    size_nodes = root.getElementsByTagName("size")
    if not size_nodes:
        return (0, 0), []

    size_node = size_nodes[0]
    w = int(size_node.getElementsByTagName("width")[0].childNodes[0].data)
    h = int(size_node.getElementsByTagName("height")[0].childNodes[0].data)

    objects = root.getElementsByTagName("object")
    boxes = []
    for obj in objects:
        cls_name = obj.getElementsByTagName("name")[0].childNodes[0].data
        bndbox = obj.getElementsByTagName("bndbox")[0]
        x1 = float(bndbox.getElementsByTagName("xmin")[0].childNodes[0].data)
        y1 = float(bndbox.getElementsByTagName("ymin")[0].childNodes[0].data)
        x2 = float(bndbox.getElementsByTagName("xmax")[0].childNodes[0].data)
        y2 = float(bndbox.getElementsByTagName("ymax")[0].childNodes[0].data)
        boxes.append((cls_name, [x1, y1, x2, y2]))

    return (w, h), boxes


def convert_voc_to_yolo(
    xml_dir: Union[str, Path],
    output_label_dir: Union[str, Path],
    class_map: dict[str, int] | None = None,
) -> int:
    """
    Batch converts VOC XML annotations to YOLO format .txt label files.
    Default class mapping:
      'person' -> 1 (head in SHWD)
      'hat' -> 2 (helmet in SHWD)
    """
    if class_map is None:
        class_map = {
            "person": 1,  # In original SHWD dataset, 'person' tags head
            "head": 1,
            "hat": 2,     # 'hat' tags helmet
            "helmet": 2,
        }

    src_dir = Path(xml_dir)
    dst_dir = Path(output_label_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    xml_files = list(src_dir.glob("*.xml"))
    converted_count = 0

    for xml_file in xml_files:
        (w, h), boxes = parse_voc_xml(xml_file)
        if w <= 0 or h <= 0:
            continue

        txt_file = dst_dir / f"{xml_file.stem}.txt"
        with open(txt_file, "w", encoding="utf-8") as f:
            for cls_name, bbox in boxes:
                if cls_name not in class_map:
                    continue
                cls_id = class_map[cls_name]
                yolo_box = voc_bbox_to_yolo_xywh((w, h), bbox)
                f.write(f"{cls_id} {yolo_box[0]:.6f} {yolo_box[1]:.6f} {yolo_box[2]:.6f} {yolo_box[3]:.6f}\n")
        converted_count += 1

    return converted_count
