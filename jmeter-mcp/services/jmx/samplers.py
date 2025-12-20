"""
services/jmx/samplers.py

This module contains functions to create JMeter Sampler components.
For example, it includes functions to generate "HTTP Request", "Flow Control Action" components, etc.
End-users and developers can extend or modify these functions independently
of the core JMeter component utilities.
"""
import xml.etree.ElementTree as ET
import datetime
import os
import urllib.parse
from xml.dom import minidom
from services.jmx.config_elements import (
    create_header_manager
)

# === HTTP Sampler for GET Requests ===
def create_http_sampler_get(entry):
    """
    Creates an HTTP Sampler for a GET request.
    'entry' is a dictionary containing:
      - url (full URL)
      - method (expected to be GET)
      - headers (dictionary of headers)
    Returns:
      - The HTTPSamplerProxy element
      - (Optionally) the HeaderManager element if headers exist, otherwise None.
    """
    url = entry.get("url", "")
    method = entry.get("method", "GET")
    headers = entry.get("headers", {})
    parsed_url = urllib.parse.urlparse(url)
    domain = parsed_url.netloc
    protocol = parsed_url.scheme if parsed_url.scheme else "http"
    path = parsed_url.path if parsed_url.path else "/"
    
    sampler = ET.Element("HTTPSamplerProxy", attrib={
        "guiclass": "HttpTestSampleGui",
        "testclass": "HTTPSamplerProxy",
        "testname": f"{method.upper()} {path}"
    })
    ET.SubElement(sampler, "stringProp", attrib={"name": "HTTPSampler.domain"}).text = domain
    ET.SubElement(sampler, "stringProp", attrib={"name": "HTTPSampler.protocol"}).text = protocol
    ET.SubElement(sampler, "stringProp", attrib={"name": "HTTPSampler.path"}).text = path
    ET.SubElement(sampler, "stringProp", attrib={"name": "HTTPSampler.method"}).text = method.upper()
    ET.SubElement(sampler, "stringProp", attrib={"name": "HTTPSampler.postBodyRaw"}).text = ""
    ET.SubElement(sampler, "boolProp", attrib={"name": "HTTPSampler.auto_redirects"}).text = "true"
    
    header_manager = create_header_manager(headers) if headers else None
    return sampler, header_manager

# === HTTP Sampler for POST/PUT/DELETE Requests ===
def create_http_sampler_with_body(entry):
    """
    Creates an HTTP Sampler for POST/PUT/DELETE requests.
    'entry' should include:
      - url, method, headers, and post_data (the raw body)
    Returns:
      - The HTTPSamplerProxy element
      - (Optionally) the HeaderManager element if headers exist.
    """
    url = entry.get("url", "")
    method = entry.get("method", "POST")
    headers = entry.get("headers", {})
    post_data = entry.get("post_data", "")

    parsed_url = urllib.parse.urlparse(url)
    domain = parsed_url.netloc
    protocol = parsed_url.scheme if parsed_url.scheme else "http"
    path = parsed_url.path if parsed_url.path else "/"

    # Create the HTTPSamplerProxy element
    sampler = ET.Element("HTTPSamplerProxy", attrib={
        "guiclass": "HttpTestSampleGui",
        "testclass": "HTTPSamplerProxy",
        "testname": f"{method.upper()} {path}"
    })
    ET.SubElement(sampler, "stringProp", attrib={"name": "HTTPSampler.domain"}).text = domain
    ET.SubElement(sampler, "stringProp", attrib={"name": "HTTPSampler.protocol"}).text = protocol
    ET.SubElement(sampler, "stringProp", attrib={"name": "HTTPSampler.path"}).text = path
    ET.SubElement(sampler, "stringProp", attrib={"name": "HTTPSampler.method"}).text = method.upper()
    ET.SubElement(sampler, "boolProp", attrib={"name": "HTTPSampler.auto_redirects"}).text = "true"
    
    # ----------------------------
    # Here is the crucial part for raw body in JMeter:
    # ----------------------------
    # 1) Mark postBodyRaw as true
    ET.SubElement(sampler, "boolProp", attrib={"name": "HTTPSampler.postBodyRaw"}).text = "true"
    
    # 2) Create the HTTPsampler.Arguments element
    arguments_prop = ET.SubElement(sampler, "elementProp", attrib={
        "name": "HTTPsampler.Arguments",
        "elementType": "Arguments"
    })
    collection_prop = ET.SubElement(arguments_prop, "collectionProp", attrib={
        "name": "Arguments.arguments"
    })
    
    # 3) Create a single HTTPArgument to hold the raw body
    arg_element = ET.SubElement(collection_prop, "elementProp", attrib={
        "name": "",
        "elementType": "HTTPArgument"
    })
    # Do not automatically encode the body
    ET.SubElement(arg_element, "boolProp", attrib={"name": "HTTPArgument.always_encode"}).text = "false"
    # The actual body content
    ET.SubElement(arg_element, "stringProp", attrib={"name": "Argument.value"}).text = post_data
    # JMeter uses this to separate name/value pairs; for raw body, we just use "="
    ET.SubElement(arg_element, "stringProp", attrib={"name": "Argument.metadata"}).text = "="
    # Tells JMeter not to treat this as a name=value form
    ET.SubElement(arg_element, "boolProp", attrib={"name": "HTTPArgument.use_equals"}).text = "true"

    # Create a header manager if needed
    header_manager = create_header_manager(headers) if headers else None

    return sampler, header_manager

# === Append Sampler to Parent HashTree ===
def append_sampler(parent, sampler, header_manager=None, extractors=None):
    """
    Appends a sampler and its children to the parent hashTree.
    JMeter expects that every sampler is immediately followed by a hashTree element.
    If a HeaderManager exists, it is placed inside its own hashTree.
    If extractors are provided, they are added as post-processors.
    
    Args:
        parent: The parent hashTree element (Thread Group or Controller)
        sampler: The HTTP Sampler element
        header_manager: Optional HeaderManager element
        extractors: Optional list of extractor elements (JSON, Regex, etc.)
    
    Returns:
        ET.Element: The sampler's hashTree (for further modifications if needed)
    """
    # Append the sampler
    parent.append(sampler)
    # Create a hashTree for the sampler's children.
    sampler_hash_tree = ET.Element("hashTree")
    
    # Add HeaderManager if present
    if header_manager is not None:
        sampler_hash_tree.append(header_manager)
        # Append an empty hashTree for the HeaderManager's children.
        header_hash_tree = ET.Element("hashTree")
        sampler_hash_tree.append(header_hash_tree)
    
    # Add extractors (post-processors) if present
    if extractors:
        for extractor in extractors:
            sampler_hash_tree.append(extractor)
            # Each extractor needs its own empty hashTree
            sampler_hash_tree.append(ET.Element("hashTree"))
    
    parent.append(sampler_hash_tree)
    return sampler_hash_tree

# === Flow Control Action Sampler ===
def create_flow_control_action(action_type="pause", testname="Flow Control Action"):
    """
    Creates a Flow Control Action sampler.
    'action_type' can be "pause", "stop", or "interrupt".
    Returns the FlowControlAction element.
    """
    action = ET.Element("FlowControlAction", attrib={
        "guiclass": "FlowControlActionGui",
        "testclass": "FlowControlAction",
        "testname": testname
    })
    ET.SubElement(action, "stringProp", attrib={"name": "FlowControlAction.action"}).text = action_type.lower()
    return action

