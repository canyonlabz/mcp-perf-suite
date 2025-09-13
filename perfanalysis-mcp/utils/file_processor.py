# utils/file_processor.py

import pandas as pd
import json
from pathlib import Path
from typing import Optional, Dict, Any

def load_jmeter_results(file_path: Path) -> Optional[pd.DataFrame]:
    """Load JMeter results from CSV file"""
    try:
        df = pd.read_csv(file_path)
        # Basic validation of required columns
        required_cols = ['timeStamp', 'elapsed', 'label', 'responseCode', 'success']
        if not all(col in df.columns for col in required_cols):
            return None
        return df
    except Exception:
        return None

def load_datadog_metrics(file_path: Path) -> Optional[pd.DataFrame]:
    """Load Datadog metrics from CSV file"""
    try:
        return pd.read_csv(file_path)
    except Exception:
        return None

def write_json_output(data: Dict[str, Any], file_path: Path):
    """Write data to JSON file"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

def write_csv_output(data: pd.DataFrame, file_path: Path):
    """Write DataFrame to CSV file"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(file_path, index=False)

def write_markdown_output(content: str, file_path: Path):
    """Write markdown content to file"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w') as f:
        f.write(content)
