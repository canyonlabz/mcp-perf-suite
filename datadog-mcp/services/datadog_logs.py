import requests
import json
import csv
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv
from pathlib import Path
from utils.config import load_config
import logging

logger = logging.getLogger(__name__)

# -----------------------------------------------
# Bootstrap
# -----------------------------------------------

load_dotenv()   # Load environment variables from .env file such as API keys and secrets
config = load_config()

# -----------------------------------------------
# Datadog Logs Service
# -----------------------------------------------
class DatadogLogsService:
    def __init__(self, config: dict):
        self.config = config
        self.dd_api_key = os.getenv('DD_API_KEY')
        self.dd_app_key = os.getenv('DD_APP_KEY')
        
        if not self.dd_api_key or not self.dd_app_key:
            raise ValueError("DD_API_KEY and DD_APP_KEY environment variables are required")
    
    def build_query(self, env_tag: str, query_type: str, custom_query: str = None, env_config: dict = None) -> str:
        """Build Datadog log query based on type and environment configuration."""
        
        if query_type == 'custom':
            if not custom_query:
                raise ValueError("Custom query_type requires a custom_query string")
            return custom_query
        
        # Predefined query templates
        templates = {
            'all_errors': f"(env:{env_tag}) AND (status:error OR level:ERROR OR level:CRITICAL OR level:FATAL)",
            'warnings': f"(env:{env_tag}) AND (status:warn OR level:WARN OR level:WARNING)",
            'http_errors': f"(env:{env_tag}) AND (@http.status_code:[400 TO 599])",
            'api_errors': f"(env:{env_tag}) AND (@http.method:* AND @http.status_code:[400 TO 599])"
        }
        
        if query_type in templates:
            return templates[query_type]
        
        # Environment-specific queries
        if query_type == 'service_errors':
            if not env_config or 'services' not in env_config:
                raise ValueError("Environment configuration with services required for service_errors query")
            
            services = [s['service_name'] for s in env_config.get('services', [])]
            if not services:
                return templates['all_errors']  # Fallback to all errors if no services
            
            service_query_part = ' OR '.join([f"service:{s}" for s in services])
            return f"(env:{env_tag}) AND ({service_query_part}) AND (status:error OR level:ERROR)"
        
        if query_type == 'host_errors':
            if not env_config or 'hosts' not in env_config:
                raise ValueError("Environment configuration with hosts required for host_errors query")
            
            hosts = [h['hostname'] for h in env_config.get('hosts', [])]
            if not hosts:
                return templates['all_errors']  # Fallback to all errors if no hosts
            
            host_query_part = ' OR '.join([f"host:{h}" for h in hosts])
            return f"(env:{env_tag}) AND ({host_query_part}) AND (status:error OR level:ERROR)"
        
        if query_type == 'kubernetes_errors':
            if not env_config or 'kubernetes' not in env_config:
                raise ValueError("Environment configuration with kubernetes required for kubernetes_errors query")
            
            k8s_services = env_config.get('kubernetes', {}).get('services', [])
            if not k8s_services:
                return templates['all_errors']  # Fallback to all errors if no k8s services
            
            k8s_query_parts = []
            for svc in k8s_services:
                service_filter = svc.get('service_filter', '')
                if '*' in service_filter:
                    # Wildcard pattern
                    k8s_query_parts.append(f"kube_service:{service_filter}")
                else:
                    # Exact match
                    k8s_query_parts.append(f"kube_service:{service_filter}")
            
            k8s_query_part = ' OR '.join(k8s_query_parts)
            return f"(env:{env_tag}) AND ({k8s_query_part}) AND (status:error OR level:ERROR)"
        
        raise ValueError(f"Unrecognized query_type: {query_type}")
    
    def parse_logs_response(self, response_json: dict) -> Tuple[List[dict], Optional[str]]:
        """Parse Datadog logs API response and extract log entries."""
        logs = []
        
        for entry in response_json.get('data', []):
            attrs = entry.get('attributes', {})
            custom_attrs = attrs.get('attributes', {})
            
            log_entry = {
                'id': entry.get('id'),
                'timestamp': attrs.get('timestamp'),
                'message': attrs.get('message', ''),
                'status': attrs.get('status', ''),
                'service': attrs.get('service', ''),
                'host': attrs.get('host', ''),
                'level': attrs.get('level', ''),
                'source': attrs.get('source', ''),
                'http_status_code': custom_attrs.get('http.status_code', ''),
                'http_method': custom_attrs.get('http.method', ''),
                'error_kind': custom_attrs.get('error.kind', ''),
                'error_stack': custom_attrs.get('error.stack', ''),
                'custom_attributes': json.dumps(custom_attrs) if custom_attrs else ''
            }
            logs.append(log_entry)
        
        # Extract pagination cursor
        pagination = response_json.get('meta', {}).get('page', {})
        next_cursor = pagination.get('after')
        
        return logs, next_cursor
    
    def logs_to_csv(self, logs: List[dict], env_name: str, env_tag: str, query_type: str) -> str:
        """Convert logs to CSV format."""
        if not logs:
            return "env_name,env_tag,query_type,id,timestamp_utc,message,status,service,host,level,source,http_status_code,http_method,error_kind,custom_attributes\n"
        
        csv_rows = []
        fieldnames = ['env_name', 'env_tag', 'query_type', 'id', 'timestamp_utc', 'message', 'status', 'service', 'host', 'level', 'source', 'http_status_code', 'http_method', 'error_kind', 'custom_attributes']
        
        for log in logs:
            row = {
                'env_name': env_name,
                'env_tag': env_tag,
                'query_type': query_type,
                'id': log.get('id', ''),
                'timestamp_utc': log.get('timestamp', ''),
                'message': log.get('message', '').replace('\n', ' ').replace('\r', ' ')[:500],  # Truncate long messages
                'status': log.get('status', ''),
                'service': log.get('service', ''),
                'host': log.get('host', ''),
                'level': log.get('level', ''),
                'source': log.get('source', ''),
                'http_status_code': log.get('http_status_code', ''),
                'http_method': log.get('http_method', ''),
                'error_kind': log.get('error_kind', ''),
                'custom_attributes': log.get('custom_attributes', '')
            }
            csv_rows.append(row)
        
        # Generate CSV content
        import io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
        return output.getvalue()
    
    def normalize_timestamp(self, timestamp: str) -> str:
        """Convert timestamp to ISO 8601 format if needed."""
        # If it's already in ISO format, return as-is
        if 'T' in timestamp and 'Z' in timestamp:
            return timestamp
        
        # If it's epoch timestamp, convert
        try:
            epoch_time = int(timestamp)
            dt = datetime.fromtimestamp(epoch_time)
            return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        except ValueError:
            # Assume it's already in correct format
            return timestamp
    
    def get_logs(self, env_name: str, start_time: str, end_time: str, query_type: str = "custom",
                 custom_query: str = None, limit: int = 1000, run_id: str = None,
                 env_config: dict = None) -> dict:
        """
        Retrieve logs from Datadog Logs API.
        
        Args:
            env_name: Environment name
            start_time: Start time (ISO 8601 or epoch)
            end_time: End time (ISO 8601 or epoch)
            query_type: Type of query template
            custom_query: Custom Datadog query string
            limit: Maximum logs to retrieve
            run_id: Run ID for artifacts organization
            env_config: Environment configuration
            
        Returns:
            Dict with results and file paths
        """
        try:
            # Normalize timestamps
            start_iso = self.normalize_timestamp(start_time)
            end_iso = self.normalize_timestamp(end_time)
            
            # Extract environment configuration
            env_tag = env_config.get('env_tag')
            
            # Build query
            query = self.build_query(env_tag, query_type, custom_query, env_config)
            
            logger.info(f"Fetching logs for {env_name} from {start_iso} to {end_iso}")
            logger.info(f"Query: {query}")
            
            # API request setup
            url = "https://api.datadoghq.com/api/v2/logs/events"
            headers = {
                'DD-API-KEY': self.dd_api_key,
                'DD-APPLICATION-KEY': self.dd_app_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            params = {
                'filter[from]': start_iso,
                'filter[to]': end_iso,
                'filter[query]': query,
                'page[limit]': min(limit, 1000),  # API max is 1000
                'sort': 'timestamp'
            }
            
            # Collect all logs with pagination
            all_logs = []
            next_cursor = None
            page_count = 0
            
            while len(all_logs) < limit and page_count < 10:  # Safety limit on pages
                if next_cursor:
                    params['page[cursor]'] = next_cursor
                
                logger.info(f"Fetching page {page_count + 1}...")
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                response_json = response.json()
                logs, next_cursor = self.parse_logs_response(response_json)
                
                all_logs.extend(logs)
                page_count += 1
                
                if not next_cursor:
                    break
            
            # Limit to requested number
            all_logs = all_logs[:limit]
            
            logger.info(f"Retrieved {len(all_logs)} logs")
            
            # Generate CSV content
            csv_content = self.logs_to_csv(all_logs, env_name, env_tag, query_type)
            
            # Save to artifacts directory
            if not run_id:
                run_id = datetime.now().strftime('%Y-%m-%d_%H%M%S_UTC')
            
            artifacts_path = Path(self.config['artifacts']['artifacts_path'])
            run_artifacts_dir = artifacts_path / run_id / 'datadog'
            run_artifacts_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            safe_query_type = query_type.replace('_', '-')
            csv_filename = f"logs_{safe_query_type}_{env_name.lower()}.csv"
            csv_filepath = run_artifacts_dir / csv_filename
            
            # Write CSV file
            with open(csv_filepath, 'w', encoding='utf-8', newline='') as f:
                f.write(csv_content)
            
            logger.info(f"Saved logs to: {csv_filepath}")
            
            # Summary statistics
            status_counts = {}
            level_counts = {}
            service_counts = {}
            
            for log in all_logs:
                status = log.get('status', 'unknown')
                level = log.get('level', 'unknown')
                service = log.get('service', 'unknown')
                
                status_counts[status] = status_counts.get(status, 0) + 1
                level_counts[level] = level_counts.get(level, 0) + 1
                service_counts[service] = service_counts.get(service, 0) + 1
            
            return {
                'env_name': env_name,
                'env_tag': env_tag,
                'query_type': query_type,
                'query': query,
                'time_range': {
                    'start': start_iso,
                    'end': end_iso
                },
                'log_count': len(all_logs),
                'pages_fetched': page_count,
                'csv_file': str(csv_filepath),
                'run_id': run_id,
                'summary': {
                    'status_counts': status_counts,
                    'level_counts': level_counts,
                    'top_services': dict(sorted(service_counts.items(), key=lambda x: x[1], reverse=True)[:10])
                }
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            raise Exception(f"Datadog API request failed: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error retrieving logs: {str(e)}")
            raise

# Initialize service instance
datadog_logs_service = DatadogLogsService(config)
