import asyncio
import logging
import sys
import os
import re
from urllib.parse import urlparse

# === Set up logging ===
def setup_logging(log_level_str="INFO"):
    # Convert string to logging level (default to INFO if invalid)
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    
    # Create a logger
    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)
    
    # Disable propagation to the root logger
    logger.propagate = False

    # Avoid adding duplicate handlers
    if not logger.handlers:
        # Create a stream-based handler
        handler = logging.StreamHandler(sys.stdout)
        
        # Create a formatter and add it to the handler
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        # Add the handler to the logger
        logger.addHandler(handler)
    
    return logger

# === Define where the recordings will be saved ===
def get_recording_path(config):
    # Check if recording is enabled in the config
    if not config.get("enable_recording", False):
        return None

    # Get the path from the config or use a default path
    recording_path = config.get("save_recording_path", "./tmp/recordings")
    
    # Ensure the directory exists
    os.makedirs(recording_path, exist_ok=True)
    
    return recording_path

# === Define the trace path ===
def get_trace_path(config):
    # Check if tracing is enabled in the config
    if not config.get("enable_trace", False):
        return None

    # Check if tracing is set to False in the config
    if config.get("enable_trace") is False:
        return None

    # Get the path from the config or use a default path
    trace_path = config.get("trace_path", "./tmp/trace")
    
    # Ensure the directory exists
    os.makedirs(trace_path, exist_ok=True)
    
    return trace_path

# === Define the conversation path ===
def get_conversation_path(config):
    # Check if conversation saving is enabled in the config
    if not config.get("enable_conversation", False):
        return None

    # Check if conversation saving is set to False in the config
    if config.get("enable_conversation") is False:
        return None

    # Get the path from the config or use a default path
    conversation_path = config.get("save_conversation_path", "./tmp/conversations/")
    
    # Ensure the directory exists
    os.makedirs(conversation_path, exist_ok=True)
    
    return conversation_path

# === Extract the apex domain from a task ===
def extract_apex_domain_from_task(task_text: str) -> str:
    """
    Scans the task text for the first http(s) URL and returns its apex domain
    (the last two labels), e.g. example.com. Strips any port number.
    If none found, returns an empty string.
    """
    # find any http(s) URLs
    urls = re.findall(r"https?://[^\s,;]+", task_text)
    if not urls:
        return ""
    parsed = urlparse(urls[0])
    # remove port if present
    host = parsed.netloc.split(":", 1)[0]
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host

# === Run an async coroutine with a timeout ===
async def run_with_timeout(coro, timeout_seconds):
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        print(f"⏰ Step timed out after {timeout_seconds} seconds.")
        return None
