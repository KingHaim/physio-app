document.addEventListener('DOMContentLoaded', function() {
    const recordButton = document.getElementById('recordNoteBtn');
    const recordingStatus = document.getElementById('recordingStatus');
    const notesTextarea = document.getElementById('notes');

    // Check if necessary elements exist on the page
    if (!recordButton || !recordingStatus || !notesTextarea) {
        // console.log("Voice note elements not found on this page.");
        return; // Exit if elements aren't present (e.g., not on new/edit treatment page)
    }

    // ---- Language Selection Logic ----
    const languageSelectBtn = document.getElementById('languageSelectBtn');
    const languageDropdownItems = document.querySelectorAll('#languageDropdownMenu .lang-option');
    let currentLang = languageSelectBtn ? languageSelectBtn.dataset.currentLang : 'en-GB'; // Default

    if (languageSelectBtn && languageDropdownItems.length > 0) {
        languageDropdownItems.forEach(item => {
            item.addEventListener('click', function(e) {
                e.preventDefault();
                currentLang = this.dataset.lang;
                languageSelectBtn.dataset.currentLang = currentLang;
                // Update button text (e.g., "EN" or "ES")
                languageSelectBtn.textContent = this.textContent.split(' ')[0]; 
                console.log("Language changed to:", currentLang);
            });
        });
    } else {
        console.warn("Language selection elements not found. Defaulting to", currentLang);
    }
    // ---- End Language Selection Logic ----

    // Feature detection for Web Speech API
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.warn("Web Speech API not supported by this browser.");
        recordButton.disabled = true;
        recordButton.textContent = 'Voice Not Supported';
        return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true; // Keep listening even after pauses
    recognition.interimResults = true; // Get results while speaking

    let isRecording = false;
    let finalTranscript = '';

    recognition.onstart = () => {
        console.log("Voice recognition started.");
        recordingStatus.textContent = 'Listening...';
        recordingStatus.style.display = 'inline';
        recordButton.innerHTML = '<i class="bi bi-stop-circle-fill"></i> Stop';
        recordButton.classList.remove('btn-outline-secondary');
        recordButton.classList.add('btn-danger');
    };

    recognition.onresult = (event) => {
        let interimTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                finalTranscript += event.results[i][0].transcript + '. '; // Add punctuation
            } else {
                interimTranscript += event.results[i][0].transcript;
            }
        }
        // Update textarea with final transcript immediately for better feedback
        notesTextarea.value = notesTextarea.value.trim() + (notesTextarea.value.trim() ? ' ' : '') + finalTranscript; 
        finalTranscript = ''; // Clear final transcript after appending

        // Optionally show interim results (can be jumpy)
        // recordingStatus.textContent = `Listening... (Heard: ${interimTranscript})`; 
    };

    recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        let errorMessage = 'An error occurred.';
        if (event.error === 'no-speech') {
            errorMessage = 'No speech detected.';
        } else if (event.error === 'audio-capture') {
            errorMessage = 'Microphone problem.';
        } else if (event.error === 'not-allowed') {
            errorMessage = 'Mic permission denied.';
        } else if (event.error === 'network') {
            errorMessage = 'Network error.';
        } else if (event.error === 'aborted') {
            errorMessage = 'Recording aborted, please try again.';
        }
        recordingStatus.textContent = `Error: ${errorMessage}`;
        recordingStatus.style.color = 'red';
        stopRecording(); // Stop recording on error
    };

    recognition.onend = () => {
        console.log("Voice recognition ended.");
        if (isRecording) { // If ended unexpectedly (e.g., network error, silence timeout)
             stopRecording(); // Ensure UI is reset
             // Optionally try restarting:
             // console.log("Recognition ended unexpectedly, attempting restart...");
             // startRecording(); 
        }
    };

    function startRecording() {
        if (isRecording) return;
        console.log("Attempting to start recording in", currentLang, "...");
        
        // --- Set language BEFORE starting ---
        recognition.lang = currentLang;
        // ----------------------------------

        finalTranscript = ''; // Reset transcript
        notesTextarea.value = notesTextarea.value.trim() + ' '; // Add space before new recording
        try {
             recognition.start();
             isRecording = true;
        } catch (e) {
             console.error("Error starting recognition:", e);
              recordingStatus.textContent = 'Error starting.';
              recordingStatus.style.color = 'red';
              isRecording = false; // Ensure state is correct
        }
    }

    function stopRecording() {
        if (!isRecording) return;
        console.log("Stopping recording...");
         try {
            recognition.stop();
         } catch(e) {
             console.error("Error stopping recognition:", e);
         }
        isRecording = false;
        recordingStatus.textContent = '';
        recordingStatus.style.display = 'none';
        recordingStatus.style.color = ''; // Reset color
        recordButton.innerHTML = '<i class="bi bi-mic-fill"></i> Record';
        recordButton.classList.remove('btn-danger');
        recordButton.classList.add('btn-outline-secondary');
    }

    recordButton.addEventListener('click', () => {
        if (isRecording) {
            stopRecording();
        } else {
            // Request permission implicitly by starting
            startRecording();
        }
    });

    // Add safety net: Stop recording if the user navigates away
    window.addEventListener('beforeunload', () => {
        if (isRecording) {
            stopRecording();
        }
    });
}); 