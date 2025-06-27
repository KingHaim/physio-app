// Welcome Modal with Dynamic Translation
document.addEventListener('DOMContentLoaded', function() {
    const welcomeModal = document.getElementById('welcomeModal');
    if (welcomeModal) {
        let currentStep = 1;
        const totalSteps = 5;
        let currentTranslations = null;
        
        // Show modal automatically for new users
        const modal = new bootstrap.Modal(welcomeModal);
        modal.show();
        
        const nextBtn = document.getElementById('nextBtn');
        const prevBtn = document.getElementById('prevBtn');
        const completeBtn = document.getElementById('completeBtn');
        const progressBar = document.getElementById('progressBar');
        const languageSelect = document.getElementById('language');
        
        // Language change handler
        if (languageSelect) {
            languageSelect.addEventListener('change', function() {
                const selectedLang = this.value;
                if (selectedLang && ['es', 'en', 'fr', 'it'].includes(selectedLang)) {
                    // Fetch translations for selected language
                    fetch('/api/welcome-translations/' + selectedLang)
                        .then(response => response.json())
                        .then(translations => {
                            applyTranslations(translations);
                            currentTranslations = translations;
                        })
                        .catch(error => {
                            console.error('Error loading translations:', error);
                        });
                }
            });
        }
        
        // Function to apply translations to the modal
        function applyTranslations(translations) {
            // Update step indicators
            const stepIndicators = document.querySelectorAll('.step-indicator');
            if (stepIndicators[0]) stepIndicators[0].textContent = '1. ' + translations.step_language;
            if (stepIndicators[1]) stepIndicators[1].textContent = '2. ' + translations.step_personal_info;
            if (stepIndicators[2]) stepIndicators[2].textContent = '3. ' + translations.step_work_setup;
            if (stepIndicators[3]) stepIndicators[3].textContent = '4. ' + translations.step_clinic_info;
            if (stepIndicators[4]) stepIndicators[4].textContent = '5. ' + translations.step_fees;
            
            // Update Step 1 content
            const step1Title = document.querySelector('#step1 h5');
            if (step1Title) step1Title.textContent = translations.get_to_know;
            const step1Desc = document.querySelector('#step1 p');
            if (step1Desc) step1Desc.textContent = translations.which_language;
            const selectOption = document.querySelector('#language option[value=""]');
            if (selectOption) selectOption.textContent = translations.select_language;
            
            // Update Step 2 content
            const step2Title = document.querySelector('#step2 h5');
            if (step2Title) step2Title.textContent = translations.nice_to_meet;
            const step2Desc = document.querySelector('#step2 p');
            if (step2Desc) step2Desc.textContent = translations.what_call_you;
            
            // Update Step 3 content
            const step3Title = document.querySelector('#step3 h5');
            if (step3Title) step3Title.textContent = translations.tell_about_work;
            const step3Desc = document.querySelector('#step3 p');
            if (step3Desc) step3Desc.textContent = translations.self_employed_clinic;
            
            // Update work type options
            const freelanceTitle = document.querySelector('label[for="freelance"] h6');
            if (freelanceTitle) freelanceTitle.textContent = translations.work_freelancer;
            const freelanceDesc = document.querySelector('label[for="freelance"] small');
            if (freelanceDesc) freelanceDesc.textContent = translations.work_freelancer_desc;
            
            const clinicTitle = document.querySelector('label[for="clinic_employee"] h6');
            if (clinicTitle) clinicTitle.textContent = translations.work_clinic;
            const clinicDesc = document.querySelector('label[for="clinic_employee"] small');
            if (clinicDesc) clinicDesc.textContent = translations.work_clinic_desc;
            
            const mixedTitle = document.querySelector('label[for="mixed"] h6');
            if (mixedTitle) mixedTitle.textContent = translations.work_both;
            const mixedDesc = document.querySelector('label[for="mixed"] small');
            if (mixedDesc) mixedDesc.textContent = translations.work_both_desc;
            
            // Update Step 4 content
            const step4Title = document.querySelector('#step4 h5');
            if (step4Title) step4Title.textContent = translations.about_clinic;
            const step4Desc = document.querySelector('#step4 p');
            if (step4Desc) step4Desc.textContent = translations.if_work_clinic;
            
            const perfectMsg = document.querySelector('.no-clinic-message h6');
            if (perfectMsg) perfectMsg.textContent = translations.perfect;
            const configureMsg = document.querySelector('.no-clinic-message p');
            if (configureMsg) configureMsg.textContent = translations.configure_fees_next;
            
            // Update Step 5 content
            const step5Title = document.querySelector('#step5 h5');
            if (step5Title) step5Title.textContent = translations.fee_structure;
            const step5Desc = document.querySelector('#step5 p');
            if (step5Desc) step5Desc.textContent = translations.what_charge_sessions;
            
            // Update navigation buttons
            const prevBtnText = document.querySelector('#prevBtn');
            if (prevBtnText) prevBtnText.innerHTML = '<i class="bi bi-arrow-left me-2"></i>' + translations.previous;
            const nextBtnText = document.querySelector('#nextBtn');
            if (nextBtnText) nextBtnText.innerHTML = translations.next + '<i class="bi bi-arrow-right ms-2"></i>';
            const completeBtnText = document.querySelector('#completeBtn');
            if (completeBtnText) completeBtnText.innerHTML = '<i class="bi bi-check-circle me-2"></i>' + translations.complete_setup;
        }
        
        function showStep(step) {
            // Hide all steps
            document.querySelectorAll('.step-content').forEach(content => {
                content.classList.add('d-none');
            });
            
            // Show current step
            const currentStepElement = document.getElementById('step' + step);
            if (currentStepElement) {
                currentStepElement.classList.remove('d-none');
            }
            
            // Update progress bar
            const progressPercent = (step / totalSteps) * 100;
            progressBar.style.width = progressPercent + '%';
            
            // Update step indicators
            document.querySelectorAll('.step-indicator').forEach((indicator, index) => {
                indicator.classList.remove('active', 'completed');
                if (index + 1 < step) {
                    indicator.classList.add('completed');
                } else if (index + 1 === step) {
                    indicator.classList.add('active');
                }
            });
            
            // Show/hide navigation buttons
            prevBtn.style.display = step > 1 ? 'inline-block' : 'none';
            
            if (step === totalSteps) {
                nextBtn.style.display = 'none';
                completeBtn.style.display = 'inline-block';
            } else {
                nextBtn.style.display = 'inline-block';
                completeBtn.style.display = 'none';
            }
        }
        
        function validateCurrentStep() {
            if (currentStep === 1) {
                const language = document.getElementById('language');
                if (!language || !language.value) {
                    const message = currentTranslations ? currentTranslations.please_select_language : 'Please select a language';
                    alert(message);
                    return false;
                }
            } else if (currentStep === 2) {
                const firstName = document.querySelector('input[name="first_name"]');
                if (!firstName || !firstName.value.trim()) {
                    const message = currentTranslations ? currentTranslations.please_enter_first_name : 'Please enter your first name';
                    alert(message);
                    return false;
                }
            } else if (currentStep === 3) {
                const workType = document.querySelector('input[name="work_type"]:checked');
                if (!workType) {
                    const message = currentTranslations ? currentTranslations.please_select_work : 'Please select how you work';
                    alert(message);
                    return false;
                }
            }
            return true;
        }
        
        // Next button click
        nextBtn.addEventListener('click', function() {
            if (validateCurrentStep()) {
                currentStep++;
                showStep(currentStep);
            }
        });
        
        // Previous button click
        prevBtn.addEventListener('click', function() {
            currentStep--;
            showStep(currentStep);
        });
        
        // Work type change handler
        document.querySelectorAll('input[name="work_type"]').forEach(radio => {
            radio.addEventListener('change', function() {
                const clinicFields = document.querySelector('.clinic-fields');
                const noClinicMessage = document.querySelector('.no-clinic-message');
                
                if (clinicFields && noClinicMessage) {
                    if (this.value === 'clinic_employee' || this.value === 'mixed') {
                        clinicFields.style.display = 'block';
                        noClinicMessage.style.display = 'none';
                    } else {
                        clinicFields.style.display = 'none';
                        noClinicMessage.style.display = 'block';
                    }
                }
            });
        });
        
        // Commission checkbox handler
        const paysCommissionCheckbox = document.getElementById('pays_commission');
        if (paysCommissionCheckbox) {
            paysCommissionCheckbox.addEventListener('change', function() {
                const commissionFields = document.querySelector('.commission-fields');
                if (commissionFields) {
                    commissionFields.style.display = this.checked ? 'block' : 'none';
                }
            });
        }
    }
});
