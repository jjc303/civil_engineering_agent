from __future__ import annotations

from pathlib import Path
from typing import Union


def merge_person_pseudo_labels(
    pseudo_label_dir: Union[str, Path],
    dataset_label_dir: Union[str, Path],
    person_class_id: int = 0,
) -> int:
    """
    Merges pseudo-labeled 'person' bounding boxes inferred by large models
    into the target dataset's label files.
    :param pseudo_label_dir: directory containing inference output .txt files
    :param dataset_label_dir: target dataset label directory to append person boxes
    :param person_class_id: class ID for person in pseudo labels (default 0)
    :return: number of files merged
    """
    pseudo_path = Path(pseudo_label_dir)
    target_path = Path(dataset_label_dir)

    if not pseudo_path.is_dir() or not target_path.is_dir():
        return 0

    merged_files = 0
    for txt_file in pseudo_path.glob("*.txt"):
        lines_to_add = []
        with open(txt_file, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if not parts:
                    continue
                # Filter for person class
                if int(parts[0]) == person_class_id:
                    lines_to_add.append(line.strip())

        if not lines_to_add:
            continue

        target_file = target_path / txt_file.name
        if target_file.is_file():
            with open(target_file, "a", encoding="utf-8") as tf:
                for line in lines_to_add:
                    tf.write(f"\n{line}")
            merged_files += 1

    return merged_files
