# utils/statistical_analyzer.py
import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Any
from scipy.stats import pearsonr, spearmanr

# -----------------------------------------------
# Statistical analysis functions
# -----------------------------------------------
def calculate_response_time_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate comprehensive response time statistics"""
    
    # Overall statistics
    overall_stats = {
        "total_samples": len(df),
        "success_rate": (df['success'].sum() / len(df)) * 100 if 'success' in df.columns else 0,
        "avg_response_time": df['elapsed'].mean(),
        "min_response_time": df['elapsed'].min(),
        "max_response_time": df['elapsed'].max(),
        "p90_response_time": df['elapsed'].quantile(0.9),
        "p95_response_time": df['elapsed'].quantile(0.95),
        "p99_response_time": df['elapsed'].quantile(0.99),
        "std_dev": df['elapsed'].std(),
        "error_count": len(df[df['success'] == False]) if 'success' in df.columns else 0
    }
    
    # Per-API statistics
    api_analysis = {}
    if 'label' in df.columns:
        for label in df['label'].unique():
            label_df = df[df['label'] == label]
            api_analysis[label] = {
                "samples": len(label_df),
                "avg_response_time": label_df['elapsed'].mean(),
                "min_response_time": label_df['elapsed'].min(),
                "max_response_time": label_df['elapsed'].max(),
                "p90_response_time": label_df['elapsed'].quantile(0.9),
                "success_rate": (label_df['success'].sum() / len(label_df)) * 100 if 'success' in label_df.columns else 0,
                "error_count": len(label_df[label_df['success'] == False]) if 'success' in label_df.columns else 0
            }
    
    return {
        "overall_stats": overall_stats,
        "api_analysis": api_analysis,
        "analysis_timestamp": pd.Timestamp.now().isoformat()
    }

def calculate_correlation_matrix(performance_data: Dict, infrastructure_data: Dict, test_run_id: str) -> Dict:
    """Calculate correlation between performance and infrastructure metrics"""
    
    correlations = {
        "test_run_id": test_run_id,
        "correlation_matrix": {},
        "significant_correlations": [],
        "correlation_threshold": 0.3
    }
    
    # Extract key metrics for correlation
    perf_metrics = performance_data.get('overall_stats', {})
    infra_metrics = infrastructure_data.get('host_analysis', {})
    
    # Implementation would calculate correlations between response times and resource utilization
    # This is a simplified placeholder
    
    return correlations

def detect_statistical_anomalies(blazemeter_file: Path, datadog_files: List[Path], sensitivity: str) -> Dict:
    """Detect anomalies using statistical methods"""
    
    # Map sensitivity to standard deviations
    sensitivity_map = {"low": 3.0, "medium": 2.5, "high": 2.0}
    threshold = sensitivity_map.get(sensitivity, 2.5)
    
    anomalies = {
        "sensitivity": sensitivity,
        "threshold_std_dev": threshold,
        "anomalies": [],
        "summary": {
            "total_anomalies": 0,
            "response_time_anomalies": 0,
            "resource_anomalies": 0
        }
    }
    
    # Load and analyze BlazeMeter data for response time anomalies
    if blazemeter_file.exists():
        df = pd.read_csv(blazemeter_file)
        mean_rt = df['elapsed'].mean()
        std_rt = df['elapsed'].std()
        
        # Detect response time anomalies
        rt_anomalies = df[(np.abs(df['elapsed'] - mean_rt) > threshold * std_rt)]
        
        for _, row in rt_anomalies.iterrows():
            anomalies["anomalies"].append({
                "type": "response_time",
                "timestamp": row['timeStamp'],
                "api": row.get('label', 'unknown'),
                "value": row['elapsed'],
                "z_score": (row['elapsed'] - mean_rt) / std_rt,
                "severity": "high" if abs((row['elapsed'] - mean_rt) / std_rt) > threshold + 1 else "medium"
            })
    
    anomalies["summary"]["total_anomalies"] = len(anomalies["anomalies"])
    return anomalies

def identify_resource_bottlenecks(correlation_file: Path, anomaly_file: Path, test_run_id: str) -> Dict:
    """Identify system bottlenecks based on correlation and anomaly analysis"""
    
    bottlenecks = {
        "test_run_id": test_run_id,
        "bottlenecks": [],
        "recommendations": [],
        "priority_ranking": []
    }
    
    # Load correlation and anomaly data
    if correlation_file.exists():
        with open(correlation_file, 'r') as f:
            correlation_data = json.load(f)
    
    if anomaly_file and anomaly_file.exists():
        with open(anomaly_file, 'r') as f:
            anomaly_data = json.load(f)
    
    # Analyze patterns and identify bottlenecks
    # This would involve more complex logic to identify resource constraints
    
    return bottlenecks
