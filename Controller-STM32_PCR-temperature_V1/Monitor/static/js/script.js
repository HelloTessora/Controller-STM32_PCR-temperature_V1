
// ==============================
// TEMPERATURE CHART
// ==============================

const MAX_POINTS = 60;

const labels = [];
const temperatureHistory = {};

// Initialize temperature history for T1-T9
for (let i = 1; i <= 9; i++) {
    temperatureHistory[`T${i}`] = [];
}

// Create chart datasets
const datasets = [];

for (let i = 1; i <= 9; i++) {
    datasets.push({
        label: `T${i}`,
        data: temperatureHistory[`T${i}`],
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.25,
        fill: false
    });
}

// Initialize Chart.js
const chart = new Chart(
    document.getElementById("temperatureChart"),
    {
        type: "line",

        data: {
            labels: labels,
            datasets: datasets
        },

        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,

            interaction: {
                mode: "index",
                intersect: false
            },

            plugins: {
                legend: {
                    position: "bottom"
                }
            },

            scales: {
                x: {
                    title: {
                        display: true,
                        text: "Time"
                    }
                },

                y: {
                    title: {
                        display: true,
                        text: "Temperature (°C)"
                    }
                }
            }
        }
    }
);


// ==============================
// LIVE DASHBOARD
// ==============================

let dashboardUpdating = false;

async function updateDashboard() {

    if (dashboardUpdating) return;

    dashboardUpdating = true;

    try {
        const response = await fetch("/api/data");

        if (!response.ok) {
            throw new Error("Failed to fetch sensor data.");
        }

        const data = await response.json();

        // Connection status
        const status = document.getElementById(
            "connection-status"
        );

        if (data.serial.connected) {

            status.textContent = "● STM32 Connected";
            status.style.background = "#e6f7ee";
            status.style.color = "#16834a";

        } else {

            status.textContent = "● Disconnected";
            status.style.background = "#fdeaea";
            status.style.color = "#d93025";
        }

        // Update Device Connection panel
        updateDeviceConnectionUI(data.serial);

        // Update sensor values T1-T9
        for (let i = 1; i <= 9; i++) {

            const temperature = data.sensors[`T${i}`];

            const sensorElement = document.getElementById(
                `T${i}`
            );

            if (sensorElement) {
                sensorElement.textContent =
                    temperature !== null &&
                    temperature !== undefined
                        ? Number(temperature).toFixed(2)
                        : "--.--";
            }
        }

        // Check whether all sensors have valid data
        const allValid = Array.from(
            { length: 9 },
            (_, i) => {
        const value = data.sensors[`T${i + 1}`];

        return (
            value !== null &&
            value !== undefined &&
            Number.isFinite(Number(value))
        );
    }
).every(Boolean);

        // Update temperature chart
        if (allValid) {

            const now = new Date().toLocaleTimeString();

            labels.push(now);

            for (let i = 1; i <= 9; i++) {

                temperatureHistory[`T${i}`].push(
                    Number(data.sensors[`T${i}`])
                );
            }


            // Limit chart history to MAX_POINTS
            if (labels.length > MAX_POINTS) {

                labels.shift();

                for (let i = 1; i <= 9; i++) {
                    temperatureHistory[`T${i}`].shift();
                }
            }

            chart.update("none");
        }

    } catch (error) {

        console.error("Dashboard error:", error);
    } finally {

        dashboardUpdating = false;
    }
}


// Update dashboard every second
setInterval(updateDashboard, 1000);
updateDashboard();

// ==============================
// DATA ACQUISITION CONTROL
// ==============================

const modeInputs = document.querySelectorAll(
    'input[name="mode"]'
);

const durationGroup = document.getElementById(
    "duration-group"
);

const hoursInput = document.getElementById(
    "duration-hours"
);

const minutesInput = document.getElementById(
    "duration-minutes"
);

const secondsInput = document.getElementById(
    "duration-seconds"
);

const intervalInput = document.getElementById(
    "interval"
);

const countdownDisplay = document.getElementById(
    "countdown"
);

const recordingStatus = document.getElementById(
    "recording-status"
);

const recordedRows = document.getElementById(
    "recorded-rows"
);

const startButton = document.getElementById(
    "start-button"
);

const stopButton = document.getElementById(
    "stop-button"
);

const recordingMessage = document.getElementById(
    "recording-message"
);


// ==============================
// MODE SELECTION
// ==============================

function updateMode() {

    const selectedMode = document.querySelector(
        'input[name="mode"]:checked'
    ).value;

    durationGroup.style.display =
        selectedMode === "timed" ? "block" : "none";
}


modeInputs.forEach(input => {
    input.addEventListener("change", updateMode);
});

updateMode();


// ==============================
// TIME FORMAT
// ==============================

function formatTime(seconds) {

    seconds = Math.ceil(Math.max(0, seconds));

    const hours = Math.floor(seconds / 3600);

    const minutes = Math.floor(
        (seconds % 3600) / 60
    );

    const secs = seconds % 60;

    return [hours, minutes, secs]
        .map(value => String(value).padStart(2, "0"))
        .join(":");
}


// ==============================
// START RECORDING
// ==============================

async function startRecording() {

    const mode = document.querySelector(
        'input[name="mode"]:checked'
    ).value;

    const hours = Number(hoursInput.value);
    const minutes = Number(minutesInput.value);
    const seconds = Number(secondsInput.value);

    const interval = Number(intervalInput.value);


    // Convert HH:MM:SS into total seconds
    const totalSeconds =
        (hours * 3600) +
        (minutes * 60) +
        seconds;


    // Validate duration for Timed Mode
    if (
        mode === "timed" &&
        (
            hoursInput.value.trim() === "" ||
            minutesInput.value.trim() === "" ||
            secondsInput.value.trim() === "" ||
            !Number.isInteger(hours) ||
            !Number.isInteger(minutes) ||
            !Number.isInteger(seconds) ||
            hours < 0 || hours > 24 ||
            minutes < 0 || minutes > 59 ||
            seconds < 0 || seconds > 59 ||
            totalSeconds < 1 ||
            totalSeconds > 86400
        )
    ) {

        alert(
            "Please enter a valid duration. Maximum duration is 24 hours."
        );

        return;
    }


    // Validate sampling interval
    if (![0.5, 1, 2, 5, 10].includes(interval)) {

        alert("Please select a valid sampling interval.");

        return;
    }


    startButton.disabled = true;

    recordingMessage.textContent = "Starting recording...";


    try {

        const response = await fetch("/api/start", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({

                mode: mode,

                duration: mode === "timed"
                    ? totalSeconds
                    : 0,

                interval: interval
            })
        });


        const result = await response.json();


        if (!response.ok) {

            throw new Error(
                result.message || "Failed to start recording."
            );
        }


        recordingMessage.textContent = result.message;

        await updateRecordingStatus();


    } catch (error) {

        recordingMessage.textContent = error.message;

        startButton.disabled = false;
    }
}


// ==============================
// STOP RECORDING
// ==============================

async function stopRecording() {

    stopButton.disabled = true;


    try {

        const response = await fetch("/api/stop", {

            method: "POST"
        });


        const result = await response.json();


        if (!response.ok) {

            throw new Error(
                result.message || "Failed to stop recording."
            );
        }


        recordingMessage.textContent = result.message;

        await updateRecordingStatus();


    } catch (error) {

        recordingMessage.textContent = error.message;
    }
}


// ==============================
// UPDATE RECORDING STATUS
// ==============================

async function updateRecordingStatus() {

    try {

        const response = await fetch("/api/session");

        if (!response.ok) {
            throw new Error("Failed to fetch session status.");
        }

        const data = await response.json();

        // Update recording information
        recordingStatus.textContent = data.status;
        recordedRows.textContent = data.rows;

        const active = data.active;

        // Enable or disable buttons
        startButton.disabled = active;
        stopButton.disabled = !active;

        // Lock mode selection during recording
        modeInputs.forEach(input => {
            input.disabled = active;
        });

        // Lock duration inputs during recording
        hoursInput.disabled = active;
        minutesInput.disabled = active;
        secondsInput.disabled = active;
        intervalInput.disabled = active;

        // Countdown display
        if (data.mode === "timed" && active) {

            countdownDisplay.textContent = formatTime(
                data.remaining
            );

        } else if (data.mode === "manual" && active) {

            countdownDisplay.textContent = "MANUAL";

        } else {

            countdownDisplay.textContent = "00:00:00";
        }

        // Recording completion message
        if (!active) {

            if (data.status === "Completed") {

            recordingMessage.textContent =
            "Timed recording completed.";

            } else if (data.status === "Manually Stopped") {

            recordingMessage.textContent =
            "Recording stopped manually.";

            } else if (data.status.startsWith("Error:")) {

            recordingMessage.textContent =
            data.status;
            }
        }

    } catch (error) {

        console.error("Session status error:", error);
    }
}

// ==============================
// AUTOMATIC STATUS UPDATE
// ==============================

setInterval(updateRecordingStatus, 500);
updateRecordingStatus();

// ==============================
// DATA STORAGE
// ==============================

// Display the CSV storage location
async function updateStorageLocation() {

    const storagePath = document.getElementById(
        "storage-path"
    );

    if (!storagePath) return;

    try {

        const response = await fetch("/api/storage");

        if (!response.ok) {
            throw new Error("Failed to get storage location.");
        }

        const data = await response.json();

        if (data.success) {

            storagePath.textContent = data.path;

        } else {

            storagePath.textContent =
                "Storage location unavailable.";
        }

    } catch (error) {

        console.error("Storage location error:", error);

        storagePath.textContent =
            "Unable to retrieve storage location.";
    }
}

// ==============================
// OPEN DATA FOLDER
// ==============================

async function openDataFolder() {

    const openFolderButton = document.getElementById(
        "open-folder-button"
    );

    openFolderButton.disabled = true;
    openFolderButton.textContent = "Opening...";

    try {

        const response = await fetch(
            "/api/open-data-folder",
            {
                method: "POST"
            }
        );

        const result = await response.json();

        if (!response.ok) {

            throw new Error(
                result.message || "Failed to open data folder."
            );
        }

        openFolderButton.textContent = "Folder Opened";

    } catch (error) {

        console.error("Open folder error:", error);

        alert(
            "Unable to open data folder:\n" + error.message
        );

        openFolderButton.textContent = "Open Data Folder";

    } finally {

        openFolderButton.disabled = false;

        setTimeout(() => {

            openFolderButton.textContent =
                "Open Data Folder";

        }, 2000);
    }
}

// Initialize storage information
updateStorageLocation();


// ==============================
// DEVICE CONNECTION
// ==============================

const serialPortSelect = document.getElementById("serial-port");
const refreshPortButton = document.getElementById("refresh-port-button");
const connectButton = document.getElementById("connect-button");
const disconnectButton = document.getElementById("disconnect-button");

const deviceStatus = document.getElementById("device-status");
const deviceMessage = document.getElementById("device-message");


// ==============================
// REFRESH AVAILABLE PORTS
// ==============================

async function refreshSerialPorts() {

    refreshPortButton.disabled = true;
    refreshPortButton.textContent = "Scanning...";

    try {

        const response = await fetch("/api/ports");

        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.message || "Unable to scan serial ports.");
        }

        const ports = result.ports || [];

        const previousPort = serialPortSelect.value;

        serialPortSelect.innerHTML = "";

        if (ports.length === 0) {

            serialPortSelect.add(
                new Option("No serial ports detected", "")
            );

            deviceMessage.textContent = "No serial devices found.";
            return;
        }

        ports.forEach(port => {

            const option = new Option(
                `${port.device} - ${port.description}`,
                port.device
            );

            option.dataset.hwid = port.hwid || "";

            serialPortSelect.add(option);
        });

        // Preserve previous selection when available
        const previousAvailable = ports.some(
            port => port.device === previousPort
        );

        if (previousAvailable) {

            serialPortSelect.value = previousPort;

        } else {

            // Detect STM32 using USB VID/PID
            const stm32Port = ports.find(port =>
                (port.hwid || "").toUpperCase().includes("VID:PID=0483:5740")
            );

            if (stm32Port) {

                serialPortSelect.value = stm32Port.device;

                deviceMessage.textContent =
                    `STM32 detected on ${stm32Port.device}`;

            } else {

                serialPortSelect.value = ports[0].device;

                deviceMessage.textContent =
                    "Select the serial port connected to your STM32.";
            }
        }

    } catch (error) {

        console.error("Port scanning error:", error);

        deviceMessage.textContent = error.message;

    } finally {

        refreshPortButton.disabled = false;
        refreshPortButton.textContent = "Refresh Ports";
    }
}


// ==============================
// CONNECT STM32
// ==============================

async function connectSTM32() {

    const port = serialPortSelect.value;

    if (!port) {

        deviceMessage.textContent = "Please select a serial port.";
        return;
    }

    connectButton.disabled = true;
    connectButton.textContent = "Connecting...";

    try {

        const response = await fetch("/api/connect", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                port: port
            })
        });

        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.message || "Connection failed.");
        }

        deviceMessage.textContent = result.message;

        await updateDashboard();

    } catch (error) {

        console.error("STM32 connection error:", error);

        deviceMessage.textContent = error.message;

    } finally {

        connectButton.disabled = false;
        connectButton.textContent = "Connect";
    }
}


// ==============================
// DISCONNECT STM32
// ==============================

async function disconnectSTM32() {

    disconnectButton.disabled = true;
    disconnectButton.textContent = "Disconnecting...";

    try {

        const response = await fetch("/api/disconnect", {
            method: "POST"
        });

        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.message || "Disconnection failed.");
        }

        deviceMessage.textContent = result.message;

        await updateDashboard();

    } catch (error) {

        console.error("STM32 disconnection error:", error);

        deviceMessage.textContent = error.message;

    } finally {

        disconnectButton.textContent = "Disconnect";
    }
}


// ==============================
// UPDATE DEVICE CONNECTION UI
// ==============================

function updateDeviceConnectionUI(serial) {

    if (!serial) return;

    if (serial.connected) {

        deviceStatus.textContent = "Connected";
        deviceStatus.className = "device-status connected";

        deviceMessage.textContent =
            `STM32 connected${serial.port ? " on " + serial.port : ""}.`;

        connectButton.disabled = true;
        disconnectButton.disabled = false;
        serialPortSelect.disabled = true;

    } else {

        deviceStatus.textContent = "Disconnected";
        deviceStatus.className = "device-status disconnected";

        connectButton.disabled = false;
        disconnectButton.disabled = true;
        serialPortSelect.disabled = false;

        if (serial.message) {
            deviceMessage.textContent = serial.message;
        }
    }
}


// ==============================
// INITIALIZE DEVICE CONNECTION
// ==============================

refreshSerialPorts();
