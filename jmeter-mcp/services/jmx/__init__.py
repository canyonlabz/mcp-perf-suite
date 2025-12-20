# services/jmx/__init__.py
"""
JMeter JMX Builder Package

This package provides modular functions to create JMeter JMX script elements:
- plan.py: Test Plan and Thread Group
- controllers.py: Simple Controller, Transaction Controller
- samplers.py: HTTP Request samplers
- config_elements.py: Cookie Manager, User Defined Variables, CSV Data Set, Header Manager
- listeners.py: View Results Tree, Aggregate Report
- post_processor.py: JSON Extractor, Regex Extractor, Boundary Extractor
- pre_processor.py: JSR223 PreProcessor, Timestamp, UUID, PKCE generators
- oauth2.py: OAuth 2.0 specific elements
"""

# Post-Processors (Extractors)
from .post_processor import (
    create_json_extractor,
    create_regex_extractor,
    create_boundary_extractor,
    append_extractor
)

# Pre-Processors
from .pre_processor import (
    create_jsr223_preprocessor,
    create_timestamp_preprocessor,
    create_multiple_timestamps_preprocessor,
    create_uuid_preprocessor,
    create_pkce_preprocessor,
    create_cookie_preprocessor,
    append_preprocessor
)

# Expose commonly used functions at package level
__all__ = [
    # Post-Processors
    "create_json_extractor",
    "create_regex_extractor",
    "create_boundary_extractor",
    "append_extractor",
    # Pre-Processors
    "create_jsr223_preprocessor",
    "create_timestamp_preprocessor",
    "create_multiple_timestamps_preprocessor",
    "create_uuid_preprocessor",
    "create_pkce_preprocessor",
    "create_cookie_preprocessor",
    "append_preprocessor",
]

