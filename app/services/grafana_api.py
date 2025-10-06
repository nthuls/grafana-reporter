# app/services/grafana_api.py
import requests
import json
import re
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from app.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GrafanaService:
    """Service for interacting with Grafana API to fetch datasources, indices, fields, dashboards, and panel data"""
    
    def __init__(self):
        self.base_url = settings.GRAFANA_URL
        self.api_key = settings.GRAFANA_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self.logger = logging.getLogger(__name__)
    
    def get_datasources(self) -> List[Dict[str, Any]]:
        """Fetch available data sources from Grafana"""
        url = f"{self.base_url}/api/datasources"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        # Filter for Elasticsearch and OpenSearch datasources
        datasources = response.json()
        return [
            {
                "id": ds["id"],
                "uid": ds["uid"],
                "name": ds["name"],
                "type": ds["type"]
            }
            for ds in datasources
            if ds["type"] in ["elasticsearch", "grafana-opensearch-datasource"]
        ]
    
    def get_indices(self, datasource_id: str) -> List[str]:
        """Fetch available indices for a datasource"""
        url = f"{self.base_url}/api/datasources/{datasource_id}"
        
        # First get the datasource details
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        datasource = response.json()
        
        # Then get the indices based on datasource type
        if datasource["type"] == "elasticsearch":
            return self._get_elasticsearch_indices(datasource)
        elif datasource["type"] == "grafana-opensearch-datasource":
            return self._get_opensearch_indices(datasource)
        else:
            raise Exception(f"Unsupported datasource type: {datasource['type']}")
    
    def _get_elasticsearch_indices(self, datasource: Dict[str, Any]) -> List[str]:
        """Get all indices via Grafana proxy"""
        url = f"{self.base_url}/api/datasources/proxy/{datasource['id']}/_cat/indices?format=json"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        indices_data = response.json()

        # Return all indices
        all_indices = [index["index"] for index in indices_data]

        return all_indices
    
    def _get_opensearch_indices(self, datasource: Dict[str, Any]) -> List[str]:
        """Get indices from OpenSearch datasource"""
        # Similar to Elasticsearch but using OpenSearch API
        return self._get_elasticsearch_indices(datasource)  # They use the same API
    
    def get_fields(self, datasource_id: str, index: str) -> List[Dict[str, Any]]:
        """Fetch available fields for an index"""
        url = f"{self.base_url}/api/datasources/proxy/{datasource_id}/{index}/_mapping"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        # Parse the mapping response to extract fields
        mappings = response.json()
        fields = self._extract_fields_from_mapping(mappings)
        
        return fields
    
    def _extract_fields_from_mapping(self, mappings: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract fields from Elasticsearch/OpenSearch mapping response"""
        fields = []
        
        # Iterate through the mapping to extract field names and types
        for index_name, index_mapping in mappings.items():
            properties = index_mapping.get("mappings", {}).get("properties", {})
            if not properties:
                # Try alternate mapping structure
                properties = index_mapping.get("mappings", {}).get("_doc", {}).get("properties", {})
            
            self._process_properties(properties, "", fields)
        
        return sorted(fields, key=lambda x: x["name"])
    
    def _process_properties(self, properties: Dict[str, Any], prefix: str, fields: List[Dict[str, str]]) -> None:
        """Recursively process mapping properties to extract field info"""
        for field_name, field_info in properties.items():
            full_name = f"{prefix}{field_name}" if prefix else field_name
            
            if "type" in field_info:
                fields.append({"name": full_name, "type": field_info["type"]})
            
            # Process nested fields
            if "properties" in field_info:
                new_prefix = f"{full_name}."
                self._process_properties(field_info["properties"], new_prefix, fields)
    
    def get_data(self, datasource_id: str, index: str, fields: List[str], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch data from the datasource based on selected fields and filters"""
        # Construct Elasticsearch/OpenSearch query based on filters
        query = self._build_query(filters)
        
        # Prepare request
        url = f"{self.base_url}/api/datasources/proxy/{datasource_id}/{index}/_search"
        payload = {
            "query": query,
            "_source": fields,
            "size": 10000  # Limit results, adjust as needed
        }
        
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        
        # Extract results
        results = response.json()
        hits = results.get("hits", {}).get("hits", [])
        
        # Format data for report
        data = []
        for hit in hits:
            source = hit.get("_source", {})
            row = {}
            for field in fields:
                # Handle nested fields
                value = source
                for part in field.split("."):
                    value = value.get(part, {}) if isinstance(value, dict) else None
                
                # Convert non-primitive types to string
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                
                row[field] = value
            data.append(row)
        
        return data
    
    def _build_query(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Build Elasticsearch/OpenSearch query from filters"""
        if not filters:
            return {"match_all": {}}
        
        # Convert filters to Elasticsearch/OpenSearch query
        must_clauses = []
        for field, value in filters.items():
            if isinstance(value, dict) and ("gte" in value or "lte" in value):
                # Range query
                must_clauses.append({
                    "range": {
                        field: value
                    }
                })
            elif isinstance(value, list):
                # Terms query (multiple values)
                must_clauses.append({
                    "terms": {
                        field: value
                    }
                })
            else:
                # Match query (single value)
                must_clauses.append({
                    "match": {
                        field: value
                    }
                })
        
        return {
            "bool": {
                "must": must_clauses
            }
        }
    
    # New methods for dashboard and panel operations
    def get_dashboards(self) -> List[Dict[str, Any]]:
        """Fetch available dashboards from Grafana"""
        url = f"{self.base_url}/api/search"
        params = {
            "type": "dash-db",  # Only return dashboards
            "limit": 100        # Limit to 100 dashboards, adjust as needed
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        
        dashboards = response.json()
        # Filter out folders and clean up the response
        return [
            {
                "uid": dash.get("uid", ""),
                "title": dash.get("title", ""),
                "url": dash.get("url", ""),
                "tags": dash.get("tags", []),
                "folder": dash.get("folderTitle", "")
            }
            for dash in dashboards
            if dash.get("type") == "dash-db"
        ]
    
    def get_dashboard_panels(self, dashboard_uid: str) -> List[Dict[str, Any]]:
        """Fetch panels from a specific dashboard"""
        url = f"{self.base_url}/api/dashboards/uid/{dashboard_uid}"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        dashboard = response.json()
        dashboard_data = dashboard.get("dashboard", {})
        
        # Extract panels from the dashboard
        panels = []
        for panel in self._extract_panels_from_dashboard(dashboard_data):
            panels.append({
                "id": panel.get("id", 0),
                "title": panel.get("title", "Unnamed Panel"),
                "type": panel.get("type", ""),
                "description": panel.get("description", ""),
                "datasource": self._get_panel_datasource(panel)
            })
        
        return panels
    
    def _extract_panels_from_dashboard(self, dashboard_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all panels from dashboard, including those in rows and collapsed rows"""
        panels = []
        
        # Add top-level panels
        raw_panels = dashboard_data.get("panels", [])
        for panel in raw_panels:
            # Skip row type panels, as they're containers
            if panel.get("type") == "row":
                # If row has collapsed panels, extract them
                row_panels = panel.get("panels", [])
                panels.extend(row_panels)
            else:
                panels.append(panel)
                
        return panels
    
    def _get_panel_datasource(self, panel: Dict[str, Any]) -> Dict[str, Any]:
        """Extract datasource information from a panel"""
        # In newer Grafana versions, datasource is defined at the target level
        # Try to get datasource from the first target
        targets = panel.get("targets", [])
        if targets and "datasource" in targets[0]:
            ds = targets[0]["datasource"]
            if isinstance(ds, dict):
                return {
                    "uid": ds.get("uid", ""),
                    "type": ds.get("type", "")
                }
        
        # Fallback to panel-level datasource
        if "datasource" in panel:
            ds = panel["datasource"]
            if isinstance(ds, dict):
                return {
                    "uid": ds.get("uid", ""),
                    "type": ds.get("type", "")
                }
            elif isinstance(ds, str):
                return {
                    "uid": "",
                    "type": ds
                }
        
        return {"uid": "", "type": ""}
    
    def _resolve_template_vars(self, dashboard: dict, query_str: str) -> str:
        """Replace ${var} placeholders and $__all with usable values."""
        templating = dashboard.get("templating", {}).get("list", [])
        replacements = {}
        for var in templating:
            name = var.get("name")
            value = var.get("current", {}).get("value", "*")
            if value == "$__all":
                value = "*"  # expand All to wildcard
            if isinstance(value, list):
                value = " OR ".join(value) if value else "*"
            replacements[name] = value

        out = query_str
        for name, val in replacements.items():
            out = out.replace(f"${{{name}:lucene}}", val)
            out = out.replace(f"${{{name}}}", val)

        # Handle global $__all if left unexpanded
        out = out.replace("$__all", "*")

        # Remove Grafana-internal filters
        out = out.replace("${Filters:lucene}", "").replace("${Filters}", "")
        return out



    def get_panel_data(self, dashboard_uid: str, panel_id: int, time_range: Dict[str, str]) -> Dict[str, Any]:
        """Fetch data for a specific panel with the given time range (dynamic datasource resolution)."""
        try:
            # --- Get dashboard JSON ---
            dashboard_url = f"{self.base_url}/api/dashboards/uid/{dashboard_uid}"
            resp = requests.get(dashboard_url, headers=self.headers)
            resp.raise_for_status()
            dashboard_data = resp.json().get("dashboard", {})

            # --- Find the panel ---
            panel = next((p for p in self._extract_panels_from_dashboard(dashboard_data) if p.get("id") == panel_id), None)
            if not panel:
                return self._create_empty_panel_result(panel_id, "Panel not found")

            panel_type = panel.get("type", "")
            panel_targets = panel.get("targets", [])
            if not panel_targets:
                return self._create_empty_panel_result(panel_id, "No query targets", panel.get("title", ""), panel_type)

            # --- Resolve datasource dynamically ---
            ds_resp = requests.get(f"{self.base_url}/api/datasources", headers=self.headers)
            ds_resp.raise_for_status()
            datasources = ds_resp.json()

            ds = next((d for d in datasources if d["type"] == "grafana-opensearch-datasource" and d.get("isDefault")), None)
            if not ds:
                return self._create_empty_panel_result(panel_id, "No OpenSearch datasource found", panel.get("title", ""), panel_type)

            datasource_uid = ds["uid"]
            datasource_type = ds["type"]

            # --- Build queries ---
            queries = []
            for i, target in enumerate(panel_targets):
                if target.get("hide"):
                    continue
                q = {
                    "refId": target.get("refId", chr(65 + i)),
                    "datasource": {"uid": datasource_uid, "type": datasource_type},
                    "datasourceId": ds["id"],
                    "intervalMs": 60000,
                    "maxDataPoints": 500,
                    "panelId": panel_id,
                }
                for key in ["alias", "bucketAggs", "metrics", "timeField", "format", "queryType", "luceneQueryType", "query"]:
                    if key in target:
                        q[key] = target[key]

                # Resolve template variables in query string
                if "query" in q:
                    q["query"] = self._resolve_template_vars(dashboard_data, q["query"])

                # Normalize bucketAggs numeric settings
                for agg in q.get("bucketAggs", []):
                    if "settings" in agg:
                        for k, v in agg["settings"].items():
                            if isinstance(v, str) and v.isdigit():
                                agg["settings"][k] = int(v)

                queries.append(q)

            if not queries:
                return self._create_empty_panel_result(panel_id, "No valid queries", panel.get("title", ""), panel_type)

            # --- Time range ---
            from_time = time_range.get("from", "now-24h")
            to_time = time_range.get("to", "now")

            def to_ms(val: str) -> str:
                if val.startswith("now"):
                    return val
                try:
                    dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    return str(int(dt.timestamp() * 1000))
                except Exception:
                    return val

            payload = {
                "from": to_ms(from_time),
                "to": to_ms(to_time),
                "queries": queries,
                "requestId": f"Q{panel_id}"
            }

            self.logger.info(f"[QUERY PAYLOAD] {json.dumps(payload, indent=2)}")

            query_url = f"{self.base_url}/api/ds/query"
            q_resp = requests.post(query_url, headers=self.headers, json=payload)
            q_resp.raise_for_status()
            query_data = q_resp.json()

            result = self._process_panel_data(panel, query_data)
            result["panel"] = {
                "id": panel_id,
                "title": panel.get("title", ""),
                "type": panel_type,
                "description": panel.get("description", ""),
            }
            return result

        except Exception as e:
            self.logger.error(f"[ERROR] get_panel_data: {e}", exc_info=True)
            return self._create_empty_panel_result(panel_id, f"Error: {e}")

            
    def _create_empty_panel_result(self, panel_id: int, error_message: str, title: str = "Unknown Panel", panel_type: str = "unknown", description: str = "") -> Dict[str, Any]:
        """Create an empty panel result with error message"""
        return {
            "fields": ["Error"],
            "rows": [[error_message]],
            "panel": {
                "id": panel_id,
                "title": title,
                "type": panel_type,
                "description": description,
                "error": error_message
            }
        }
    
    def _create_panel_result_for_text(self, panel: Dict[str, Any]) -> Dict[str, Any]:
        """Create a result for text-type panels"""
        panel_id = panel.get("id", 0)
        panel_title = panel.get("title", "Text Panel")
        panel_type = panel.get("type", "text")
        description = panel.get("description", "")
        content = panel.get("content", panel.get("options", {}).get("content", "No content"))
        
        return {
            "fields": ["Content"],
            "rows": [[content]],
            "panel": {
                "id": panel_id,
                "title": panel_title,
                "type": panel_type,
                "description": description
            }
        }
    
    def _process_panel_data(self, panel: dict, query_data: dict) -> dict:
        """
        Normalize Grafana /api/ds/query result into {fields, rows}.
        Handles stat, table, timeseries, pie, etc. by inspecting frames schema.
        """
        panel_type = panel.get("type", "unknown")
        panel_title = panel.get("title", "Unnamed Panel")
        self.logger.debug(f"[PROCESS] Panel '{panel_title}' type={panel_type}")

        result = {"fields": [], "rows": []}

        def fmt_ts(val):
            """Format ms timestamp → human readable string, else return unchanged."""
            if isinstance(val, (int, float)) and val > 10**12:  # heuristically ms epoch
                try:
                    return datetime.fromtimestamp(val / 1000).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    return val
            return val

        try:
            frames = query_data.get("results", {}).get("A", {}).get("frames", [])
            if not frames:
                self.logger.warning(f"[PROCESS] No frames for panel {panel_title}")
                return result

            for frame in frames:
                schema = frame.get("schema", {})
                fields = schema.get("fields", [])
                values = frame.get("data", {}).get("values", [])

                # Collect field names
                field_names = [f.get("name", f"f{i}") for i, f in enumerate(fields)]
                if not result["fields"]:
                    result["fields"] = field_names

                # Transpose values → rows
                if values and all(isinstance(v, list) for v in values):
                    for row in zip(*values):
                        result["rows"].append([fmt_ts(v) for v in row])

            # --- STAT PANELS ---
            if panel_type == "stat":
                frame = frames[0]
                fields = frame.get("schema", {}).get("fields", [])
                values = frame.get("data", {}).get("values", [])

                # Case: terms aggregation with "Count" column
                field_names = [f.get("name") for f in fields]
                if "Count" in field_names:
                    count_idx = field_names.index("Count")
                    count_values = values[count_idx]
                    total = sum(v for v in count_values if isinstance(v, (int, float)))
                    return {
                        "fields": ["TOTAL"],
                        "rows": [[total]],
                        "summary": f"Sum of Count column = {total}"
                    }

                # Case: date_histogram
                if fields and len(fields) == 2:
                    x_field, y_field = fields
                    x_vals, y_vals = values
                    if x_field["name"] == "Time" and y_field["name"] in ("Value", "Count"):
                        metric = y_field.get("config", {}).get("displayNameFromDS", "").lower()
                        if metric.startswith("count"):
                            total = sum(v for v in y_vals if isinstance(v, (int, float)))
                            return {
                                "fields": ["TOTAL"],
                                "rows": [[total]],
                                "summary": f"Event count across time buckets = {total}"
                            }

                # Final fallback: sum all numeric values
                nums = []
                for col in values:
                    nums.extend(v for v in col if isinstance(v, (int, float)))
                total = sum(nums) if nums else 0
                return {
                    "fields": ["TOTAL"],
                    "rows": [[total]],
                    "summary": f"Total={total}"
                }

            # --- TABLE PANELS ---
            elif panel_type == "table":
                result["summary"] = f"{len(result['rows'])} rows"

            # --- TIMESERIES PANELS ---
            elif panel_type == "timeseries":
                result["summary"] = f"{len(result['rows'])} points"

            # Other types
            else:
                result["summary"] = f"{len(result['rows'])} rows (generic parse)"

        except Exception as e:
            self.logger.error(f"[PROCESS ERROR] {panel_title}: {e}", exc_info=True)
            result = {"error": str(e)}

        return result

    def _format_timestamp(self, timestamp):
        """Format a timestamp for display"""
        try:
            # If it's a Unix timestamp in milliseconds
            if isinstance(timestamp, (int, float)) or (isinstance(timestamp, str) and timestamp.isdigit()):
                ts = float(timestamp)
                # Check if it's in milliseconds
                if ts > 1e10:  # Timestamp is likely in milliseconds
                    ts = ts / 1000.0
                return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            # If it's an ISO string
            elif isinstance(timestamp, str) and "T" in timestamp:
                return timestamp.replace("T", " ").split(".")[0]
            # Return as is if we can't parse it
            return timestamp
        except Exception:
            return timestamp

