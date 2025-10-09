# app/routes/reports.py - FIXED VERSION WITH ERROR HANDLING
from fastapi import APIRouter, Request, Depends, Form, File, UploadFile, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
import os
import uuid
import json
import traceback
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.services.grafana_api import GrafanaService
from app.services.report_service import ReportService
from app.config import settings

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])

# Initialize templates
templates = Jinja2Templates(directory="app/templates")

# Initialize services
grafana_service = GrafanaService()
report_service = ReportService(reports_dir=settings.REPORTS_DIR)

# Helper functions
def get_session_data(request: Request):
    """Get wizard session data from cookies"""
    session_data = request.cookies.get("wizard_data", "{}")
    try:
        return json.loads(session_data)
    except:
        return {}

# Wizard step routes
@router.get("/wizard/{step}", response_class=HTMLResponse)
async def wizard_step(request: Request, step: int):
    """Render the wizard step template"""
    if step < 1 or step > 6:
        raise HTTPException(status_code=404, detail="Step not found")
    
    return templates.TemplateResponse(
        "report_wizard.html", 
        {"request": request, "step": step, "data": get_session_data(request)}
    )

# API routes for wizard steps
@router.get("/datasources", response_class=JSONResponse)
async def get_datasources():
    """Get available data sources"""
    try:
        logger.info("Fetching datasources...")
        datasources = grafana_service.get_datasources()
        logger.info(f"Found {len(datasources)} datasources")
        return {"datasources": datasources}
    except Exception as e:
        logger.error(f"Error getting datasources: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get datasources: {str(e)}")

@router.get("/indices", response_class=JSONResponse)
async def get_indices(datasource_id: str):
    """Get available indices for a datasource"""
    try:
        logger.info(f"Fetching indices for datasource: {datasource_id}")
        indices = grafana_service.get_indices(datasource_id)
        logger.info(f"Found {len(indices)} indices")
        return {"indices": indices}
    except Exception as e:
        logger.error(f"Error getting indices: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get indices: {str(e)}")

@router.get("/fields", response_class=JSONResponse)
async def get_fields(datasource_id: str, index: str):
    """Get available fields for an index"""
    try:
        logger.info(f"Fetching fields for datasource {datasource_id}, index {index}")
        fields = grafana_service.get_fields(datasource_id, index)
        logger.info(f"Found {len(fields)} fields")
        return {"fields": fields}
    except Exception as e:
        logger.error(f"Error getting fields: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get fields: {str(e)}")

@router.post("/upload-logo", response_class=JSONResponse)
async def upload_logo(file: UploadFile = File(...)):
    """Upload a logo for the report"""
    try:
        logger.info(f"Uploading logo: {file.filename}")
        # Validate file extension
        file_ext = file.filename.split(".")[-1].lower()
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"File extension not allowed. Allowed extensions: {settings.ALLOWED_EXTENSIONS}"
            )
        
        # Create unique filename
        filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join(settings.UPLOAD_FOLDER, filename)
        
        # Save file
        with open(file_path, "wb") as f:
            contents = await file.read()
            f.write(contents)
        
        logger.info(f"Logo uploaded successfully: {filename}")
        return {"filename": filename, "path": f"/static/uploads/{filename}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading logo: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to upload logo: {str(e)}")

# New API endpoints for Grafana dashboards and panels
@router.get("/dashboards", response_class=JSONResponse)
async def get_dashboards():
    """Get available Grafana dashboards"""
    try:
        logger.info("=" * 80)
        logger.info("FETCHING DASHBOARDS")
        logger.info(f"Grafana URL: {settings.GRAFANA_URL}")
        logger.info(f"API Key configured: {bool(settings.GRAFANA_API_KEY)}")
        logger.info("=" * 80)
        
        dashboards = grafana_service.get_dashboards()
        
        logger.info(f"Successfully fetched {len(dashboards)} dashboards")
        for dash in dashboards[:5]:  # Log first 5
            logger.info(f"  - {dash.get('title')} (UID: {dash.get('uid')})")
        
        return {"dashboards": dashboards}
        
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error to Grafana: {e}")
        logger.error(f"Check if Grafana is running at {settings.GRAFANA_URL}")
        raise HTTPException(
            status_code=500, 
            detail=f"Cannot connect to Grafana at {settings.GRAFANA_URL}. Is Grafana running?"
        )
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error from Grafana: {e}")
        logger.error(f"Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
        if e.response.status_code == 401:
            raise HTTPException(
                status_code=500,
                detail="Grafana API authentication failed. Check your GRAFANA_API_KEY in .env file"
            )
        raise HTTPException(
            status_code=500,
            detail=f"Grafana API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error getting dashboards: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get dashboards: {str(e)}"
        )

@router.get("/panels", response_class=JSONResponse)
async def get_dashboard_panels(dashboard_uid: str):
    """Get panels for a specific dashboard"""
    try:
        logger.info("=" * 80)
        logger.info(f"FETCHING PANELS FOR DASHBOARD: {dashboard_uid}")
        logger.info("=" * 80)
        
        panels = grafana_service.get_dashboard_panels(dashboard_uid)
        
        logger.info(f"Successfully fetched {len(panels)} panels")
        for panel in panels[:5]:  # Log first 5
            logger.info(f"  - Panel {panel.get('id')}: {panel.get('title')} (type: {panel.get('type')})")
        
        return {"panels": panels}
        
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error to Grafana: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Cannot connect to Grafana. Check if it's running at {settings.GRAFANA_URL}"
        )
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error from Grafana: {e}")
        logger.error(f"Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get panels from Grafana: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error getting panels: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get panels: {str(e)}"
        )

@router.post("/generate-from-panels", response_class=FileResponse)
async def generate_report_from_panels(
    dashboard_uid: str = Form(...),
    panel_ids: str = Form(...),
    dashboards: Optional[str] = Form(None),
    time_range: str = Form(...),
    report_title: str = Form(settings.DEFAULT_REPORT_TITLE),
    company_name: Optional[str] = Form(None),
    logo_path: Optional[str] = Form(None)
):
    """Generate and download a report from selected Grafana panels"""
    try:
        logger.info("=" * 80)
        logger.info("GENERATING REPORT")
        logger.info("=" * 80)
        
        # Parse time range
        time_range_dict = json.loads(time_range)
        logger.info(f"Time range: {time_range_dict}")
        
        if not isinstance(time_range_dict, dict) or "from" not in time_range_dict or "to" not in time_range_dict:
            raise HTTPException(
                status_code=400,
                detail="time_range must be a JSON object with 'from' and 'to' fields"
            )
        
        panels_data = []
        
        # Parse dashboard selections
        if dashboards:
            try:
                dashboard_list = json.loads(dashboards)
                if not isinstance(dashboard_list, list):
                    dashboard_list = []
            except:
                dashboard_list = []
        else:
            dashboard_list = []
        
        # Fallback to old format
        if not dashboard_list:
            try:
                panel_id_list = json.loads(panel_ids)
                if not isinstance(panel_id_list, list) or not panel_id_list:
                    raise HTTPException(
                        status_code=400,
                        detail="panel_ids must be a non-empty array"
                    )
            except:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid panel_ids format"
                )
            
            dashboard_list = [{
                "uid": dashboard_uid,
                "panels": panel_id_list
            }]
        
        logger.info(f"Processing {len(dashboard_list)} dashboard(s)")
        
        # Fetch panel data
        for dashboard_data in dashboard_list:
            dash_uid = dashboard_data.get("uid")
            panel_id_list = dashboard_data.get("panels", [])
            
            logger.info(f"Dashboard {dash_uid}: {len(panel_id_list)} panels")
            
            if not dash_uid or not panel_id_list:
                continue
            
            for panel_id in panel_id_list:
                try:
                    logger.info(f"  Fetching panel {panel_id}...")
                    panel_data = grafana_service.get_panel_data(
                        dash_uid,
                        int(panel_id),
                        time_range_dict
                    )
                    
                    # Check if we got data
                    rows_count = len(panel_data.get('rows', []))
                    logger.info(f"  Panel {panel_id}: {rows_count} rows")
                    
                    if rows_count == 0:
                        logger.warning(f"  ⚠️  Panel {panel_id} returned no data!")
                    
                    panels_data.append(panel_data)
                    
                except Exception as panel_error:
                    logger.error(f"  ❌ Error fetching panel {panel_id}: {panel_error}")
                    logger.error(traceback.format_exc())
                    # Add error panel
                    error_panel = {
                        "fields": ["Error"],
                        "rows": [[f"Failed to fetch data: {str(panel_error)}"]],
                        "panel": {
                            "id": panel_id,
                            "title": f"Panel {panel_id} (Error)",
                            "type": "unknown",
                            "description": str(panel_error)
                        }
                    }
                    panels_data.append(error_panel)
        
        if not panels_data:
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch data for any panels"
            )
        
        # Check total rows
        total_rows = sum(len(pd.get('rows', [])) for pd in panels_data)
        logger.info(f"Total data rows across all panels: {total_rows}")
        
        if total_rows == 0:
            logger.warning("⚠️  NO DATA IN ANY PANELS!")
        
        # Generate report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_title.replace(' ', '_')}_{timestamp}"
        
        logger.info(f"Generating Excel file: {filename}")
        
        file_path = report_service.generate_xlsx_from_panels(
            panels_data,
            filename,
            report_title,
            time_range_dict,
            logo_path,
            company_name
        )
        
        logger.info(f"✅ Report generated: {file_path}")
        logger.info(f"File size: {os.path.getsize(file_path)} bytes")
        
        return FileResponse(
            path=file_path,
            filename=os.path.basename(file_path),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to generate report: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@router.get("/panel-data", response_class=JSONResponse)
async def get_panel_data(dashboard_uid: str, panel_id: int, from_time: str = "now-24h", to_time: str = "now"):
    """Get data for a specific panel"""
    try:
        logger.info(f"Fetching data for panel {panel_id} in dashboard {dashboard_uid}")
        
        time_range = {
            "from": from_time,
            "to": to_time
        }
        
        panel_data = grafana_service.get_panel_data(dashboard_uid, panel_id, time_range)
        
        logger.info(f"Panel data: {len(panel_data.get('rows', []))} rows")
        
        return {
            "panel_info": panel_data.get("panel", {}),
            "fields": panel_data.get("fields", []),
            "rows": panel_data.get("rows", []),
            "row_count": len(panel_data.get("rows", [])),
            "time_range": time_range
        }
    except Exception as e:
        logger.error(f"Error getting panel data: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get panel data: {str(e)}")

@router.get("/panel-test", response_class=HTMLResponse)
async def panel_test(request: Request):
    """Render the panel test page"""
    return templates.TemplateResponse(
        "panel_test.html",
        {"request": request}
    )

@router.get("/dashboards-list", response_class=JSONResponse)
async def get_dashboards_list():
    """Get a list of all available dashboards for dropdown"""
    try:
        dashboards = grafana_service.get_dashboards()
        return {"dashboards": dashboards}
    except Exception as e:
        logger.error(f"Error getting dashboards list: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard-panels", response_class=JSONResponse)
async def get_dashboard_panels_list(dashboard_uid: str):
    """Get a list of all panels in a dashboard for dropdown"""
    try:
        panels = grafana_service.get_dashboard_panels(dashboard_uid)
        return {"panels": panels}
    except Exception as e:
        logger.error(f"Error getting dashboard panels: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))