
// ==============================
// TEMPERATURE CHART
// ==============================

const MAX_POINTS = 60;

const labels = [];
const temperatureHistory = {};

for (let i = 1; i <= 8; i++) {
    temperatureHistory[`T${i}`] = [];
}

const datasets = [];

for (let i = 1; i <= 8; i++) {
    datasets.push({
        label: `T${i}`,
        data: temperatureHistory[`T${i}`],
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.25,
        fill: false
    });
}

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

async function updateDashboard() {
    try {
        const response = await fetch("/api/data");

        if (!response.ok) {
            throw new Error("Failed to fetch sensor data.");
        }

        const data = await response.json();

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

        for (let i = 1; i <= 8; i++) {
            const temperature = data.sensors[`T${i}`];

            document.getElementById(`T${i}`).textContent =
                temperature !== null
                    ? temperature.toFixed(2)
                    : "--.--";
        }

        const allValid = Object.values(data.sensors)
            .every(value => value !== null);

        if (allValid) {
            const now = new Date().toLocaleTimeString();

            labels.push(now);

            for (let i = 1; i <= 8; i++) {
                temperatureHistory[`T${i}`].push(
                    data.sensors[`T${i}`]
                );
            }

            if (labels.length > MAX_POINTS) {
                labels.shift();

                for (let i = 1; i <= 8; i++) {
                    temperatureHistory[`T${i}`].shift();
                }
            }

            chart.update("none");
        }

    } catch (error) {
        console.error("Dashboard error:", error);
    }
}

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
    const minutes = Math.floor((seconds % 3600) / 60);
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
                duration: mode === "timed" ? totalSeconds : 0,
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

        recordingStatus.textContent = data.status;
        recordedRows.textContent = data.rows;

        const active = data.active;

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
        if (!active && data.status === "Completed") {
            recordingMessage.textContent =
                "Timed recording completed.";
        }

        if (!active && data.status === "Manually Stopped") {
            recordingMessage.textContent =
                "Recording stopped manually.";
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
