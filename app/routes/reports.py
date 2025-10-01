# app/routes/reports.py
from fastapi import APIRouter, Request, Depends, Form, File, UploadFile, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
import os
import uuid
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.services.grafana_api import GrafanaService
from app.services.report_service import ReportService
from app.config import settings

router = APIRouter(prefix="/reports", tags=["reports"])

# Initialize templates
templates = Jinja2Templates(directory="app/templates")

# Initialize services
grafana_service = GrafanaService()
report_service = ReportService()

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
        datasources = grafana_service.get_datasources()
        return {"datasources": datasources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/indices", response_class=JSONResponse)
async def get_indices(datasource_id: str):
    """Get available indices for a datasource"""
    try:
        indices = grafana_service.get_indices(datasource_id)
        return {"indices": indices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fields", response_class=JSONResponse)
async def get_fields(datasource_id: str, index: str):
    """Get available fields for an index"""
    try:
        fields = grafana_service.get_fields(datasource_id, index)
        return {"fields": fields}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-logo", response_class=JSONResponse)
async def upload_logo(file: UploadFile = File(...)):
    """Upload a logo for the report"""
    try:
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
            
        return {"filename": filename, "path": f"/static/uploads/{filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate", response_class=FileResponse)
async def generate_report(
    datasource_id: str = Form(...),
    index: str = Form(...),
    fields: List[str] = Form(...),
    filters: str = Form("{}"),  # JSON string of filters
    report_format: str = Form("csv"),  # 'csv' or 'xlsx'
    report_title: str = Form(settings.DEFAULT_REPORT_TITLE),
    logo_path: Optional[str] = Form(None)
):
    """Generate and download a report based on the wizard inputs"""
    try:
        # Parse filters
        filter_dict = json.loads(filters)
        
        # Get data from grafana
        data = grafana_service.get_data(datasource_id, index, fields, filter_dict)
        
        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_title.replace(' ', '_')}_{timestamp}"
        
        # Generate report file
        if report_format.lower() == "xlsx":
            file_path = report_service.generate_xlsx(
                data, 
                filename, 
                fields, 
                report_title, 
                logo_path
            )
        else:  # Default to CSV
            file_path = report_service.generate_csv(
                data, 
                filename, 
                fields
            )
        
        # Return file for download
        return FileResponse(
            path=file_path, 
            filename=os.path.basename(file_path),
            media_type="application/octet-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# New API endpoints for Grafana dashboards and panels
@router.get("/dashboards", response_class=JSONResponse)
async def get_dashboards():
    """Get available Grafana dashboards"""
    try:
        dashboards = grafana_service.get_dashboards()
        return {"dashboards": dashboards}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/panels", response_class=JSONResponse)
async def get_dashboard_panels(dashboard_uid: str):
    """Get panels for a specific dashboard"""
    try:
        panels = grafana_service.get_dashboard_panels(dashboard_uid)
        return {"panels": panels}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-from-panels", response_class=FileResponse)
async def generate_report_from_panels(
    dashboard_uid: str = Form(...),  # For backward compatibility
    panel_ids: str = Form(...),      # For backward compatibility
    dashboards: Optional[str] = Form(None),  # New parameter for multi-dashboard support
    time_range: str = Form(...),  # JSON string with from and to fields
    report_title: str = Form(settings.DEFAULT_REPORT_TITLE),
    company_name: Optional[str] = Form(None),
    logo_path: Optional[str] = Form(None)
):
    """Generate and download a report from selected Grafana panels across multiple dashboards"""
    try:
        # Parse time range
        time_range_dict = json.loads(time_range)
        
        if not isinstance(time_range_dict, dict) or "from" not in time_range_dict or "to" not in time_range_dict:
            raise HTTPException(
                status_code=400,
                detail="time_range must be a JSON object with 'from' and 'to' fields"
            )
        
        panels_data = []
        
        # Check if we have the new multi-dashboard format
        if dashboards:
            try:
                dashboard_list = json.loads(dashboards)
                if not isinstance(dashboard_list, list):
                    dashboard_list = []
            except:
                dashboard_list = []
        else:
            dashboard_list = []
            
        # If we don't have the new format, use the old format for backward compatibility
        if not dashboard_list:
            # Parse panel IDs from the old format
            try:
                panel_id_list = json.loads(panel_ids)
                if not isinstance(panel_id_list, list) or not panel_id_list:
                    raise HTTPException(
                        status_code=400,
                        detail="panel_ids must be a non-empty array of panel IDs"
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
            
        # Process each dashboard and its panels
        for dashboard_data in dashboard_list:
            dashboard_uid = dashboard_data.get("uid")
            panel_id_list = dashboard_data.get("panels", [])
            
            if not dashboard_uid or not panel_id_list:
                continue  # Skip this dashboard if it has no uid or panels
                
            # Fetch data for each panel in this dashboard
            for panel_id in panel_id_list:
                try:
                    panel_data = grafana_service.get_panel_data(
                        dashboard_uid, 
                        int(panel_id),  # Ensure panel_id is an integer
                        time_range_dict
                    )
                    panels_data.append(panel_data)
                except Exception as panel_error:
                    # Log the error
                    print(f"Error fetching panel {panel_id} from dashboard {dashboard_uid}: {str(panel_error)}")
                    # Add an error panel to the report
                    error_panel = {
                        "fields": ["Error"],
                        "rows": [[f"Failed to fetch data: {str(panel_error)}"]],
                        "panel": {
                            "id": panel_id,
                            "title": f"Panel {panel_id} (Error)",
                            "type": "unknown",
                            "description": "Error fetching panel data"
                        }
                    }
                    panels_data.append(error_panel)
        
        # Check if we have any panels with data
        if not panels_data:
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch data for any of the selected panels"
            )
        
        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_title.replace(' ', '_')}_{timestamp}"
        
        # Generate the XLSX report with multiple sheets
        file_path = report_service.generate_xlsx_from_panels(
            panels_data,
            filename,
            report_title,
            time_range_dict,
            logo_path,
            company_name
        )
        
        # Return file for download
        return FileResponse(
            path=file_path,
            filename=os.path.basename(file_path),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        # Log the full error details
        import traceback
        print(f"Error generating report: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/panel-data", response_class=JSONResponse)
async def get_panel_data(dashboard_uid: str, panel_id: int, from_time: str = "now-24h", to_time: str = "now"):
    """Get data for a specific panel"""
    try:
        # Create time range
        time_range = {
            "from": from_time,
            "to": to_time
        }
        
        # Fetch panel data
        panel_data = grafana_service.get_panel_data(dashboard_uid, panel_id, time_range)
        
        # Return panel data
        return {
            "panel_info": panel_data.get("panel", {}),
            "fields": panel_data.get("fields", []),
            "rows": panel_data.get("rows", []),
            "row_count": len(panel_data.get("rows", [])),
            "time_range": time_range
        }
    except Exception as e:
        # Log the full error details
        import traceback
        print(f"Error getting panel data: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

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
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard-panels", response_class=JSONResponse)
async def get_dashboard_panels_list(dashboard_uid: str):
    """Get a list of all panels in a dashboard for dropdown"""
    try:
        panels = grafana_service.get_dashboard_panels(dashboard_uid)
        return {"panels": panels}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))