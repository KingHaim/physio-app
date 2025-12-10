/**
 * Pathology Guide Manager - Clinical Pathway Guide System
 * Handles loading and displaying rich clinical content for diagnoses
 */

class PathologyGuideManager {
    constructor() {
        this.currentGuide = null;
        this.modal = null;
        this.initializeModal();
    }

    initializeModal() {
        const modalElement = document.getElementById('pathologyGuideModal');
        if (modalElement) {
            this.modal = new bootstrap.Modal(modalElement);
        } else {
            console.error('Pathology guide modal element not found');
        }
    }

    /**
     * Load and display a pathology guide
     * @param {string} templateName - Name of the diagnosis template
     * @param {number} templateId - ID of the diagnosis template (optional)
     */
    async loadGuide(templateName, templateId = null) {
        try {
            // Ensure modal is initialized
            if (!this.modal) {
                this.initializeModal();
            }
            
            if (!this.modal) {
                throw new Error('Modal not available - pathology guide modal not found in DOM');
            }
            
            this.showLoading();
            this.modal.show();

            // Fetch guide data from API
            console.log('🔍 Fetching pathology guide:', templateName);
            const response = await fetch(`/api/pathology-guide/${encodeURIComponent(templateName)}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                credentials: 'same-origin'  // Ensure cookies are sent
            });

            console.log('📡 Pathology guide response:', response.status, response.statusText);
            console.log('📡 Response URL:', response.url);

            // Check if we were redirected to login page
            if (response.url.includes('/auth/login') || response.status === 302) {
                throw new Error('Authentication required. Please refresh the page and log in again.');
            }

            if (!response.ok) {
                const errorText = await response.text();
                console.error('❌ Pathology guide API error:', errorText);
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // Check if response is actually JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const text = await response.text();
                console.error('❌ Non-JSON response received:', text.substring(0, 200));
                throw new Error('Server returned invalid response. Please try refreshing the page.');
            }

            const guideData = await response.json();
            console.log('✅ Pathology guide loaded:', guideData.name);
            this.currentGuide = guideData;
            this.displayGuide(guideData);

        } catch (error) {
            console.error('Error loading pathology guide:', error);
            this.showError(`Failed to load guide: ${error.message}`);
        }
    }

    showLoading() {
        const loadingEl = document.getElementById('guide-loading');
        const errorEl = document.getElementById('guide-error');
        const contentEl = document.getElementById('guide-content');
        
        if (loadingEl) loadingEl.classList.remove('d-none');
        if (errorEl) errorEl.classList.add('d-none');
        if (contentEl) contentEl.classList.add('d-none');
    }

    showError(message) {
        const loadingEl = document.getElementById('guide-loading');
        const errorEl = document.getElementById('guide-error');
        const contentEl = document.getElementById('guide-content');
        const errorMessageEl = document.getElementById('guide-error-message');
        
        if (loadingEl) loadingEl.classList.add('d-none');
        if (errorEl) errorEl.classList.remove('d-none');
        if (contentEl) contentEl.classList.add('d-none');
        if (errorMessageEl) errorMessageEl.textContent = message;
    }

    displayGuide(guide) {
        document.getElementById('guide-loading').classList.add('d-none');
        document.getElementById('guide-error').classList.add('d-none');
        document.getElementById('guide-content').classList.remove('d-none');

        // Set modal title
        document.getElementById('guide-title').textContent = guide.name;

        // Overview tab
        this.populateOverview(guide);

        // Clinical pearls tab
        this.populateClinicalPearls(guide);

        // Patient education tab
        this.populatePatientEducation(guide);

        // Treatment tab
        this.populateTreatment(guide);

        // FAQ tab
        this.populateFAQ(guide);

        // Red flags tab
        this.populateRedFlags(guide);
    }

    populateOverview(guide) {
        // Description
        const descElement = document.getElementById('guide-description');
        descElement.textContent = guide.description || 'No description available.';

        // Anatomy overview
        const anatomyElement = document.getElementById('guide-anatomy');
        const anatomyCard = document.getElementById('anatomy-card');
        if (guide.anatomy_overview) {
            anatomyElement.textContent = guide.anatomy_overview;
            anatomyCard.classList.remove('d-none');
        } else {
            anatomyCard.classList.add('d-none');
        }

        // Duration
        const durationElement = document.getElementById('guide-duration');
        if (guide.typical_duration_days) {
            const weeks = Math.round(guide.typical_duration_days / 7);
            durationElement.textContent = `${weeks} weeks`;
        } else {
            durationElement.textContent = 'Variable';
        }

        // Phase count
        const phaseCountElement = document.getElementById('phase-count');
        if (guide.treatment_phases) {
            const phases = guide.treatment_phases.split(/Phase \d+:/).length - 1;
            phaseCountElement.textContent = phases > 0 ? phases : '3';
        }

        // Red flags preview
        const redFlagsPreview = document.getElementById('guide-red-flags-preview');
        if (guide.red_flags) {
            const preview = guide.red_flags.substring(0, 100) + (guide.red_flags.length > 100 ? '...' : '');
            redFlagsPreview.textContent = preview;
        } else {
            redFlagsPreview.textContent = 'See Red Flags tab for safety information.';
        }
    }

    populateClinicalPearls(guide) {
        const container = document.getElementById('guide-clinical-pearls');
        if (guide.clinical_pearls) {
            container.innerHTML = this.formatTextContent(guide.clinical_pearls);
        } else {
            container.innerHTML = '<p class="text-muted">No clinical pearls available for this condition.</p>';
        }
    }

    populatePatientEducation(guide) {
        const educationContainer = document.getElementById('guide-patient-education');
        const symptomsContainer = document.getElementById('guide-symptoms');

        // Patient education content
        if (guide.patient_education) {
            educationContainer.innerHTML = this.formatTextContent(guide.patient_education);
        } else {
            educationContainer.innerHTML = '<p class="text-muted">No patient education content available.</p>';
        }

        // Common symptoms
        if (guide.common_symptoms) {
            const symptoms = guide.common_symptoms.split(',').map(s => s.trim());
            const symptomsHTML = symptoms.map(symptom => 
                `<span class="badge bg-light text-dark me-2 mb-2">${symptom}</span>`
            ).join('');
            symptomsContainer.innerHTML = symptomsHTML;
        } else {
            symptomsContainer.innerHTML = '<p class="text-muted">No symptoms listed.</p>';
        }
    }

    populateTreatment(guide) {
        // Treatment phases
        const phasesContainer = document.getElementById('guide-treatment-phases');
        if (guide.treatment_phases) {
            phasesContainer.innerHTML = this.formatPhases(guide.treatment_phases);
        } else {
            phasesContainer.innerHTML = '<p class="text-muted">No treatment phases defined.</p>';
        }

        // Home exercises
        const exercisesContainer = document.getElementById('guide-home-exercises');
        if (guide.home_exercises) {
            exercisesContainer.innerHTML = this.formatExercises(guide.home_exercises);
        } else {
            exercisesContainer.innerHTML = '<p class="text-muted">No home exercises specified.</p>';
        }

        // Treatment guidelines
        const guidelinesContainer = document.getElementById('guide-treatment-guidelines');
        if (guide.treatment_guidelines) {
            guidelinesContainer.innerHTML = this.formatTextContent(guide.treatment_guidelines);
        } else {
            guidelinesContainer.innerHTML = '<p class="text-muted">No treatment guidelines available.</p>';
        }
    }

    populateFAQ(guide) {
        const container = document.getElementById('faqAccordion');
        
        if (guide.faq_list && guide.faq_list.length > 0) {
            const faqHTML = guide.faq_list.map((faq, index) => `
                <div class="accordion-item">
                    <h2 class="accordion-header" id="faq-heading-${index}">
                        <button class="accordion-button collapsed" type="button" 
                                data-bs-toggle="collapse" data-bs-target="#faq-collapse-${index}" 
                                aria-expanded="false" aria-controls="faq-collapse-${index}">
                            <i class="fas fa-question-circle me-2 text-primary"></i>
                            ${this.escapeHtml(faq.q)}
                        </button>
                    </h2>
                    <div id="faq-collapse-${index}" class="accordion-collapse collapse" 
                         aria-labelledby="faq-heading-${index}" data-bs-parent="#faqAccordion">
                        <div class="accordion-body">
                            <i class="fas fa-lightbulb me-2 text-warning"></i>
                            ${this.escapeHtml(faq.a)}
                        </div>
                    </div>
                </div>
            `).join('');
            
            container.innerHTML = faqHTML;
        } else {
            container.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle me-2"></i>
                    No frequently asked questions available for this condition.
                </div>
            `;
        }
    }

    populateRedFlags(guide) {
        const container = document.getElementById('guide-red-flags');
        if (guide.red_flags) {
            container.innerHTML = `
                <div class="alert alert-danger">
                    <h6><i class="fas fa-exclamation-triangle me-2"></i>When to Refer or Seek Urgent Care:</h6>
                    ${this.formatTextContent(guide.red_flags)}
                </div>
                <div class="mt-3">
                    <h6><i class="fas fa-phone me-2"></i>Emergency Contacts</h6>
                    <p class="small text-muted">
                        If any red flag symptoms are present, consider immediate referral to appropriate medical services.
                        Document findings and communicate urgency clearly.
                    </p>
                </div>
            `;
        } else {
            container.innerHTML = `
                <div class="alert alert-warning">
                    <i class="fas fa-info-circle me-2"></i>
                    No specific red flags documented for this condition. 
                    Always use clinical judgment and refer when in doubt.
                </div>
            `;
        }
    }

    formatTextContent(text) {
        if (!text) return '';
        
        // Convert line breaks to paragraphs
        const paragraphs = text.split('\n').filter(p => p.trim());
        return paragraphs.map(p => `<p>${this.escapeHtml(p.trim())}</p>`).join('');
    }

    formatPhases(text) {
        if (!text) return '';
        
        const phases = text.split(/Phase \d+:/).filter(p => p.trim());
        let phaseNumber = 1;
        
        return phases.map(phase => `
            <div class="mb-3">
                <h6 class="text-primary">
                    <i class="fas fa-play-circle me-2"></i>Phase ${phaseNumber++}
                </h6>
                <p class="mb-0">${this.escapeHtml(phase.trim())}</p>
            </div>
        `).join('');
    }

    formatExercises(text) {
        if (!text) return '';
        
        // Split by numbers (1., 2., etc.) or bullet points
        const exercises = text.split(/\d+\.|\•/).filter(e => e.trim());
        
        return `
            <ul class="list-group list-group-flush">
                ${exercises.map(exercise => `
                    <li class="list-group-item border-0 px-0">
                        <i class="fas fa-dumbbell me-2 text-success"></i>
                        ${this.escapeHtml(exercise.trim())}
                    </li>
                `).join('')}
            </ul>
        `;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    getCSRFToken() {
        return document.querySelector('meta[name=csrf-token]')?.getAttribute('content') || '';
    }
}

// Global functions for modal actions
function printGuide() {
    if (window.pathologyGuideManager && window.pathologyGuideManager.currentGuide) {
        window.print();
    }
}

function emailGuide() {
    if (window.pathologyGuideManager && window.pathologyGuideManager.currentGuide) {
        const guide = window.pathologyGuideManager.currentGuide;
        const subject = `Clinical Guide: ${guide.name}`;
        const body = `Please find attached information about ${guide.name}.\n\nThis guide was generated from your physiotherapy clinic's clinical pathway system.`;
        
        window.location.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    }
}

// Initialize the manager when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.pathologyGuideManager = new PathologyGuideManager();
});

// Function to show guide (called from info buttons)
function showPathologyGuide(templateName, templateId = null) {
    if (window.pathologyGuideManager) {
        window.pathologyGuideManager.loadGuide(templateName, templateId);
    } else {
        // Try to initialize if not ready
        console.warn('PathologyGuideManager not initialized, attempting to initialize...');
        try {
            window.pathologyGuideManager = new PathologyGuideManager();
            window.pathologyGuideManager.loadGuide(templateName, templateId);
        } catch (error) {
            console.error('Failed to initialize PathologyGuideManager:', error);
            alert('Clinical guide system not available. Please refresh the page and try again.');
        }
    }
}
