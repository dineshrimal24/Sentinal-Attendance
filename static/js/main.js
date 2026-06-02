/* ==========================================================================
   Global Functions & Clock
   ========================================================================== */
document.addEventListener("DOMContentLoaded", function() {
    // 1. Start live digital clock
    const clockEl = document.getElementById("live-time");
    if (clockEl) {
        setInterval(() => {
            const now = new Date();
            clockEl.textContent = now.toLocaleTimeString();
        }, 1000);
    }
});

/**
 * Displays a premium custom toast notification alert.
 * @param {string} type - 'success', 'error', 'warning', 'info'
 * @param {string} message - Text message to show
 * @param {number} duration - Delay in ms before alert disappears
 */
function showAlert(type, message, duration = 4000) {
    const container = document.getElementById("alert-container");
    if (!container) return;
    
    const alert = document.createElement("div");
    alert.className = `custom-alert alert-${type}`;
    
    let icon = "fa-circle-info";
    if (type === "success") icon = "fa-circle-check";
    else if (type === "error") icon = "fa-circle-exclamation";
    else if (type === "warning") icon = "fa-triangle-exclamation";
    
    alert.innerHTML = `
        <i class="fa-solid ${icon} alert-icon"></i>
        <div class="alert-message">${message}</div>
        <button class="alert-close"><i class="fa-solid fa-xmark"></i></button>
    `;
    
    container.appendChild(alert);
    
    // Auto dismiss
    const dismissTimeout = setTimeout(() => {
        dismissAlert(alert);
    }, duration);
    
    // Manual dismiss
    alert.querySelector(".alert-close").addEventListener("click", () => {
        clearTimeout(dismissTimeout);
        dismissAlert(alert);
    });
}

function dismissAlert(alertEl) {
    alertEl.classList.add("fade-out");
    alertEl.addEventListener("transitionend", () => {
        alertEl.remove();
    });
}

/**
 * Synthesizes a futuristic notification beep using the browser's Web Audio API.
 * Prevents needing external audio files.
 */
function playSuccessBeep() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        
        // Single tone
        const osc = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        
        osc.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        
        osc.type = "sine";
        osc.frequency.setValueAtTime(880, audioCtx.currentTime); // High pitch (A5)
        
        // Volume envelope (prevent clicking at startup and fade out smoothly)
        gainNode.gain.setValueAtTime(0, audioCtx.currentTime);
        gainNode.gain.linearRampToValueAtTime(0.25, audioCtx.currentTime + 0.01);
        gainNode.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.2);
        
        osc.start(audioCtx.currentTime);
        osc.stop(audioCtx.currentTime + 0.2);
    } catch (e) {
        console.error("Synthesizer beep failed:", e);
    }
}

/* ==========================================================================
   User Registration & Enrollment (HTML5 Webcam & Dropzone)
   ========================================================================== */
let captureStream = null;

function initEnrollmentControls() {
    const form = document.getElementById("enrollment-form");
    if (!form) return;

    const tabWebcam = document.getElementById("tab-webcam");
    const tabUpload = document.getElementById("tab-upload");
    const contentWebcam = document.getElementById("content-webcam");
    const contentUpload = document.getElementById("content-upload");
    const captureSourceInput = document.getElementById("capture_source");
    
    // Tab switching
    tabWebcam.addEventListener("click", () => {
        tabWebcam.classList.add("active");
        tabUpload.classList.remove("active");
        contentWebcam.style.display = "block";
        contentUpload.style.display = "none";
        captureSourceInput.value = "webcam";
    });
    
    tabUpload.addEventListener("click", () => {
        tabUpload.classList.add("active");
        tabWebcam.classList.remove("active");
        contentUpload.style.display = "block";
        contentWebcam.style.display = "none";
        captureSourceInput.value = "upload";
        stopCaptureWebcam(); // Turn off camera if running
    });
    
    // Webcam capture elements
    const startCamBtn = document.getElementById("start-cam-btn");
    const snapBtn = document.getElementById("snap-btn");
    const retakeBtn = document.getElementById("retake-btn");
    const video = document.getElementById("capture-video");
    const canvas = document.getElementById("capture-canvas");
    const preview = document.getElementById("capture-preview");
    const instruct = document.getElementById("webcam-instruct");
    const imageDataInput = document.getElementById("image_data");
    
    // Start Camera Action
    startCamBtn.addEventListener("click", async () => {
        try {
            captureStream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: "user" }
            });
            video.srcObject = captureStream;
            video.style.display = "block";
            instruct.style.display = "none";
            preview.style.display = "none";
            
            startCamBtn.style.display = "none";
            snapBtn.style.display = "inline-flex";
            retakeBtn.style.display = "none";
            
            showAlert("info", "Webcam initialized. Align face in frame.");
        } catch (err) {
            console.error("Camera access error:", err);
            showAlert("error", "Could not access webcam. Verify permissions or select File Upload.");
        }
    });
    
    // Capture Photo Action
    snapBtn.addEventListener("click", () => {
        if (!captureStream) return;
        
        // Draw video frame to hidden canvas
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        const ctx = canvas.getContext("2d");
        
        // Mirror the canvas because webcam preview is usually mirrored or for better alignment
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // Extract base64 image data
        const dataUrl = canvas.toDataURL("image/jpeg", 0.95);
        imageDataInput.value = dataUrl;
        
        // Update elements to show snapshot
        preview.src = dataUrl;
        preview.style.display = "block";
        video.style.display = "none";
        
        snapBtn.style.display = "none";
        retakeBtn.style.display = "inline-flex";
        
        // Turn off camera stream to release device
        stopCaptureWebcam();
        showAlert("success", "Snapshot captured.");
    });
    
    // Retake Photo Action
    retakeBtn.addEventListener("click", () => {
        imageDataInput.value = "";
        preview.style.display = "none";
        instruct.style.display = "flex";
        startCamBtn.style.display = "inline-flex";
        retakeBtn.style.display = "none";
        startCamBtn.click(); // Restart instantly
    });
    
    // File Upload drop zone controls
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const uploadPrompt = document.getElementById("upload-prompt");
    const uploadFilename = document.getElementById("upload-filename");
    
    if (dropZone && fileInput) {
        dropZone.addEventListener("click", () => fileInput.click());
        
        dropZone.addEventListener("dragover", (e) => {
            e.preventDefault();
            dropZone.classList.add("dragover");
        });
        
        ["dragleave", "dragend", "drop"].forEach(event => {
            dropZone.addEventListener(event, () => dropZone.classList.remove("dragover"));
        });
        
        dropZone.addEventListener("drop", (e) => {
            e.preventDefault();
            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files;
                updateUploadUI(fileInput.files[0]);
            }
        });
        
        fileInput.addEventListener("change", () => {
            if (fileInput.files.length) {
                updateUploadUI(fileInput.files[0]);
            }
        });
    }
    
    function updateUploadUI(file) {
        uploadPrompt.textContent = "File Selected";
        uploadPrompt.style.color = "var(--color-success)";
        uploadFilename.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        showAlert("info", `File selected: ${file.name}`);
    }
    
    // Validate Form submission
    form.addEventListener("submit", function(e) {
        const source = captureSourceInput.value;
        if (source === "webcam" && !imageDataInput.value) {
            e.preventDefault();
            showAlert("warning", "Please start the camera and capture a snapshot before submitting.");
            return;
        }
        if (source === "upload" && (!fileInput.files || fileInput.files.length === 0)) {
            e.preventDefault();
            showAlert("warning", "Please select a file to upload.");
            return;
        }
        
        // Show loading state
        const submitBtn = form.querySelector(".btn-submit-enroll");
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Enrolling User...';
    });
}

function stopCaptureWebcam() {
    if (captureStream) {
        captureStream.getTracks().forEach(track => track.stop());
        captureStream = null;
    }
}

/* ==========================================================================
   User Directory Management
   ========================================================================== */
function initDirectorySearch() {
    const searchInput = document.getElementById("directory-search");
    if (!searchInput) return;
    
    searchInput.addEventListener("input", function() {
        const query = searchInput.value.toLowerCase().trim();
        const cards = document.querySelectorAll(".user-card");
        const emptyState = document.getElementById("directory-empty");
        
        let visibleCount = 0;
        cards.forEach(card => {
            const searchableText = card.getAttribute("data-search");
            if (searchableText.includes(query)) {
                card.style.display = "flex";
                visibleCount++;
            } else {
                card.style.display = "none";
            }
        });
        
        // Handle empty directory search results placeholder
        if (visibleCount === 0 && cards.length > 0) {
            if (!document.getElementById("search-empty")) {
                const empty = document.createElement("div");
                empty.id = "search-empty";
                empty.className = "directory-empty-state";
                empty.innerHTML = `<i class="fa-solid fa-magnifying-glass"></i><p>No matches found for "${query}"</p>`;
                document.getElementById("directory-grid-container").appendChild(empty);
            }
        } else {
            const searchEmpty = document.getElementById("search-empty");
            if (searchEmpty) searchEmpty.remove();
        }
    });
}

function initDeleteUserHandlers() {
    const gridContainer = document.getElementById("directory-grid-container");
    if (!gridContainer) return;
    
    gridContainer.addEventListener("click", function(e) {
        const btn = e.target.closest(".delete-user-btn");
        if (!btn) return;
        
        const userId = btn.getAttribute("data-id");
        const userName = btn.getAttribute("data-name");
        
        if (confirm(`Are you sure you want to delete ${userName} (${userId})? This will delete their registration metadata and facial template.`)) {
            // Disable button
            btn.disabled = true;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
            
            fetch(`/api/delete_user/${userId}`, {
                method: "POST"
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    const card = document.getElementById(`user-card-${userId}`);
                    card.style.transform = "scale(0.8)";
                    card.style.opacity = "0";
                    setTimeout(() => {
                        card.remove();
                        // Update counts
                        const countEl = document.getElementById("user-count");
                        if (countEl) {
                            const newCount = document.querySelectorAll(".user-card").length;
                            countEl.textContent = newCount;
                            
                            if (newCount === 0) {
                                window.location.reload(); // show empty state
                            }
                        }
                    }, 250);
                    showAlert("success", data.message);
                } else {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa-solid fa-trash-can"></i> Delete';
                    showAlert("error", data.message);
                }
            })
            .catch(err => {
                console.error("Delete failed:", err);
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-trash-can"></i> Delete';
                showAlert("error", "Server communication error. Try again.");
            });
        }
    });
}

/* ==========================================================================
   Real-Time Scanner Activity Polling
   ========================================================================== */
let lastSeenLogKey = null; // Stored as "UserID_Time" to identify fresh logs

function initScannerPolling() {
    const timeline = document.getElementById("live-scan-timeline");
    if (!timeline) return;
    
    // Initial fetch to establish baseline
    fetch("/api/recent_scans")
        .then(res => res.json())
        .then(data => {
            if (data.logs && data.logs.length > 0) {
                // Initialize the last seen log key with the newest item
                const latest = data.logs[0];
                lastSeenLogKey = `${latest.User_ID}_${latest.Time}`;
                
                // Pop items onto the timeline list visually
                const emptyState = document.getElementById("timeline-empty");
                if (emptyState) emptyState.remove();
                
                data.logs.forEach(log => {
                    appendTimelineItem(timeline, log, false);
                });
            }
        });
        
    // Periodic polling (every 1.5 seconds)
    setInterval(() => {
        fetch("/api/recent_scans")
            .then(res => res.json())
            .then(data => {
                if (data.logs && data.logs.length > 0) {
                    const latest = data.logs[0];
                    const key = `${latest.User_ID}_${latest.Time}`;
                    
                    if (lastSeenLogKey !== null && lastSeenLogKey !== key) {
                        // Found a new scan!
                        lastSeenLogKey = key;
                        
                        // Play beep!
                        playSuccessBeep();
                        
                        // Remove empty state if present
                        const emptyState = document.getElementById("timeline-empty");
                        if (emptyState) emptyState.remove();
                        
                        // Prepend new item
                        appendTimelineItem(timeline, latest, true);
                    } else if (lastSeenLogKey === null) {
                        lastSeenLogKey = key;
                    }
                }
            })
            .catch(err => console.error("Polling error:", err));
    }, 1500);
}

function appendTimelineItem(containerEl, log, animate = true) {
    // Avoid duplicates in timeline visual list
    const existingId = `timeline-log-${log.User_ID}-${log.Time.replace(/:/g, '')}`;
    if (document.getElementById(existingId)) return;
    
    const item = document.createElement("div");
    item.id = existingId;
    item.className = "timeline-item success";
    if (!animate) {
        item.style.animation = "none";
    }
    
    item.innerHTML = `
        <img class="timeline-avatar" src="/images/${log.User_ID}.jpg" alt="${log.Name}" onerror="this.src='https://api.dicebear.com/7.x/bottts/svg?seed=${log.User_ID}'">
        <div class="timeline-info">
            <h4>${log.Name}</h4>
            <p>ID: <span class="id-badge">${log.User_ID}</span> | ${log.Department}</p>
        </div>
        <div class="timeline-time">${log.Time}</div>
    `;
    
    // Prepend to show newest on top
    containerEl.insertBefore(item, containerEl.firstChild);
    
    // Keep max 10 items in feed list
    if (containerEl.children.length > 10) {
        containerEl.lastChild.remove();
    }
}
