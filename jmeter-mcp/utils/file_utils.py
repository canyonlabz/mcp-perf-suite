"""
file_utils.py

This module contains utility functions for file operations.
End-users and developers can extend or modify these functions independently
of the core JMeter component utilities.
"""
import xml.etree.ElementTree as ET
import datetime
import os
import urllib.parse
from xml.dom import minidom

from utils.config import load_config

# === Global configuration ===
CONFIG = load_config()
ARTIFACTS_PATH = CONFIG["artifacts"]["artifacts_path"]

def get_jmeter_artifacts_dir(run_id: str) -> str:
    """
    Returns the absolute directory path where JMeter artifacts
    (JMX, JTL, logs, etc.) should be stored for a given run_id.

    Final layout:
      artifacts/<run_id>/jmeter/
    """
    output_dir = os.path.join(ARTIFACTS_PATH, str(run_id), "jmeter")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

def save_jmx_file(root_element: ET.Element, run_id: str) -> str:
    """
    Saves the given XML tree (root_element) as a pretty-printed JMX file
    for the given run_id.

    The file will be stored under:
      artifacts/<run_id>/jmeter/

    The filename will include a timestamp for uniqueness:
      ai-generated_script_<timestamp>.jmx

    Returns the full output file path.
    """
    output_dir = get_jmeter_artifacts_dir(run_id)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"ai-generated_script_{timestamp}.jmx")

    xml_string = ET.tostring(root_element, encoding="utf-8")
    pretty_xml = minidom.parseString(xml_string).toprettyxml(indent="  ")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(pretty_xml)

    return output_file
