/**
 * ICD-10 Diagnosis Management JavaScript
 * 
 * Provides functionality for:
 * - ICD-10 code search and selection
 * - Diagnosis management (add, edit, delete)
 * - Template application
 * - Analytics display
 */

class ICD10DiagnosisManager {
    constructor(patientId = null) {
        this.patientId = patientId;
        this.searchTimeout = null;
        this.selectedCodes = [];
        this.templates = [];
        
        this.init();
    }
    
    init() {
        this.loadTemplates();
        this.bindEvents();
        
        if (this.patientId) {
            this.loadPatientDiagnoses();
        }
    }
    
    bindEvents() {
        // Search functionality
        const searchInput = document.getElementById('icd10-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                clearTimeout(this.searchTimeout);
                this.searchTimeout = setTimeout(() => {
                    this.searchCodes(e.target.value);
                }, 300);
            });
        }
        
        // Category filter
        const categorySelect = document.getElementById('icd10-category-filter');
        if (categorySelect) {
            categorySelect.addEventListener('change', (e) => {
                const searchTerm = document.getElementById('icd10-search')?.value || '';
                this.searchCodes(searchTerm, e.target.value);
            });
        }
        
        // Template selection
        const templateSelect = document.getElementById('diagnosis-template-select');
        if (templateSelect) {
            templateSelect.addEventListener('change', (e) => {
                if (e.target.value) {
                    this.showTemplatePreview(e.target.value);
                }
            });
        }
        
        // Form submissions
        const diagnosisForm = document.getElementById('add-diagnosis-form');
        if (diagnosisForm) {
            diagnosisForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.addDiagnosis();
            });
        }
    }
    
    async searchCodes(query, category = '') {
        if (query.length < 2) {
            this.clearSearchResults();
            return;
        }
        
        try {
            const params = new URLSearchParams({
                q: query,
                limit: 20
            });
            
            if (category) {
                params.append('category', category);
            }
            
            const response = await fetch(`/api/icd10/search?${params}`);
            const data = await response.json();
            
            this.displaySearchResults(data.codes);
        } catch (error) {
            console.error('Error searching ICD-10 codes:', error);
            this.showError('Error searching codes. Please try again.');
        }
    }
    
    displaySearchResults(codes) {
        const resultsContainer = document.getElementById('icd10-search-results');
        if (!resultsContainer) return;
        
        if (codes.length === 0) {
            resultsContainer.innerHTML = '<div class="text-muted p-3">No codes found matching your search.</div>';
            return;
        }
        
        let html = '<div class="list-group">';
        
        codes.forEach(code => {
            html += `
                <div class="list-group-item list-group-item-action icd10-code-item" 
                     data-code-id="${code.id}" 
                     data-code="${code.code}"
                     data-description="${code.short_description}">
                    <div class="d-flex w-100 justify-content-between">
                        <div>
                            <h6 class="mb-1">
                                <span class="badge bg-primary me-2">${code.code}</span>
                                ${code.short_description}
                            </h6>
                            <p class="mb-1 text-muted small">${code.description}</p>
                            <small class="text-muted">
                                <i class="bi bi-tag"></i> ${code.category} → ${code.subcategory}
                            </small>
                        </div>
                        <button class="btn btn-sm btn-outline-primary select-code-btn" 
                                data-code-id="${code.id}">
                            <i class="bi bi-plus-circle"></i> Select
                        </button>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        resultsContainer.innerHTML = html;
        
        // Bind selection events
        resultsContainer.querySelectorAll('.select-code-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const codeId = e.target.dataset.codeId;
                const codeItem = e.target.closest('.icd10-code-item');
                this.selectCode({
                    id: codeId,
                    code: codeItem.dataset.code,
                    description: codeItem.dataset.description
                });
            });
        });
    }
    
    selectCode(codeData) {
        // Update form fields
        const codeIdInput = document.getElementById('selected-icd10-code-id');
        const codeDisplay = document.getElementById('selected-icd10-display');
        
        if (codeIdInput) {
            codeIdInput.value = codeData.id;
        }
        
        if (codeDisplay) {
            codeDisplay.innerHTML = `
                <div class="alert alert-info">
                    <strong>Selected:</strong> 
                    <span class="badge bg-primary me-2">${codeData.code}</span>
                    ${codeData.description}
                    <button type="button" class="btn-close float-end" onclick="icd10Manager.clearSelection()"></button>
                </div>
            `;
        }
        
        // Clear search results
        this.clearSearchResults();
        
        // Enable form submission
        const submitBtn = document.getElementById('add-diagnosis-btn');
        if (submitBtn) {
            submitBtn.disabled = false;
        }
    }
    
    clearSelection() {
        const codeIdInput = document.getElementById('selected-icd10-code-id');
        const codeDisplay = document.getElementById('selected-icd10-display');
        const submitBtn = document.getElementById('add-diagnosis-btn');
        
        if (codeIdInput) codeIdInput.value = '';
        if (codeDisplay) codeDisplay.innerHTML = '';
        if (submitBtn) submitBtn.disabled = true;
    }
    
    clearSearchResults() {
        const resultsContainer = document.getElementById('icd10-search-results');
        if (resultsContainer) {
            resultsContainer.innerHTML = '';
        }
    }
    
    async loadTemplates() {
        try {
            const response = await fetch('/api/icd10/templates');
            const data = await response.json();
            this.templates = data.templates;
            this.displayTemplates();
        } catch (error) {
            console.error('Error loading templates:', error);
        }
    }
    
    displayTemplates() {
        const templateSelect = document.getElementById('diagnosis-template-select');
        if (!templateSelect) return;
        
        let html = '<option value="">Choose a common diagnosis template...</option>';
        
        this.templates.forEach(template => {
            html += `
                <option value="${template.id}" 
                        data-code="${template.icd10_code}"
                        data-description="${template.icd10_description}"
                        data-severity="${template.default_severity}">
                    ${template.name} (${template.icd10_code})
                </option>
            `;
        });
        
        templateSelect.innerHTML = html;
    }
    
    showTemplatePreview(templateId) {
        const template = this.templates.find(t => t.id == templateId);
        if (!template) return;
        
        const previewContainer = document.getElementById('template-preview');
        if (!previewContainer) return;
        
        previewContainer.innerHTML = `
            <div class="card border-info">
                <div class="card-header bg-info text-white">
                    <h6 class="mb-0">
                        <i class="bi bi-clipboard-check"></i> Template Preview: ${template.name}
                    </h6>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <strong>ICD-10 Code:</strong> 
                            <span class="badge bg-primary">${template.icd10_code}</span>
                        </div>
                        <div class="col-md-6">
                            <strong>Default Severity:</strong> 
                            <span class="badge bg-secondary">${template.default_severity}</span>
                        </div>
                    </div>
                    <div class="mt-2">
                        <strong>Description:</strong> ${template.icd10_description}
                    </div>
                    ${template.description ? `<div class="mt-2"><strong>Notes:</strong> ${template.description}</div>` : ''}
                    ${template.typical_duration_days ? `<div class="mt-2"><strong>Typical Duration:</strong> ${template.typical_duration_days} days</div>` : ''}
                    
                    <div class="mt-3">
                        <button type="button" class="btn btn-info" onclick="icd10Manager.applyTemplate(${template.id})">
                            <i class="bi bi-check-circle"></i> Apply This Template
                        </button>
                        <button type="button" class="btn btn-outline-secondary ms-2" onclick="icd10Manager.clearTemplatePreview()">
                            Cancel
                        </button>
                    </div>
                </div>
            </div>
        `;
    }
    
    async applyTemplate(templateId) {
        if (!this.patientId) {
            this.showError('Patient ID is required to apply template');
            return;
        }
        
        try {
            const onsetDate = document.getElementById('template-onset-date')?.value;
            const clinicalNotes = document.getElementById('template-clinical-notes')?.value;
            
            const response = await fetch(`/api/template/${templateId}/apply/${this.patientId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    onset_date: onsetDate,
                    clinical_notes: clinicalNotes
                })
            });
            
            console.log('🔍 Template response status:', response.status);
            console.log('🔍 Template response headers:', response.headers.get('content-type'));
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('❌ Template application failed:', response.status, 'Response:', errorText);
                this.showError(`Failed to apply template (${response.status}). Check console for details.`);
                return;
            }
            
            // Check if response is actually JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const text = await response.text();
                console.error('❌ Non-JSON response received:', text);
                this.showError(`Server error: Expected JSON but got ${contentType}. Check browser console for details.`);
                return;
            }
            
            const data = await response.json();
            console.log('✅ Template result:', data);
            
            if (data.success) {
                this.showSuccess(data.message);
                this.loadPatientDiagnoses();
                this.clearTemplatePreview();
                
                // Close modal if open
                const modal = bootstrap.Modal.getInstance(document.getElementById('add-diagnosis-modal'));
                if (modal) modal.hide();
            } else {
                this.showError(data.error || 'Failed to apply template');
            }
        } catch (error) {
            console.error('Error applying template:', error);
            this.showError('Error applying template. Please try again.');
        }
    }
    
    clearTemplatePreview() {
        const previewContainer = document.getElementById('template-preview');
        if (previewContainer) {
            previewContainer.innerHTML = '';
        }
        
        const templateSelect = document.getElementById('diagnosis-template-select');
        if (templateSelect) {
            templateSelect.value = '';
        }
    }
    
    async addDiagnosis() {
        if (!this.patientId) {
            this.showError('Patient ID is required');
            return;
        }
        
        const form = document.getElementById('add-diagnosis-form');
        const editId = form.getAttribute('data-edit-id');
        const isEdit = !!editId;
        
        const formData = new FormData(form);
        const data = {
            icd10_code_id: formData.get('icd10_code_id'),
            diagnosis_type: formData.get('diagnosis_type') || 'primary',
            severity: formData.get('severity') || 'moderate',
            confidence_level: formData.get('confidence_level') || 'confirmed',
            clinical_notes: formData.get('clinical_notes') || '',
            onset_date: formData.get('onset_date'),
            diagnosis_date: formData.get('diagnosis_date') || new Date().toISOString().split('T')[0]
        };
        
        if (!data.icd10_code_id) {
            this.showError('Please select an ICD-10 code');
            return;
        }
        
        try {
            // Get CSRF token
            const csrfToken = document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || 
                             document.querySelector('input[name=csrf_token]')?.value;
            
            const headers = {
                'Content-Type': 'application/json',
            };
            
            // Add CSRF token if available
            if (csrfToken) {
                headers['X-CSRFToken'] = csrfToken;
            }
            
            // Determine URL and method based on edit mode
            const url = isEdit 
                ? `/api/patient/${this.patientId}/diagnoses/${editId}`
                : `/api/patient/${this.patientId}/diagnoses`;
            const method = isEdit ? 'PUT' : 'POST';
            
            const response = await fetch(url, {
                method: method,
                headers: headers,
                body: JSON.stringify(data)
            });
            
            console.log('Response status:', response.status);
            console.log('Response headers:', response.headers);
            
            // Check if response is actually JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const text = await response.text();
                console.error('Non-JSON response received:', text);
                this.showError(`Server error: Expected JSON but got ${contentType}. Check browser console for details.`);
                return;
            }
            
            const result = await response.json();
            console.log('Parsed result:', result);
            
            if (result.success) {
                this.showSuccess(result.message || (isEdit ? 'Diagnosis updated successfully' : 'Diagnosis added successfully'));
                this.loadPatientDiagnoses();
                this.resetForm();
                
                // Close modal if open
                const modal = bootstrap.Modal.getInstance(document.getElementById('add-diagnosis-modal'));
                if (modal) modal.hide();
            } else {
                this.showError(result.error || (isEdit ? 'Failed to update diagnosis' : 'Failed to add diagnosis'));
            }
        } catch (error) {
            console.error('Error adding diagnosis:', error);
            this.showError('Error adding diagnosis. Please try again.');
        }
    }
    
    async loadPatientDiagnoses() {
        if (!this.patientId) return;
        
        try {
            console.log('🔍 Loading patient diagnoses for patient ID:', this.patientId);
            const response = await fetch(`/api/patient/${this.patientId}/diagnoses`);
            const data = await response.json();
            
            console.log('📡 API Response:', data);
            console.log('📋 Diagnoses array:', data.diagnoses);
            
            this.displayPatientDiagnoses(data.diagnoses);
        } catch (error) {
            console.error('Error loading patient diagnoses:', error);
        }
    }
    
    displayPatientDiagnoses(diagnoses) {
        const container = document.getElementById('patient-diagnoses-list');
        if (!container) return;
        
        console.log('🔍 Displaying patient diagnoses:', diagnoses);
        
        // Debug: Log each diagnosis and its pathology guide status
        diagnoses.forEach((diagnosis, index) => {
            console.log(`📋 Diagnosis ${index + 1}:`, {
                description: diagnosis.description,
                has_pathology_guide: diagnosis.has_pathology_guide,
                template_name: diagnosis.template_name,
                type_of_has_pathology_guide: typeof diagnosis.has_pathology_guide
            });
        });
        
        if (diagnoses.length === 0) {
            container.innerHTML = `
                <div class="text-center py-4">
                    <i class="bi bi-clipboard-x text-muted" style="font-size: 2rem;"></i>
                    <p class="text-muted mt-2">No ICD-10 diagnoses recorded yet.</p>
                    <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#add-diagnosis-modal">
                        <i class="bi bi-plus-circle"></i> Add First Diagnosis
                    </button>
                </div>
            `;
            return;
        }
        
        let html = '';
        
        // Ensure container allows dropdowns to overflow
        container.style.overflow = 'visible';
        
        diagnoses.forEach(diagnosis => {
            
            const statusBadge = this.getStatusBadge(diagnosis.status);
            const typeBadge = this.getTypeBadge(diagnosis.diagnosis_type);
            const severityBadge = this.getSeverityBadge(diagnosis.severity);
            
            html += `
                <div class="card mb-3 diagnosis-card" data-diagnosis-id="${diagnosis.id}" style="overflow: visible; position: relative;">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start">
                            <div class="flex-grow-1">
                                <h6 class="card-title">
                                    <span class="badge bg-primary me-2">${diagnosis.icd10_code}</span>
                                    ${diagnosis.description}
                                    ${typeBadge}
                                </h6>
                                <p class="card-text text-muted small mb-2">${diagnosis.full_description}</p>
                                
                                <div class="row g-2 mb-2">
                                    <div class="col-auto">
                                        <small class="text-muted">Status:</small> ${statusBadge}
                                    </div>
                                    <div class="col-auto">
                                        <small class="text-muted">Severity:</small> ${severityBadge}
                                    </div>
                                    ${diagnosis.onset_date ? `
                                    <div class="col-auto">
                                        <small class="text-muted">Onset:</small> 
                                        <span class="badge bg-light text-dark">${new Date(diagnosis.onset_date).toLocaleDateString()}</span>
                                    </div>
                                    ` : ''}
                                    ${diagnosis.duration_days ? `
                                    <div class="col-auto">
                                        <small class="text-muted">Duration:</small> 
                                        <span class="badge bg-light text-dark">${diagnosis.duration_days} days</span>
                                    </div>
                                    ` : ''}
                                </div>
                                
                                ${diagnosis.clinical_notes ? `
                                <div class="mt-2">
                                    <small class="text-muted">Clinical Notes:</small>
                                    <p class="small mb-0">${diagnosis.clinical_notes}</p>
                                </div>
                                ` : ''}
                            </div>
                            
                            <div class="d-flex gap-2">
                                <!-- Info Button (if pathology guide exists) -->
                                <button class="btn btn-sm btn-outline-info" 
                                        onclick="showPathologyGuide('${diagnosis.template_name || diagnosis.description}')"
                                        title="Clinical Pathway Guide"
                                        style="display: ${diagnosis.has_pathology_guide === true ? 'inline-block' : 'none'};">
                                    <i class="bi bi-info-circle"></i> Info
                                </button>
                                
                                <div class="dropdown">
                                    <button class="btn btn-sm btn-outline-secondary dropdown-toggle" 
                                            type="button" data-bs-toggle="dropdown" aria-expanded="false">
                                        <i class="bi bi-three-dots-vertical"></i>
                                    </button>
                                    <ul class="dropdown-menu dropdown-menu-end">
                                        <li><a class="dropdown-item" href="#" onclick="icd10Manager.editDiagnosis(${diagnosis.id})">
                                            <i class="bi bi-pencil"></i> Edit
                                        </a></li>
                                        ${diagnosis.status === 'active' ? `
                                        <li><a class="dropdown-item" href="#" onclick="icd10Manager.resolveDiagnosis(${diagnosis.id})">
                                            <i class="bi bi-check-circle"></i> Mark Resolved
                                        </a></li>
                                        ` : ''}
                                        <li><hr class="dropdown-divider"></li>
                                        <li><a class="dropdown-item" href="#" onclick="showPathologyGuide('${diagnosis.template_name || diagnosis.description}')">
                                            <i class="bi bi-info-circle"></i> Clinical Guide
                                        </a></li>
                                        <li><hr class="dropdown-divider"></li>
                                        <li><a class="dropdown-item text-danger" href="#" onclick="icd10Manager.deleteDiagnosis(${diagnosis.id})">
                                            <i class="bi bi-trash"></i> Delete
                                        </a></li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    }
    
    getStatusBadge(status) {
        const badges = {
            'active': '<span class="badge bg-success">Active</span>',
            'resolved': '<span class="badge bg-secondary">Resolved</span>',
            'chronic': '<span class="badge bg-warning">Chronic</span>',
            'ruled_out': '<span class="badge bg-danger">Ruled Out</span>'
        };
        return badges[status] || `<span class="badge bg-light text-dark">${status}</span>`;
    }
    
    getTypeBadge(type) {
        const badges = {
            'primary': '<span class="badge bg-primary ms-1">Primary</span>',
            'secondary': '<span class="badge bg-info ms-1">Secondary</span>',
            'differential': '<span class="badge bg-warning ms-1">Differential</span>'
        };
        return badges[type] || '';
    }
    
    getSeverityBadge(severity) {
        const badges = {
            'mild': '<span class="badge bg-success">Mild</span>',
            'moderate': '<span class="badge bg-warning">Moderate</span>',
            'severe': '<span class="badge bg-danger">Severe</span>'
        };
        return badges[severity] || `<span class="badge bg-light text-dark">${severity}</span>`;
    }
    
    async resolveDiagnosis(diagnosisId) {
        if (!confirm('Mark this diagnosis as resolved?')) return;
        
        try {
            const response = await fetch(`/api/patient/${this.patientId}/diagnoses/${diagnosisId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    status: 'resolved'
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess('Diagnosis marked as resolved');
                this.loadPatientDiagnoses();
            } else {
                this.showError(result.error || 'Failed to update diagnosis');
            }
        } catch (error) {
            console.error('Error updating diagnosis:', error);
            this.showError('Error updating diagnosis. Please try again.');
        }
    }
    
    async editDiagnosis(diagnosisId) {
        try {
            // Fetch the diagnosis details
            const response = await fetch(`/api/patient/${this.patientId}/diagnoses/${diagnosisId}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const diagnosis = await response.json();
            
            // Populate the edit form with current diagnosis data
            this.populateEditForm(diagnosis);
            
            // Show the modal
            const modal = new bootstrap.Modal(document.getElementById('add-diagnosis-modal'));
            modal.show();
            
            // Change the form to edit mode
            const form = document.getElementById('add-diagnosis-form');
            form.setAttribute('data-edit-id', diagnosisId);
            
            // Update modal title and button text
            const modalTitle = document.getElementById('add-diagnosis-modal-label');
            if (modalTitle) modalTitle.textContent = 'Edit Diagnosis';
            
            const submitBtn = document.querySelector('#add-diagnosis-modal .btn-primary');
            if (submitBtn) submitBtn.textContent = 'Update Diagnosis';
            
        } catch (error) {
            console.error('Error loading diagnosis for edit:', error);
            this.showError('Failed to load diagnosis details for editing.');
        }
    }
    
    populateEditForm(diagnosis) {
        // Populate form fields with diagnosis data
        const fields = {
            'icd10-search': diagnosis.description,
            'diagnosis-type': diagnosis.diagnosis_type,
            'status': diagnosis.status,
            'severity': diagnosis.severity,
            'confidence-level': diagnosis.confidence_level,
            'onset-date': diagnosis.onset_date,
            'diagnosis-date': diagnosis.diagnosis_date,
            'clinical-notes': diagnosis.clinical_notes
        };
        
        for (const [fieldId, value] of Object.entries(fields)) {
            const field = document.getElementById(fieldId);
            if (field && value !== null && value !== undefined) {
                field.value = value;
            }
        }
        
        // Store the ICD-10 code info for submission
        this.selectedICD10 = {
            id: diagnosis.icd10_code_id || null,
            code: diagnosis.icd10_code,
            description: diagnosis.description
        };
        
        // Update the search results display
        this.displaySearchResults([{
            id: diagnosis.icd10_code_id,
            code: diagnosis.icd10_code,
            short_description: diagnosis.description,
            description: diagnosis.full_description || diagnosis.description
        }]);
    }
    
    async deleteDiagnosis(diagnosisId) {
        if (!confirm('Are you sure you want to delete this diagnosis? This action cannot be undone.')) return;
        
        try {
            console.log('🗑️ Deleting diagnosis:', diagnosisId);
            const response = await fetch(`/api/patient/${this.patientId}/diagnoses/${diagnosisId}`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.getCSRFToken(),
                    'Content-Type': 'application/json'
                }
            });
            
            console.log('🔍 Delete response status:', response.status);
            console.log('🔍 Delete response headers:', response.headers.get('content-type'));
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('❌ Delete failed with status:', response.status, 'Response:', errorText);
                this.showError(`Failed to delete diagnosis (${response.status}). Check console for details.`);
                return;
            }
            
            // Check if response is actually JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const text = await response.text();
                console.error('❌ Non-JSON response received:', text);
                this.showError(`Server error: Expected JSON but got ${contentType}. Check browser console for details.`);
                return;
            }
            
            const result = await response.json();
            console.log('✅ Delete result:', result);
            
            if (result.success) {
                this.showSuccess('Diagnosis deleted successfully');
                this.loadPatientDiagnoses();
            } else {
                this.showError(result.error || 'Failed to delete diagnosis');
            }
        } catch (error) {
            console.error('❌ Error deleting diagnosis:', error);
            this.showError('Error deleting diagnosis. Please try again.');
        }
    }
    
    resetForm() {
        const form = document.getElementById('add-diagnosis-form');
        if (form) {
            form.reset();
            form.removeAttribute('data-edit-id'); // Clear edit mode
        }
        
        // Reset modal title and button text to add mode
        const modalTitle = document.getElementById('add-diagnosis-modal-label');
        if (modalTitle) modalTitle.textContent = 'Add New Diagnosis';
        
        const submitBtn = document.querySelector('#add-diagnosis-modal .btn-primary');
        if (submitBtn) submitBtn.textContent = 'Add Diagnosis';
        
        this.clearSelection();
        this.clearTemplatePreview();
    }
    
    showSuccess(message) {
        this.showAlert(message, 'success');
    }
    
    showError(message) {
        this.showAlert(message, 'danger');
    }
    
    showAlert(message, type) {
        // Create or update alert container
        let alertContainer = document.getElementById('icd10-alerts');
        if (!alertContainer) {
            alertContainer = document.createElement('div');
            alertContainer.id = 'icd10-alerts';
            alertContainer.className = 'position-fixed top-0 end-0 p-3';
            alertContainer.style.zIndex = '9999';
            document.body.appendChild(alertContainer);
        }
        
        const alertId = 'alert-' + Date.now();
        const alertHtml = `
            <div id="${alertId}" class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        alertContainer.insertAdjacentHTML('beforeend', alertHtml);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            const alert = document.getElementById(alertId);
            if (alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    }
}

// Initialize global instance
let icd10Manager;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Get patient ID from data attribute or global variable
    const patientId = document.body.dataset.patientId || window.patientId || null;
    icd10Manager = new ICD10DiagnosisManager(patientId);
});
