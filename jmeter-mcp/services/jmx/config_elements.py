"""
services/jmx/config_elements.py

This module contains functions to create JMeter config elements.
For example, it includes functions to generate "User Defined Variables", "CSV Data Set Config" elements, etc.
End-users and developers can extend or modify these functions independently
of the core JMeter component utilities.
"""
import xml.etree.ElementTree as ET
import datetime
import os
import urllib.parse
from xml.dom import minidom

# === User Defined Variables Element ===
def create_user_defined_variables(udv_config):
    """
    Creates a User Defined Variables element based on configuration.
    udv_config should be a dictionary with keys:
      - enabled: bool
      - variables: dict (e.g., {"auth_token": "your_token", "user": "test"})
    Returns the Arguments element (or None if not enabled).
    """
    if not udv_config.get("enabled", False):
        return None
    udv = ET.Element("Arguments", attrib={
        "guiclass": "ArgumentsPanel",
        "testclass": "Arguments",
        "testname": "User Defined Variables",
        "enabled": "true"
    })
    collection = ET.SubElement(udv, "collectionProp", attrib={"name": "Arguments.arguments"})
    variables = udv_config.get("variables", {})
    for var, value in variables.items():
        var_elem = ET.SubElement(collection, "elementProp", attrib={
            "name": var,
            "elementType": "Argument"
        })
        ET.SubElement(var_elem, "stringProp", attrib={"name": "Argument.name"}).text = var
        ET.SubElement(var_elem, "stringProp", attrib={"name": "Argument.value"}).text = str(value)
        ET.SubElement(var_elem, "stringProp", attrib={"name": "Argument.metadata"}).text = "="
    return udv

# === CSV Data Set Config Element ===
def create_csv_data_set_config(csv_config):
    """
    Creates a CSV Data Set Config element based on configuration.
    csv_config should be a dictionary with keys:
      - enabled: bool
      - filename: path to CSV file (string)
      - ignore_first_line: bool
      - variable_names: comma separated string (e.g., "username,password")
      - delimiter: string (e.g., ",")
      - recycle_on_end: bool
      - stop_thread_on_error: bool
      - sharing_mode: string (e.g., "shareMode.all")
    Returns the CSVDataSet element (or None if not enabled).
    """
    if not csv_config.get("enabled", False):
        return None
    csv_data = ET.Element("CSVDataSet", attrib={
        "guiclass": "TestBeanGUI",
        "testclass": "CSVDataSet",
        "testname": "CSV Data Set Config",
        "enabled": "true"
    })
    ET.SubElement(csv_data, "stringProp", attrib={"name": "delimiter"}).text = csv_config.get("delimiter", ",")
    ET.SubElement(csv_data, "stringProp", attrib={"name": "fileEncoding"}).text = ""
    ET.SubElement(csv_data, "stringProp", attrib={"name": "filename"}).text = csv_config.get("filename", "test_data.csv")
    ET.SubElement(csv_data, "boolProp", attrib={"name": "ignoreFirstLine"}).text = str(csv_config.get("ignore_first_line", True)).lower()
    ET.SubElement(csv_data, "boolProp", attrib={"name": "quotedData"}).text = "false"
    ET.SubElement(csv_data, "boolProp", attrib={"name": "recycle"}).text = str(csv_config.get("recycle_on_end", True)).lower()
    ET.SubElement(csv_data, "stringProp", attrib={"name": "shareMode"}).text = csv_config.get("sharing_mode", "shareMode.all")
    ET.SubElement(csv_data, "boolProp", attrib={"name": "stopThread"}).text = str(csv_config.get("stop_thread_on_error", False)).lower()
    ET.SubElement(csv_data, "stringProp", attrib={"name": "variableNames"}).text = csv_config.get("variable_names", "")
    return csv_data

# === HTTP Header Manager Element ===
def create_header_manager(headers):
    """
    Creates a Header Manager element with the provided headers.
    Returns the HeaderManager XML element.
    """
    header_manager = ET.Element("HeaderManager", attrib={
        "guiclass": "HeaderPanel",
        "testclass": "HeaderManager",
        "testname": "HTTP Header Manager"
    })
    collection = ET.SubElement(header_manager, "collectionProp", attrib={"name": "HeaderManager.headers"})
    
    for name, value in headers.items():
        header_element = ET.SubElement(collection, "elementProp", attrib={
            "name": "",
            "elementType": "Header"
        })
        ET.SubElement(header_element, "stringProp", attrib={"name": "Header.name"}).text = name
        ET.SubElement(header_element, "stringProp", attrib={"name": "Header.value"}).text = value
    
    return header_manager

# === HTTP Cookie Manager Element ===
def create_cookie_manager():
    """
    Creates a default Cookie Manager element.
    """
    cookie_manager = ET.Element("CookieManager", attrib={
       "guiclass": "CookiePanel",
       "testclass": "CookieManager",
       "testname": "HTTP Cookie Manager",
       "enabled": "true"
    })
    ET.SubElement(cookie_manager, "collectionProp", attrib={"name": "CookieManager.cookies"})
    ET.SubElement(cookie_manager, "boolProp", attrib={"name": "CookieManager.clearEachIteration"}).text = "true"
    ET.SubElement(cookie_manager, "boolProp", attrib={"name": "CookieManager.controlledByThreadGroup"}).text = "false"
    
    return cookie_manager
