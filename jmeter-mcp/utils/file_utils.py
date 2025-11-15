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

# === Save JMX File ===
def save_jmx_file(root_element, output_dir="jmx-files"):
    """
    Saves the given XML tree (root_element) as a pretty-printed JMX file.
    The filename will include a timestamp for uniqueness.
    Returns the output file path.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"ai-generated_script_{timestamp}.jmx")
    xml_string = ET.tostring(root_element, encoding="utf-8")
    pretty_xml = minidom.parseString(xml_string).toprettyxml(indent="  ")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(pretty_xml)
    print(f"JMX file generated successfully: {output_file}")
    return output_file
