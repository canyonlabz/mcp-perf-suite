"""
jmeter_utils.py

This module contains functions to create the main JMeter core components.
For example, it includes functions to generate "Test Plan", "Thread Group" components, etc.
End-users and developers can extend or modify these functions independently
of the core JMeter component utilities.
"""
import xml.etree.ElementTree as ET
import datetime
import os
import urllib.parse
from xml.dom import minidom

# === Create Test Plan Element ===
def create_test_plan(test_plan_name="Test Plan"):
    """
    Creates the root TestPlan element and its nested hashTree.
    Returns:
      - The root element (jmeterTestPlan)
      - The hashTree for the TestPlan (where Thread Groups will be added)
    """
    jmeter_test_plan = ET.Element("jmeterTestPlan", attrib={
        "version": "1.2",
        "properties": "5.0",
        "jmeter": "5.6.3"
    })
    hash_tree = ET.SubElement(jmeter_test_plan, "hashTree")
    
    test_plan = ET.SubElement(hash_tree, "TestPlan", attrib={
        "guiclass": "TestPlanGui",
        "testclass": "TestPlan",
        "testname": test_plan_name
    })
    user_defined_vars = ET.SubElement(test_plan, "elementProp", attrib={
        "name": "TestPlan.user_defined_variables",
        "elementType": "Arguments"
    })
    ET.SubElement(user_defined_vars, "collectionProp", attrib={"name": "Arguments.arguments"})
    ET.SubElement(test_plan, "stringProp", attrib={"name": "TestPlan.user_define_classpath"}).text = ""
    
    test_plan_hash_tree = ET.SubElement(hash_tree, "hashTree")
    return jmeter_test_plan, test_plan_hash_tree

# === Create Thread Group Element ===
def create_thread_group(thread_group_name="Thread Group", num_threads="1", ramp_time="1", loops="1"):
    """
    Creates a Thread Group element along with its nested hashTree.
    Returns:
      - The ThreadGroup element
      - Its nested hashTree element
    """
    thread_group = ET.Element("ThreadGroup", attrib={
        "guiclass": "ThreadGroupGui",
        "testclass": "ThreadGroup",
        "testname": thread_group_name
    })
    ET.SubElement(thread_group, "stringProp", attrib={"name": "ThreadGroup.num_threads"}).text = num_threads
    ET.SubElement(thread_group, "stringProp", attrib={"name": "ThreadGroup.ramp_time"}).text = ramp_time
    ET.SubElement(thread_group, "longProp", attrib={"name": "ThreadGroup.duration"}).text = "0"
    ET.SubElement(thread_group, "boolProp", attrib={"name": "ThreadGroup.scheduler"}).text = "false"
    
    loop_controller = ET.SubElement(thread_group, "elementProp", attrib={
        "name": "ThreadGroup.main_controller",
        "elementType": "LoopController"
    })
    ET.SubElement(loop_controller, "stringProp", attrib={"name": "LoopController.loops"}).text = loops
    ET.SubElement(loop_controller, "boolProp", attrib={"name": "LoopController.continue_forever"}).text = "false"
    
    thread_group_hash_tree = ET.Element("hashTree")
    return thread_group, thread_group_hash_tree

# === Save JMX File ===
def save_jmx_file(root_element, output_dir="generated_jmx"):
    """
    Saves the given XML tree (root_element) as a pretty-printed JMX file.
    The filename will include a timestamp for uniqueness.
    Returns the output file path.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"generated_test_plan_{timestamp}.jmx")
    xml_string = ET.tostring(root_element, encoding="utf-8")
    pretty_xml = minidom.parseString(xml_string).toprettyxml(indent="  ")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(pretty_xml)
    print(f"JMX file generated successfully: {output_file}")
    return output_file
