
from flask import Flask, jsonify, render_template, request
import serial
import threading
import re
import time
import csv
import os
from datetime import datetime

app = Flask(__name__)

# ==============================
# SERIAL CONFIGURATION
# ==============================

SERIAL_PORT = "COM10"
BAUDRATE = 115200

# ==============================
# DATA STORAGE
# ==============================

DATA_FOLDER = "Data"
os.makedirs(DATA_FOLDER, exist_ok=True)

ntc_data = {f"T{i}": None for i in range(1, 9)}

serial_status = {
    "connected": False,
    "message": "Waiting for STM32"
}

data_lock = threading.Lock()
session_lock = threading.Lock()

# ==============================
# RECORDING SESSION
# ==============================

session = {
    "active": False,
    "mode": None,
    "duration": 0,
    "interval": 1,
    "start_time": None,
    "end_time": None,
    "remaining": 0,
    "rows": 0,
    "status": "Idle",
    "filename": None
}


def read_serial():
    while True:
        try:
            with serial.Serial(
                SERIAL_PORT,
                BAUDRATE,
                timeout=1
            ) as ser:

                serial_status["connected"] = True
                serial_status["message"] = "STM32 Connected"

                while True:
                    line = ser.readline().decode(
                        "utf-8", errors="ignore"
                    ).strip()

                    if not line:
                        continue

                    matches = re.findall(
                        r"T(\d+):([\d.]+)", line
                    )

                    if matches:
                        with data_lock:
                            for sensor, temperature in matches:
                                name = f"T{sensor}"

                                if name in ntc_data:
                                    ntc_data[name] = float(temperature)

        except serial.SerialException as error:
            serial_status["connected"] = False
            serial_status["message"] = str(error)
            time.sleep(2)


def recording_worker():
    """Mengelola interval pencatatan dan automatic stop."""

    while True:
        with session_lock:
            active = session["active"]

            if active:
                mode = session["mode"]
                interval = session["interval"]
                duration = session["duration"]
                start = session["start_time"]
                filename = session["filename"]

                elapsed = time.monotonic() - start
                remaining = max(0, duration - elapsed)

                session["remaining"] = remaining

                should_stop = (
                    mode == "timed" and remaining <= 0
                )
            else:
                should_stop = False

        if not active:
            time.sleep(0.1)
            continue

        if should_stop:
            stop_recording("Completed")
            continue

        if not serial_status["connected"]:
            time.sleep(0.2)
            continue

        with data_lock:
            snapshot = ntc_data.copy()

        if all(value is not None for value in snapshot.values()):
            try:
                with open(filename, "a", newline="") as file:
                    writer = csv.writer(file)

                    timestamp = datetime.now().isoformat(
                        timespec="milliseconds"
                    )

                    writer.writerow([
                        timestamp,
                        *[snapshot[f"T{i}"] for i in range(1, 9)]
                    ])

                with session_lock:
                    if session["active"]:
                        session["rows"] += 1

            except OSError as error:
                stop_recording(f"Error: {error}")
                continue

        time.sleep(interval)


def stop_recording(status="Manually Stopped"):
    with session_lock:
        if not session["active"]:
            return

        session["active"] = False
        session["end_time"] = datetime.now().isoformat(
            timespec="seconds"
        )
        session["remaining"] = 0
        session["status"] = status


# ==============================
# WEB ROUTES
# ==============================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/data")
def get_data():
    with data_lock:
        sensors = ntc_data.copy()

    return jsonify({
        "sensors": sensors,
        "serial": serial_status
    })


@app.route("/api/session")
def get_session():
    with session_lock:
        result = session.copy()

    if result["active"] and result["mode"] == "timed":
        result["remaining"] = max(
            0,
            result["duration"] - (
                time.monotonic() - result["start_time"]
            )
        )

    # Jangan kirim nilai monotonic internal ke browser
    result.pop("start_time", None)
    result.pop("filename", None)

    return jsonify(result)


@app.route("/api/start", methods=["POST"])
def start_recording():
    if not serial_status["connected"]:
        return jsonify({
            "success": False,
            "message": "STM32 belum terhubung"
        }), 400

    config = request.get_json(silent=True) or {}

    mode = config.get("mode")
    interval = config.get("interval")
    duration = config.get("duration", 0)

    if mode not in ("manual", "timed"):
        return jsonify({
            "success": False,
            "message": "Mode tidak valid"
        }), 400

    try:
        interval = float(interval)
        duration = int(duration)
    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "message": "Interval atau durasi tidak valid"
        }), 400

    if interval not in (0.5, 1, 2, 5, 10):
        return jsonify({
            "success": False,
            "message": "Sampling interval tidak valid"
        }), 400

    if mode == "timed" and not (1 <= duration <= 86400):
        return jsonify({
            "success": False,
            "message": "Durasi harus 1 sampai 86400 detik"
        }), 400

    with session_lock:
        if session["active"]:
            return jsonify({
                "success": False,
                "message": "Recording sedang berjalan"
            }), 409

        now = datetime.now()
        filename = os.path.join(
            DATA_FOLDER,
            f"NTC_Test_{now.strftime('%Y%m%d_%H%M%S')}.csv"
        )

        with open(filename, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([
                "Timestamp",
                "T1_C", "T2_C", "T3_C", "T4_C",
                "T5_C", "T6_C", "T7_C", "T8_C"
            ])

        session.update({
            "active": True,
            "mode": mode,
            "duration": duration if mode == "timed" else 0,
            "interval": interval,
            "start_time": time.monotonic(),
            "end_time": None,
            "remaining": duration if mode == "timed" else 0,
            "rows": 0,
            "status": "Recording",
            "filename": filename
        })

    return jsonify({
        "success": True,
        "message": "Recording started"
    })


@app.route("/api/stop", methods=["POST"])
def stop_route():
    stop_recording("Manually Stopped")

    return jsonify({
        "success": True,
        "message": "Recording stopped"
    })


if __name__ == "__main__":
    threading.Thread(
        target=read_serial,
        daemon=True
    ).start()

    threading.Thread(
        target=recording_worker,
        daemon=True
    ).start()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
