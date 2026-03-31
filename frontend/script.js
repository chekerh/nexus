const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const processBtn = document.getElementById('process-btn');
const statusSection = document.getElementById('status-section');
const resultsSection = document.getElementById('results-section');
const statusMessage = document.getElementById('status-message');
const transcriptContent = document.getElementById('transcript-content');
const analysisContent = document.getElementById('analysis-content');

const stopBtn = document.getElementById('stop-btn');
const thinkingConsole = document.getElementById('thinking-console');
const statusTitle = document.getElementById('status-title');

let selectedFile = null;
let currentProcessId = null;

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
    thinkingConsole.innerHTML = '<div class="thinking-line">Initializing local AI engine...</div>';
    statusTitle.innerText = "AI Processing...";

    try {
        const response = await fetch('/process', {
            method: 'POST',
            body: formData
        });

        const { process_id } = await response.json();
        currentProcessId = process_id;
        pollStatus(process_id);
    } catch (err) {
        console.error(err);
        thinkingConsole.innerHTML += `<div class="thinking-line error">Error uploading file: ${err}</div>`;
        processBtn.disabled = false;
    }
};

// Handle Stop Analysis
stopBtn.onclick = async () => {
    if (!currentProcessId) return;
    try {
        await fetch(`/cancel/${currentProcessId}`, { method: 'POST' });
        statusTitle.innerText = "Stopping Analysis...";
    } catch (err) {
        console.error("Stop failed", err);
    }
};

// Poll for Results
async function pollStatus(processId) {
    const poll = setInterval(async () => {
        try {
            const res = await fetch(`/status/${processId}`);
            const data = await res.json();

            // Update Thinking Console with new thoughts
            if (data.thinking) {
                const currentThoughts = thinkingConsole.querySelectorAll('.thinking-line').length;
                if (data.thinking.length > currentThoughts) {
                    for (let i = currentThoughts; i < data.thinking.length; i++) {
                        const line = document.createElement('div');
                        line.className = 'thinking-line';
                        line.innerText = `> ${data.thinking[i]}`;
                        thinkingConsole.appendChild(line);
                        thinkingConsole.scrollTop = thinkingConsole.scrollHeight;
                    }
                }
            }

            if (data.status === 'completed') {
                clearInterval(poll);
                showResults(data);
            } else if (data.status === 'error') {
                clearInterval(poll);
                statusTitle.innerText = "Process Failed";
                thinkingConsole.innerHTML += `<div class="thinking-line error">CRITICAL ERROR: ${data.error}</div>`;
                processBtn.disabled = false;
            } else if (data.status === 'cancelled') {
                clearInterval(poll);
                statusTitle.innerText = "Analysis Cancelled";
                thinkingConsole.innerHTML += `<div class="thinking-line">Process terminated by user. Resources released.</div>`;
                processBtn.disabled = false;
            }
        } catch (err) {
            clearInterval(poll);
            console.error(err);
        }
    }, 1500);
}

const clipsContainer = document.getElementById('clips-container');

function showResults(data) {
    statusSection.classList.add('hidden');
    resultsSection.classList.remove('hidden');
    
    transcriptContent.innerText = data.transcript;
    
    // Clear previous results
    clipsContainer.innerHTML = '';

    // Format JSON Analysis
    if (data.analysis && data.analysis.hooks) {
        analysisContent.innerHTML = data.analysis.hooks.map(hook => `
            <div class="hook-item">
                <strong>${hook.hook_name}</strong> (${hook.start}s - ${hook.end}s)<br>
                <em>${hook.caption}</em>
            </div>
        `).join('<hr>');
    }

    // Render Video Clips
    if (data.clips && data.clips.length > 0) {
        clipsContainer.innerHTML = data.clips.map((clip, index) => {
            const hook = data.analysis.hooks[index] || { hook_name: `Clip ${index+1}`, caption: '' };
            const encodedClip = encodeURIComponent(clip);
            return `
                <div class="card clip-card">
                    <h4>${hook.hook_name}</h4>
                    <video controls width="100%" src="/video_clips/${encodedClip}"></video>
                    <div class="clip-info">
                        <p>${hook.caption}</p>
                        <a href="/video_clips/${encodedClip}" download class="btn btn-secondary">Download Clip</a>
                    </div>
                </div>
            `;
        }).join('');
    } else {
        clipsContainer.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--text-dim);">No clips were generated for this video.</p>';
    }

    processBtn.disabled = false;
}
