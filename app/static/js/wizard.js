/**
 * Security Report Wizard
 * 
 * Enhanced version with Grafana dashboard panel selection supporting multiple dashboards.
 */
function wizardApp() {
    return {
        // Current step in the wizard
        currentStep: 1,
        // Track highest accessed step for navigation control
        highestStep: 1,
        
        // Loading states for various operations
        loading: {
            dashboards: false,
            panels: {}, // Object of dashboard UID -> boolean loading state
            logo: false,
            generate: false,
        },
        
        // Global data stores
        dashboards: [],
        
        // Template management
        showSaveTemplateDialog: false,
        templateName: '',
        templateToSaveIndex: null,
        savedTemplates: [],
        
        // Record of previously generated reports
        previousReports: [],
        
        // Form data that will be submitted for report generation
        formData: {
            selectedDashboards: [],
            selectedPanels: {}, // Object of dashboard UID -> array of panel IDs
            format: 'xlsx',
            reportTitle: 'Security Report',
            reportSubtitle: '',
            companyName: '',
            logoPath: null,
            logoFilename: null,
            timeRange: {
                from: 'now-24h',
                to: 'now'
            },
            // Quick selections for time range
            quickRanges: [
                { label: 'Last 24 hours', from: 'now-24h', to: 'now' },
                { label: 'Last 7 days', from: 'now-7d', to: 'now' },
                { label: 'Last 30 days', from: 'now-30d', to: 'now' },
                { label: 'This month', from: 'now/M', to: 'now/M' },
                { label: 'Last month', from: 'now-1M/M', to: 'now-1M/M' },
                { label: 'This year', from: 'now/Y', to: 'now/Y' },
                { label: 'Custom', from: '', to: '' }
            ],
            selectedQuickRange: 0, // Default to 'Last 24 hours'
            customTimeRange: {
                from: '',
                to: ''
            },
            useCustomTimeRange: false
        },

        // Available panels for each dashboard
        dashboardPanels: {}, // Object of dashboard UID -> array of panels
        
        /**
         * Initialize the application
         */
        init() {
            console.log("Initializing wizard app");
            // Load dashboards on page load
            this.loadDashboards();
            
            // Try to restore form data from localStorage
            this.restoreFormData();
            
            // Try to restore saved templates
            this.restoreSavedTemplates();
            
            // Set initial step from URL if present
            const urlParams = new URLSearchParams(window.location.search);
            const step = urlParams.get('step');
            if (step && parseInt(step) >= 1 && parseInt(step) <= 5) {
                this.currentStep = parseInt(step);
                this.highestStep = Math.max(this.highestStep, this.currentStep);
            }
            
            // Initialize date inputs for custom time range
            const now = new Date();
            const yesterday = new Date(now);
            yesterday.setDate(yesterday.getDate() - 1);
            
            this.formData.customTimeRange.from = this.formatDateForInput(yesterday);
            this.formData.customTimeRange.to = this.formatDateForInput(now);
        },
        
        /**
         * Format a Date object for datetime-local input
         */
        formatDateForInput(date) {
            // Format as YYYY-MM-DDThh:mm
            return date.toISOString().slice(0, 16);
        },
        
        /**
         * Update the time range based on the selected quick range
         */
        updateTimeRange() {
            if (this.formData.selectedQuickRange < this.formData.quickRanges.length - 1) {
                // Use a predefined time range
                this.formData.useCustomTimeRange = false;
                const quickRange = this.formData.quickRanges[this.formData.selectedQuickRange];
                this.formData.timeRange.from = quickRange.from;
                this.formData.timeRange.to = quickRange.to;
            } else {
                // Use custom time range
                this.formData.useCustomTimeRange = true;
                // Convert datetime-local inputs to ISO strings
                if (this.formData.customTimeRange.from && this.formData.customTimeRange.to) {
                    this.formData.timeRange.from = new Date(this.formData.customTimeRange.from).toISOString();
                    this.formData.timeRange.to = new Date(this.formData.customTimeRange.to).toISOString();
                }
            }
            
            this.saveFormData();
        },
        
        /**
         * Save form data to localStorage for persistence
         */
        saveFormData() {
            localStorage.setItem('reportWizardData', JSON.stringify(this.formData));
        },
        
        /**
         * Restore form data from localStorage if available
         */
        restoreFormData() {
            const savedData = localStorage.getItem('reportWizardData');
            if (savedData) {
                try {
                    const parsedData = JSON.parse(savedData);
                    
                    // Handle backward compatibility
                    if (parsedData.selectedDashboard && !parsedData.selectedDashboards) {
                        parsedData.selectedDashboards = [parsedData.selectedDashboard];
                        delete parsedData.selectedDashboard;
                    }
                    
                    if (Array.isArray(parsedData.selectedPanels)) {
                        // Convert old format to new format
                        const oldPanels = parsedData.selectedPanels;
                        parsedData.selectedPanels = {};
                        
                        if (parsedData.selectedDashboards && parsedData.selectedDashboards.length === 1) {
                            parsedData.selectedPanels[parsedData.selectedDashboards[0]] = oldPanels;
                        }
                    }
                    
                    // Update formData
                    this.formData = { ...this.formData, ...parsedData };
                    
                    // Load panels for each selected dashboard
                    if (this.formData.selectedDashboards && this.formData.selectedDashboards.length) {
                        this.formData.selectedDashboards.forEach(uid => {
                            this.loadPanelsForDashboard(uid);
                        });
                    }
                    
                } catch (e) {
                    console.error('Failed to parse saved form data', e);
                    localStorage.removeItem('reportWizardData');
                }
            }
        },
        
        /**
         * Save templates to localStorage
         */
        saveSavedTemplates() {
            localStorage.setItem('reportWizardTemplates', JSON.stringify(this.savedTemplates));
        },
        
        /**
         * Restore saved templates from localStorage if available
         */
        restoreSavedTemplates() {
            const savedTemplates = localStorage.getItem('reportWizardTemplates');
            if (savedTemplates) {
                try {
                    this.savedTemplates = JSON.parse(savedTemplates);
                } catch (e) {
                    console.error('Failed to parse saved templates', e);
                    localStorage.removeItem('reportWizardTemplates');
                }
            }
        },
        
        /**
         * Move to the next step in the wizard
         */
        nextStep() {
            if (!this.canAdvance()) {
                return;
            }
            
            if (this.currentStep < 5) {
                this.currentStep++;
                this.highestStep = Math.max(this.highestStep, this.currentStep);
                
                // Update URL
                history.pushState({}, '', `?step=${this.currentStep}`);
                
                // Save form data
                this.saveFormData();
            }
        },
        
        /**
         * Move to the previous step in the wizard
         */
        prevStep() {
            if (this.currentStep > 1) {
                this.currentStep--;
                
                // Update URL
                history.pushState({}, '', `?step=${this.currentStep}`);
            }
        },
        
        /**
         * Navigate directly to a specific step
         */
        goToStep(step) {
            if (step <= this.highestStep && step >= 1 && step <= 5) {
                this.currentStep = step;
                
                // Update URL
                history.pushState({}, '', `?step=${this.currentStep}`);
            }
        },
        
        /**
         * Check if user can advance to the next step
         */
        canAdvance() {
            switch (this.currentStep) {
                case 1:
                    // Need at least one dashboard with at least one panel
                    return this.formData.selectedDashboards.length > 0 && this.getTotalSelectedPanelCount() > 0;
                case 2:
                case 3:
                case 4:
                    // These steps are optional/informational
                    return true;
                default:
                    return true;
            }
        },
        
        /**
         * Check if we have all required data to generate a report
         */
        isReadyToGenerate() {
            return this.formData.selectedDashboards.length > 0 && 
                   this.getTotalSelectedPanelCount() > 0 && 
                   this.formData.reportTitle;
        },
        
        /**
         * Load available dashboards from the API
         */
        async loadDashboards() {
            this.loading.dashboards = true;
            
            try {
                const response = await fetch('/reports/dashboards');
                if (!response.ok) {
                    throw new Error(`HTTP error ${response.status}`);
                }
                
                const data = await response.json();
                this.dashboards = data.dashboards;
                
            } catch (error) {
                console.error('Failed to load dashboards:', error);
                alert('Failed to load Grafana dashboards. Please check your connection to Grafana and try again.');
            } finally {
                this.loading.dashboards = false;
            }
        },
        
        /**
         * Called when a dashboard checkbox is changed
         */
        handleDashboardSelection(dashboardUid, isSelected) {
            console.log(`Dashboard ${dashboardUid} selected: ${isSelected}`);
            
            if (isSelected) {
                // Dashboard was selected, load its panels
                this.loadPanelsForDashboard(dashboardUid);
            } else {
                // Dashboard was deselected, remove its panels from selection
                delete this.formData.selectedPanels[dashboardUid];
                // Also remove the panels data to clean up
                delete this.dashboardPanels[dashboardUid];
            }
            
            this.saveFormData();
        },
        
        /**
         * Load available panels for a selected dashboard
         */
        async loadPanelsForDashboard(dashboardUid) {
            if (!dashboardUid) return;
            
            console.log(`Loading panels for dashboard: ${dashboardUid}`);
            
            // Set loading state for this specific dashboard
            this.loading.panels[dashboardUid] = true;
            
            // Initialize selected panels array for this dashboard if it doesn't exist
            if (!this.formData.selectedPanels[dashboardUid]) {
                this.formData.selectedPanels[dashboardUid] = [];
            }
            
            try {
                const response = await fetch(`/reports/panels?dashboard_uid=${dashboardUid}`);
                if (!response.ok) {
                    throw new Error(`HTTP error ${response.status}`);
                }
                
                const data = await response.json();
                console.log(`Loaded ${data.panels ? data.panels.length : 0} panels for dashboard ${dashboardUid}`);
                
                // Store the panels for this dashboard
                this.dashboardPanels[dashboardUid] = data.panels || [];
                
            } catch (error) {
                console.error('Failed to load panels for dashboard:', dashboardUid, error);
                alert('Failed to load dashboard panels. Please try selecting a different dashboard.');
                
                // Set empty panels array to avoid undefined errors
                this.dashboardPanels[dashboardUid] = [];
            } finally {
                this.loading.panels[dashboardUid] = false;
            }
            
            this.saveFormData();
        },
        
        /**
         * Toggle panel selection for a specific dashboard
         */
        togglePanelSelection(dashboardUid, panelId) {
            if (!this.formData.selectedPanels[dashboardUid]) {
                this.formData.selectedPanels[dashboardUid] = [];
            }
            
            const index = this.formData.selectedPanels[dashboardUid].indexOf(panelId);
            if (index === -1) {
                this.formData.selectedPanels[dashboardUid].push(panelId);
            } else {
                this.formData.selectedPanels[dashboardUid].splice(index, 1);
            }
            
            this.saveFormData();
        },
        
        /**
         * Check if a panel is selected for a specific dashboard
         */
        isPanelSelected(dashboardUid, panelId) {
            return this.formData.selectedPanels[dashboardUid] && 
                   this.formData.selectedPanels[dashboardUid].includes(panelId);
        },
        
        /**
         * Select all panels for a specific dashboard
         */
        selectAllPanels(dashboardUid) {
            if (!this.dashboardPanels[dashboardUid]) return;
            
            this.formData.selectedPanels[dashboardUid] = this.dashboardPanels[dashboardUid].map(panel => panel.id);
            this.saveFormData();
        },
        
        /**
         * Deselect all panels for a specific dashboard
         */
        deselectAllPanels(dashboardUid) {
            this.formData.selectedPanels[dashboardUid] = [];
            this.saveFormData();
        },
        
        /**
         * Get the dashboard title from its UID
         */
        getDashboardTitle(uid) {
            const dashboard = this.dashboards.find(d => d.uid === uid);
            return dashboard ? dashboard.title : 'Unknown Dashboard';
        },
        
        /**
         * Get the panel title from its ID for a specific dashboard
         */
        getPanelTitle(dashboardUid, panelId) {
            if (!this.dashboardPanels[dashboardUid]) return null;
            
            const panel = this.dashboardPanels[dashboardUid].find(p => p.id === panelId);
            return panel ? panel.title : null;
        },
        
        /**
         * Get the count of selected panels for a specific dashboard
         */
        getSelectedPanelCount(dashboardUid) {
            return this.formData.selectedPanels[dashboardUid]?.length || 0;
        },
        
        /**
         * Get the total count of selected panels across all dashboards
         */
        getTotalSelectedPanelCount() {
            let count = 0;
            for (const dashUid in this.formData.selectedPanels) {
                count += this.formData.selectedPanels[dashUid]?.length || 0;
            }
            return count;
        },
        
        /**
         * Get the count of panels by type for a specific dashboard
         */
        getPanelTypeCount(dashboardUid, type) {
            if (!this.formData.selectedPanels[dashboardUid] || !this.dashboardPanels[dashboardUid]) return 0;
            
            return this.formData.selectedPanels[dashboardUid].filter(
                panelId => {
                    const panel = this.dashboardPanels[dashboardUid].find(p => p.id === panelId);
                    return panel && panel.type === type;
                }
            ).length;
        },
        
        /**
         * Get panel count by type for display for a specific dashboard
         */
        getSelectedPanelsInfo(dashboardUid) {
            if (!this.dashboardPanels[dashboardUid] || !this.formData.selectedPanels[dashboardUid]) {
                return '';
            }
            
            const typeCounts = {};
            
            this.formData.selectedPanels[dashboardUid].forEach(panelId => {
                const panel = this.dashboardPanels[dashboardUid].find(p => p.id === panelId);
                if (panel) {
                    const type = panel.type || 'unknown';
                    typeCounts[type] = (typeCounts[type] || 0) + 1;
                }
            });
            
            // Convert to array of strings
            return Object.entries(typeCounts).map(
                ([type, count]) => `${count} ${type}${count > 1 ? 's' : ''}`
            ).join(', ');
        },
        
        /**
         * Get total panel count by type across all dashboards
         */
        getAllSelectedPanelsInfo() {
            const typeCounts = {};
            
            for (const dashUid in this.formData.selectedPanels) {
                if (!this.dashboardPanels[dashUid]) continue;
                
                this.formData.selectedPanels[dashUid].forEach(panelId => {
                    const panel = this.dashboardPanels[dashUid].find(p => p.id === panelId);
                    if (panel) {
                        const type = panel.type || 'unknown';
                        typeCounts[type] = (typeCounts[type] || 0) + 1;
                    }
                });
            }
            
            // Convert to array of strings
            return Object.entries(typeCounts).map(
                ([type, count]) => `${count} ${type}${count > 1 ? 's' : ''}`
            ).join(', ');
        },
        
        /**
         * Upload a logo file for the report
         */
        async uploadLogo(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            // Check file type
            const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml'];
            if (!allowedTypes.includes(file.type)) {
                alert('Please select a valid image file (PNG, JPG, or SVG).');
                return;
            }
            
            // Check file size (max 10MB)
            if (file.size > 10 * 1024 * 1024) {
                alert('File size exceeds the 10MB limit.');
                return;
            }
            
            this.loading.logo = true;
            
            try {
                const formData = new FormData();
                formData.append('file', file);
                
                const response = await fetch('/reports/upload-logo', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error ${response.status}`);
                }
                
                const data = await response.json();
                this.formData.logoPath = data.path;
                this.formData.logoFilename = data.filename;
                
                this.saveFormData();
                
            } catch (error) {
                console.error('Failed to upload logo:', error);
                alert('Failed to upload logo. Please try again with a different file.');
            } finally {
                this.loading.logo = false;
                // Reset the file input
                event.target.value = '';
            }
        },
        
        /**
         * Remove the uploaded logo
         */
        removeLogo() {
            this.formData.logoPath = null;
            this.formData.logoFilename = null;
            this.saveFormData();
        },
        
        /**
         * Generate and download the report
         */
        async generateReport() {
            if (!this.isReadyToGenerate() || this.loading.generate) {
                return;
            }
            
            // Update time range before generating report
            this.updateTimeRange();
            
            this.loading.generate = true;
            
            try {
                // Prepare form data for submission
                const formData = new FormData();
                
                // Prepare the dashboard and panel selection data
                const dashboardsData = [];
                for (const dashUid of this.formData.selectedDashboards) {
                    if (this.formData.selectedPanels[dashUid] && this.formData.selectedPanels[dashUid].length > 0) {
                        dashboardsData.push({
                            uid: dashUid,
                            panels: this.formData.selectedPanels[dashUid]
                        });
                    }
                }
                
                formData.append('dashboards', JSON.stringify(dashboardsData));
                
                // For backward compatibility
                if (dashboardsData.length > 0) {
                    formData.append('dashboard_uid', dashboardsData[0].uid);
                    formData.append('panel_ids', JSON.stringify(dashboardsData[0].panels));
                }
                
                formData.append('time_range', JSON.stringify(this.formData.timeRange));
                formData.append('report_title', this.formData.reportTitle);
                
                if (this.formData.companyName) {
                    formData.append('company_name', this.formData.companyName);
                }
                
                if (this.formData.logoPath) {
                    formData.append('logo_path', this.formData.logoPath);
                }
                
                // Submit the form to generate the report
                const response = await fetch('/reports/generate-from-panels', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error ${response.status}`);
                }
                
                // Get the filename from the Content-Disposition header if available
                let filename = 'security_report.xlsx';
                const contentDisposition = response.headers.get('Content-Disposition');
                if (contentDisposition) {
                    const filenameMatch = contentDisposition.match(/filename="?([^"]*)"?/);
                    if (filenameMatch && filenameMatch[1]) {
                        filename = filenameMatch[1];
                    }
                }
                
                // Convert response to blob and download
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                
                // Add to previous reports
                const now = new Date();
                this.previousReports.unshift({
                    title: this.formData.reportTitle || 'Security Report',
                    format: 'xlsx',
                    date: now.toLocaleDateString() + ' ' + now.toLocaleTimeString(),
                    dashboardCount: this.formData.selectedDashboards.length,
                    panels: this.getTotalSelectedPanelCount()
                });
                
                // Keep only the last 5 reports
                if (this.previousReports.length > 5) {
                    this.previousReports = this.previousReports.slice(0, 5);
                }
                
                // Show success message
                alert('Report generated successfully!');
                
            } catch (error) {
                console.error('Failed to generate report:', error);
                alert('Failed to generate report. Please check your selections and try again.');
            } finally {
                this.loading.generate = false;
            }
        },
        
        /**
         * Format a datetime string for display
         */
        formatDateTime(dateTimeString) {
            if (!dateTimeString) return '';
            
            try {
                const date = new Date(dateTimeString);
                return date.toLocaleString();
            } catch (e) {
                return dateTimeString;
            }
        },
        
        /**
         * Get a human-readable name for a step
         */
        getStepName(step) {
            switch (step) {
                case 1: return 'Select Panels';
                case 2: return 'Time Range';
                case 3: return 'Settings';
                case 4: return 'Preview';
                case 5: return 'Generate';
                default: return `Step ${step}`;
            }
        },
        
        /**
         * Save the current configuration as a template
         */
        saveTemplate() {
            if (!this.templateName.trim()) {
                alert('Please enter a name for your template.');
                return;
            }
            
            // Create template object
            const template = {
                name: this.templateName,
                dashboards: this.formData.selectedDashboards,
                panels: this.formData.selectedPanels,
                timeRange: this.formData.timeRange,
                created: new Date().toISOString()
            };
            
            // Add to saved templates
            this.savedTemplates.push(template);
            
            // Save to local storage
            this.saveSavedTemplates();
            
            // Close dialog
            this.showSaveTemplateDialog = false;
            this.templateName = '';
            
            // Show confirmation
            alert('Template saved successfully!');
        }
    };
}