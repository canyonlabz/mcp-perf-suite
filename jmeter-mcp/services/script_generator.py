import sys
import json
import os
from typing import Callable

# Import necessary modules for JMeter JMX generation
import xml.etree.ElementTree as ET  # Needed for creating empty hashTree elements
from utils.config import load_config, load_jmeter_config
from services.jmx.plan import (
    create_test_plan,
    create_thread_group
)
from services.jmx.controllers import (
    create_simple_controller,
    create_transaction_controller,
    # …add more factory functions as you build them…
)
from services.jmx.samplers import (
    create_http_sampler_get,
    create_http_sampler_with_body,
    append_sampler
)
from services.jmx.config_elements import (
    create_cookie_manager,
    create_user_defined_variables,
    create_csv_data_set_config
)
from services.jmx.listeners import (
    create_view_results_tree,
    create_aggregate_report
)
from utils.file_utils import save_jmx_file

# === Main JMeter JMX Generator function ===
def run_jmx_generator(json_file: str, log_callback: Callable[[str], None] = print) -> str:
    """
    Generate a JMeter JMX file from a network capture JSON file.
    """
    # === Load Configuration Files ===
    config = load_config()
    jmeter_config = load_jmeter_config()

    # === Network Capture File ===
    # Check if the provided JSON file exists and is valid.
    if not json_file or not os.path.isfile(json_file):
        # If the file path is empty or does not exist, print an error message and exit.
        log_callback(f"Error: No JSON file provided or file does not exist for given: '{json_file}'")
        raise ValueError(f"No JSON file provided or file does not exist for given: '{json_file}'")
    # Check if the file is a valid JSON file.
    if not json_file.endswith('.json'):
        # If the file is not a JSON file, print an error message and exit.
        log_callback(f"Error: File '{json_file}' is not a valid JSON file.")
        raise ValueError(f"File '{json_file}' is not a valid JSON file.")
    
    # Load the network capture JSON file.
    with open(json_file, "r", encoding="utf-8") as f:
        network_data = json.load(f)

    log_callback(f"✅ Loaded network capture JSON file: {json_file}")
    log_callback(f"Network data contains {len(network_data)} entries.")
    
    # ============================================================
    # === JMeter JMX File Configurations ===
    # ============================================================

    # === Create JMeter Test Plan ===
    # Create the root Test Plan and its hashTree.
    test_plan, test_plan_hash_tree = create_test_plan()

    # === Add Optional Test Plan Elements ===
    # Add Cookie Manager if enabled.
    cookie_mgr_cfg = jmeter_config.get("cookie_manager", {"enabled": False})
    if cookie_mgr_cfg.get("enabled", False):
        cookie_manager_elem = create_cookie_manager()
        test_plan_hash_tree.append(cookie_manager_elem)
        test_plan_hash_tree.append(ET.Element("hashTree"))
    
    # Add User Defined Variables if enabled.
    udv_cfg = jmeter_config.get("user_defined_variables", {"enabled": False})
    udv_elem = create_user_defined_variables(udv_cfg)
    if udv_elem is not None:
        test_plan_hash_tree.append(udv_elem)
        test_plan_hash_tree.append(ET.Element("hashTree"))
    
    # Add CSV Data Set Config if enabled.
    csv_cfg = jmeter_config.get("csv_dataset_config", {"enabled": False})
    csv_elem = create_csv_data_set_config(csv_cfg)
    if csv_elem is not None:
        test_plan_hash_tree.append(csv_elem)
        test_plan_hash_tree.append(ET.Element("hashTree"))

    # === Create Thread Group ===
    # Create a single Thread Group using defaults from jmeter_config.
    tg_config = jmeter_config.get("thread_group", {})
    num_threads = str(tg_config.get("num_threads", 1))
    ramp_time = str(tg_config.get("ramp_time", 1))
    loops = str(tg_config.get("loops", 1))
    thread_group, thread_group_hash_tree = create_thread_group(
        num_threads=num_threads, ramp_time=ramp_time, loops=loops
    )
    # Append the thread group and its hashTree to the Test Plan.
    test_plan_hash_tree.append(thread_group)
    test_plan_hash_tree.append(thread_group_hash_tree)
    
    # === Create HTTP Request Samplers (possibly grouped in Controllers) ===
    ctrl_cfg = jmeter_config.get("controller_config", {})
    use_controllers = ctrl_cfg.get("enabled", False)

    if use_controllers:
        ctrl_type = ctrl_cfg.get("controller_type", "simple").lower()
        # pick factory based on type
        factory = {
            "simple": create_simple_controller,
            "transaction": create_transaction_controller,
            # Add more controller types as needed
        }.get(ctrl_type, create_simple_controller)

        for step_name, entries in network_data.items():
            # create the Controller node + its hashTree
            ctrl_elem, ctrl_hash = factory(testname=step_name)
            thread_group_hash_tree.append(ctrl_elem)
            thread_group_hash_tree.append(ctrl_hash)

            # Now append each sampler under this controller
            for entry in entries:
                method = entry.get("method", "GET").upper()
                if method == "GET":
                    sampler, header_manager = create_http_sampler_get(entry)
                else:
                    sampler, header_manager = create_http_sampler_with_body(entry)
                append_sampler(ctrl_hash, sampler, header_manager)
    else:
        # === Create HTTP Request Samplers ===
        # Iterate through the network capture entries.
        # Assume network_data is a dictionary where keys are URLs and values are entry dicts.
        for url, entry in network_data.items():
            # Ensure each entry has its "url" field.
            if "url" not in entry:
                entry["url"] = url
            method = entry.get("method", "GET").upper()
            if method == "GET":
                sampler, header_manager = create_http_sampler_get(entry)
            else:
                sampler, header_manager = create_http_sampler_with_body(entry)
            
            # Append the sampler and its header manager (if any) into the Thread Group's hashTree.
            append_sampler(thread_group_hash_tree, sampler, header_manager)

    # === Add Listeners (outside the Thread Group) ===
    results_cfg = jmeter_config.get("results_collector_config", {})
    
    # Add View Results Tree if enabled.
    if results_cfg.get("view_results_tree", True):
        view_results_tree_settings = results_cfg.get("view_results_tree_settings", {})
        vrt_elem, vrt_hash_tree = create_view_results_tree(view_results_tree_settings)
        test_plan_hash_tree.append(vrt_elem)
        test_plan_hash_tree.append(vrt_hash_tree)

    # Add Aggregate Report if enabled.
    if results_cfg.get("aggregate_report", True):
        aggregate_report_settings = results_cfg.get("aggregate_report_settings", {})
        ar_elem, ar_hash_tree = create_aggregate_report(aggregate_report_settings)
        test_plan_hash_tree.append(ar_elem)
        test_plan_hash_tree.append(ar_hash_tree)

    # (You can add additional listeners here, e.g., Aggregate Report, Response Time Graph, etc.)

    # Determine the output directory from the general config (jmeter section).
    jmx_output_path = config.get("jmeter", {}).get("jmx_output_path", "generated_jmx")
    
    # Save the complete JMX file to the output directory.
    # Saves the JMX file in the format: /{jmx_output_path}/generated_test_plan_{timestamp}.jmx
    jmx_file = save_jmx_file(test_plan, output_dir=jmx_output_path)
    if not jmx_file:
        log_callback("❌ Failed to generate JMX file.")
        raise RuntimeError("Failed to generate JMX file.")
    log_callback(f"✅ JMX file generated successfully at: {jmx_file}")
    return jmx_file

