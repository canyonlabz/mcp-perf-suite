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
# Headers to exclude from HTTP Header Manager (handled by other JMeter components)
EXCLUDED_HEADERS = {
    "cookie",      # Handled by HTTP Cookie Manager
    "content-length",  # Automatically calculated by JMeter
}

# HTTP/2 pseudo-headers that may need to be excluded
# JMeter uses HTTP/1.1 by default; these headers cause errors on non-HTTP/2 backends
HTTP2_PSEUDO_HEADERS = {
    ":method",     # HTTP/2 method pseudo-header
    ":path",       # HTTP/2 path pseudo-header
    ":scheme",     # HTTP/2 scheme pseudo-header (http/https)
    ":authority",  # HTTP/2 authority pseudo-header (host:port)
    ":status",     # HTTP/2 status pseudo-header (response only)
}

# Headers that should have hostname parameterization applied
# These headers contain hostnames that should be replaced with JMeter variables
HOSTNAME_HEADERS = {
    "host",        # e.g., west-uat-restore.pwchalo.com
    "origin",      # e.g., https://login-stg.pwc.com
    "referer",     # e.g., https://login-stg.pwc.com/login/?goto=...
    ":authority",  # HTTP/2 equivalent of Host header
    ":path",       # HTTP/2 path (may contain hostname in query params)
}

def _substitute_hostname_in_header_value(header_name: str, header_value: str, hostname_var_map: dict) -> str:
    """
    Substitute hostnames in header values with JMeter variables.
    
    Handles multiple levels of URL encoding for OAuth redirect chains where
    hostnames appear in nested query parameters like 'goto=' or 'redirect_uri='.
    
    Args:
        header_name: The header name (lowercase)
        header_value: The original header value
        hostname_var_map: Mapping from hostname to JMeter variable name
        
    Returns:
        The header value with hostnames replaced by JMeter variables
        
    Encoding patterns handled:
        - Direct: ://hostname/
        - Single-encoded: %3A%2F%2Fhostname (://hostname encoded)
        - Mixed: :%2F%2Fhostname (only // encoded, common in OAuth redirects)
        - Double-encoded: %253A%252F%252Fhostname (for URL-within-URL)
        - With ports: hostname:443, hostname%3A443, hostname%253A443
    """
    if not hostname_var_map or not header_value:
        return header_value
    
    result = header_value
    
    for hostname, var_name in hostname_var_map.items():
        jmeter_var = f"${{{var_name}}}"
        
        if header_name in ("host", ":authority"):
            # These headers contain just the hostname (no scheme)
            # Direct replacement if exact match
            if result == hostname:
                result = jmeter_var
            # Also handle port suffix (e.g., hostname:443)
            elif result.startswith(hostname + ":"):
                result = jmeter_var + result[len(hostname):]
                
        elif header_name in ("origin", "referer", ":path"):
            # These headers contain URLs or paths with hostnames
            # Process from most-encoded to least-encoded to avoid partial replacements
            
            # URL-encode the hostname for pattern matching
            encoded_hostname = urllib.parse.quote(hostname, safe='')
            
            # === Double-encoded patterns (URL within URL within URL) ===
            # Pattern: %253A%252F%252Fhostname (://hostname double-encoded)
            result = result.replace(f"%253A%252F%252F{hostname}", f"%253A%252F%252F{jmeter_var}")
            # Pattern: %252F%252Fhostname (//hostname double-encoded)
            result = result.replace(f"%252F%252F{hostname}", f"%252F%252F{jmeter_var}")
            
            # === Single-encoded patterns (nested URL in query param) ===
            # Pattern: %3A%2F%2Fhostname (://hostname single-encoded, hostname raw)
            # This is the most common pattern in OAuth redirect chains
            result = result.replace(f"%3A%2F%2F{hostname}", f"%3A%2F%2F{jmeter_var}")
            
            # Pattern: %3A%2F%2F{encoded_hostname} (://hostname single-encoded, hostname also encoded)
            if encoded_hostname != hostname:
                result = result.replace(f"%3A%2F%2F{encoded_hostname}", f"%3A%2F%2F{jmeter_var}")
            
            # Pattern: %2F%2Fhostname (//hostname single-encoded, without colon)
            result = result.replace(f"%2F%2F{hostname}", f"%2F%2F{jmeter_var}")
            if encoded_hostname != hostname:
                result = result.replace(f"%2F%2F{encoded_hostname}", f"%2F%2F{jmeter_var}")
            
            # === Mixed encoding pattern (common in OAuth) ===
            # Pattern: :%2F%2Fhostname (only // is encoded, : is raw)
            # Example: https:%2F%2Flogin-stg.pwc.com:443
            result = result.replace(f":%2F%2F{hostname}", f":%2F%2F{jmeter_var}")
            
            # === Direct (non-encoded) patterns ===
            # Pattern: ://hostname/ or ://hostname? or ://hostname: (with port)
            result = result.replace(f"://{hostname}/", f"://{jmeter_var}/")
            result = result.replace(f"://{hostname}?", f"://{jmeter_var}?")
            result = result.replace(f"://{hostname}:", f"://{jmeter_var}:")  # hostname:port
            result = result.replace(f"://{hostname}&", f"://{jmeter_var}&")  # hostname followed by query param
            
            # Handle end of string
            if result.endswith(f"://{hostname}"):
                result = result[:-len(hostname)] + jmeter_var
    
    return result

def create_header_manager(headers, hostname_var_map=None, exclude_http2_pseudo_headers=True):
    """
    Creates a Header Manager element with the provided headers.
    Excludes headers that are handled by other JMeter components (e.g., 'cookie' is handled by Cookie Manager).
    Optionally parameterizes hostname-related headers (host, origin, referer, :authority, :path).
    
    Args:
        headers: Dictionary of header name -> value pairs
        hostname_var_map: Optional mapping from hostname to JMeter variable name for parameterization
        exclude_http2_pseudo_headers: If True, exclude HTTP/2 pseudo-headers (:method, :path, :scheme, :authority, :status).
                                      JMeter uses HTTP/1.1 by default, and these headers cause errors on non-HTTP/2 backends.
                                      Default is True for compatibility with public websites.
        
    Returns:
        The HeaderManager XML element.
    """
    header_manager = ET.Element("HeaderManager", attrib={
        "guiclass": "HeaderPanel",
        "testclass": "HeaderManager",
        "testname": "HTTP Header Manager"
    })
    collection = ET.SubElement(header_manager, "collectionProp", attrib={"name": "HeaderManager.headers"})
    
    # Build the set of headers to exclude
    headers_to_exclude = set(EXCLUDED_HEADERS)
    if exclude_http2_pseudo_headers:
        headers_to_exclude.update(HTTP2_PSEUDO_HEADERS)
    
    for name, value in headers.items():
        # Skip excluded headers (case-insensitive comparison)
        if name.lower() in headers_to_exclude:
            continue
        
        # Apply hostname parameterization for relevant headers (only if not excluded)
        final_value = value
        if hostname_var_map and name.lower() in HOSTNAME_HEADERS:
            final_value = _substitute_hostname_in_header_value(name.lower(), value, hostname_var_map)
            
        header_element = ET.SubElement(collection, "elementProp", attrib={
            "name": "",
            "elementType": "Header"
        })
        ET.SubElement(header_element, "stringProp", attrib={"name": "Header.name"}).text = name
        ET.SubElement(header_element, "stringProp", attrib={"name": "Header.value"}).text = final_value
    
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
