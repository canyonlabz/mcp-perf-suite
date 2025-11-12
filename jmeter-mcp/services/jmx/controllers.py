import xml.etree.ElementTree as ET
from typing import Tuple

# jmeter_controllers.py
# Factory methods for JMeter controllers (e.g. Simple, Transaction)

def create_simple_controller(testname: str = "Simple Controller") -> Tuple[ET.Element, ET.Element]:
    """
    Create a Simple Controller element with the given testname,
    plus an empty hashTree for its children.
    """
    controller = ET.Element("GenericController", attrib={
        "guiclass": "LogicControllerGui",
        "testclass": "GenericController",
        "testname": testname
    })
    hash_tree = ET.Element("hashTree")
    return controller, hash_tree


def create_transaction_controller(
    testname: str = "Transaction Controller",
    include_timers: bool = True
) -> Tuple[ET.Element, ET.Element]:
    """
    Create a Transaction Controller element with an accompanying hashTree.
    :param testname: Display name for the controller
    :param include_timers: Whether to include child timers in the transaction
    """
    controller = ET.Element("TransactionController", attrib={
        "guiclass": "TransactionControllerGui",
        "testclass": "TransactionController",
        "testname": testname
    })
    # add includeTimers property
    bool_prop = ET.SubElement(
        controller,
        "boolProp",
        name="TransactionController.includeTimers"
    )
    bool_prop.text = str(include_timers).lower()

    hash_tree = ET.Element("hashTree")
    return controller, hash_tree

# TODO: add more controller factory functions (Loop, If, While, ForEach, Switch, etc.),
# following the same pattern: accept `testname`, return (element, hashTree).
