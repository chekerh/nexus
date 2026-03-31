const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const processBtn = document.getElementById('process-btn');
const statusSection = document.getElementById('status-section');
const resultsSection = document.getElementById('results-section');
const statusMessage = document.getElementById('status-message');
const transcriptContent = document.getElementById('transcript-content');
const analysisContent = document.getElementById('analysis-content');

let selectedFile = null;

// Handle File Selection
dropzone.onclick = () => fileInput.click();

fileInput.onchange = (e) => {
    selectedFile = e.target.files[0];
    if (selectedFile) {
        dropzone.innerText = `Selected: ${selectedFile.name}`;
        processBtn.disabled = false;
    }
};

// Handle Processing
processBtn.onclick = async () => {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append('file', selectedFile);

    // Reset UI
    processBtn.disabled = true;
    statusSection.classList.remove('hidden');
    resultsSection.classList.add('hidden');
    statusMessage.innerText = "Uploading and Transcribing (Whisper.cpp)...";

    try {
        const response = await fetch('/process', {
            method: 'POST',
            body: formData
        });

        const { process_id } = await response.json();
        pollStatus(process_id);
    } catch (err) {
        console.error(err);
        statusMessage.innerText = "Error uploading file.";
        processBtn.disabled = false;
    }
};

// Poll for Results
async function pollStatus(processId) {
    const poll = setInterval(async () => {
        try {
            const res = await fetch(`/status/${processId}`);
            const data = await res.json();

            if (data.status === 'completed') {
                clearInterval(poll);
                showResults(data);
            } else if (data.status === 'error') {
                clearInterval(poll);
                statusMessage.innerText = `Critical Error: ${data.error}`;
                processBtn.disabled = false;
            } else {
                // Show granular status updates from the backend
                statusMessage.innerText = data.status || "Processing...";
            }
        } catch (err) {
            clearInterval(poll);
            console.error(err);
        }
    }, 2000);
}

function showResults(data) {
    statusSection.classList.add('hidden');
    resultsSection.classList.remove('hidden');
    transcriptContent.innerText = data.transcript;
    analysisContent.innerText = data.analysis;
    processBtn.disabled = false;
}
