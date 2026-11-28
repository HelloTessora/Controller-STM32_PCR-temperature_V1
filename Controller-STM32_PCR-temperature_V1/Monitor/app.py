
import os
import sys
import time
import csv
import re
import threading
import webbrowser

import serial
from serial.tools import list_ports

from datetime import datetime
from flask import Flask, jsonify, render_template, request


# ==========================================
# APPLICATION CONFIGURATION
# ==========================================

if getattr(sys, "frozen", False):
    BUNDLE_DIR = sys._MEIPASS
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = BUNDLE_DIR


app = Flask(
    __name__,
    template_folder=os.path.join(BUNDLE_DIR, "templates"),
    static_folder=os.path.join(BUNDLE_DIR, "static")
)

print("BUNDLE_DIR:", BUNDLE_DIR)
print("TEMPLATE FILE:", os.path.join(BUNDLE_DIR, "templates", "index.html"))

# ==========================================
# SERIAL CONFIGURATION
# ==========================================

BAUDRATE = 115200

ser = None
serial_write_lock = threading.RLock()

serial_status = {
    "connected": False,
    "message": "Waiting for STM32",
    "port": None
}


# ==========================================
# DATA STORAGE
# ==========================================

DOCUMENTS_DIR = os.path.join(
    os.path.expanduser("~"),
    "Documents"
)

DATA_FOLDER = os.path.join(
    DOCUMENTS_DIR,
    "PCR-Temperature Monitor",
    "Data"
)

os.makedirs(DATA_FOLDER, exist_ok=True)


# ==========================================
# SENSOR DATA
# ==========================================

ntc_data = {
    f"T{i}": None for i in range(1, 10)
}

data_lock = threading.Lock()


# ==========================================
# RECORDING SESSION
# ==========================================

session_lock = threading.Lock()

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


# ==========================================
# SERIAL PORT DISCOVERY
# ==========================================

def get_available_ports():

    ports = []

    for port in list_ports.comports():

        ports.append({
            "device": port.device,
            "description": port.description,
            "hwid": port.hwid
        })

    return ports


# ==========================================
# SERIAL READER
# ==========================================

def read_serial():

    global ser

    while True:

        with serial_write_lock:
            connection = ser

        if connection is None:
            time.sleep(0.1)
            continue

        try:

            if not connection.is_open:
                raise serial.SerialException(
                    "Serial port is closed."
                )

            line = connection.readline().decode(
                "utf-8",
                errors="ignore"
            ).strip()

            if not line:
                continue

            matches = re.findall(
                r"T(\d+):(-?\d+(?:\.\d+)?)",
                line
            )

            if matches:

                with data_lock:

                    for sensor, temperature in matches:

                        name = f"T{sensor}"

                        if name in ntc_data:

                            try:
                                ntc_data[name] = float(temperature)

                            except ValueError:
                                print(
                                    "Invalid temperature:",
                                    temperature
                                )

        except (serial.SerialException, OSError) as error:

            print("Serial Error:", error)

            with serial_write_lock:

                # Jangan mengganggu koneksi baru
                if ser is connection:

                    ser = None

                    try:
                        connection.close()
                    except Exception:
                        pass

                    serial_status.update({
                        "connected": False,
                        "message": "STM32 disconnected",
                        "port": None
                    })

            # Hentikan recording jika koneksi terputus
            stop_recording("Error: STM32 disconnected")

            time.sleep(0.2)


# ==========================================
# SEND COMMAND TO STM32
# ==========================================

def send_stm32_command(command):

    global ser

    try:

        with serial_write_lock:

            if ser is None or not ser.is_open:
                print("STM32 is not connected")
                return False

            ser.write(
                (command + "\r\n").encode("utf-8")
            )

            ser.flush()

        print("Command sent:", command)

        return True

    except (serial.SerialException, OSError) as error:

        print("Command error:", error)

        return False


# ==========================================
# RECORDING WORKER
# ==========================================

def recording_worker():

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

                remaining = max(
                    0,
                    duration - elapsed
                )

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

        if all(
            value is not None
            for value in snapshot.values()
        ):

            try:

                with open(
                    filename,
                    "a",
                    newline="",
                    encoding="utf-8"
                ) as file:

                    writer = csv.writer(file)

                    timestamp = datetime.now().isoformat(
                        timespec="milliseconds"
                    )

                    row = [
                        timestamp,
                        *[
                            snapshot[f"T{i}"]
                            for i in range(1, 10)
                        ]
                    ]

                    writer.writerow(row)

                with session_lock:

                    if session["active"]:
                        session["rows"] += 1

            except OSError as error:

                stop_recording(
                    f"Error: {error}"
                )

                continue

        time.sleep(interval)


# ==========================================
# STOP RECORDING
# ==========================================

def stop_recording(status="Manually Stopped"):

    with session_lock:

        if not session["active"]:
            return False

        session["active"] = False

        session["end_time"] = datetime.now().isoformat(
            timespec="seconds"
        )

        session["remaining"] = 0
        session["status"] = status

    send_stm32_command("STOP")

    return True


# ==========================================
# DASHBOARD ROUTE
# ==========================================

@app.route("/")
def index():

    return render_template("index.html")


# ==========================================
# SERIAL PORT API
# ==========================================

@app.route("/api/ports", methods=["GET"])
def get_ports():

    return jsonify({
        "success": True,
        "ports": get_available_ports()
    })


# ==========================================
# CONNECT STM32 API
# ==========================================

@app.route("/api/connect", methods=["POST"])
def connect_stm32():

    global ser

    config = request.get_json(silent=True) or {}

    selected_port = config.get("port")

    if not selected_port:

        return jsonify({
            "success": False,
            "message": "Please select a serial port."
        }), 400

    available_ports = get_available_ports()

    valid_port = any(
        port["device"] == selected_port
        for port in available_ports
    )

    if not valid_port:

        return jsonify({
            "success": False,
            "message": "Selected serial port is not available."
        }), 404

    try:

        with serial_write_lock:

            if ser is not None and ser.is_open:

                return jsonify({
                    "success": False,
                    "message": "Another serial connection is already active."
                }), 409

            connection = serial.Serial(
                selected_port,
                BAUDRATE,
                timeout=1
            )

            connection.reset_input_buffer()

            ser = connection

            serial_status.update({
                "connected": True,
                "message": "STM32 Connected",
                "port": selected_port
            })

        print("STM32 Connected:", selected_port)

        return jsonify({
            "success": True,
            "message": f"STM32 successfully connected on {selected_port}.",
            "port": selected_port
        })

    except (serial.SerialException, OSError) as error:

        serial_status.update({
            "connected": False,
            "message": str(error),
            "port": None
        })

        return jsonify({
            "success": False,
            "message": str(error)
        }), 503


# ==========================================
# DISCONNECT STM32 API
# ==========================================

@app.route("/api/disconnect", methods=["POST"])
def disconnect_stm32():

    global ser

    with session_lock:

        if session["active"]:

            return jsonify({
                "success": False,
                "message": "Stop recording before disconnecting STM32."
            }), 409

    with serial_write_lock:

        if ser is None:

            return jsonify({
                "success": False,
                "message": "STM32 is already disconnected."
            }), 400

        try:
            ser.close()
        except Exception:
            pass

        ser = None

        serial_status.update({
            "connected": False,
            "message": "STM32 disconnected",
            "port": None
        })

    print("STM32 Disconnected")

    return jsonify({
        "success": True,
        "message": "STM32 successfully disconnected."
    })


# ==========================================
# SENSOR DATA API
# ==========================================

@app.route("/api/data")
def get_data():

    with data_lock:
        sensors = ntc_data.copy()

    return jsonify({
        "sensors": sensors,
        "serial": serial_status.copy()
    })


# ==========================================
# SESSION STATUS API
# ==========================================

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

    result.pop("start_time", None)
    result.pop("filename", None)

    return jsonify(result)


# ==========================================
# DATA STORAGE API
# ==========================================

@app.route("/api/storage", methods=["GET"])
def get_storage_location():

    return jsonify({
        "success": True,
        "path": DATA_FOLDER
    })


# ==========================================
# OPEN DATA FOLDER API
# ==========================================

@app.route("/api/open-data-folder", methods=["POST"])
def open_data_folder():

    try:

        os.makedirs(DATA_FOLDER, exist_ok=True)

        os.startfile(
            os.path.normpath(DATA_FOLDER)
        )

        return jsonify({
            "success": True,
            "message": "Data folder opened successfully."
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "message": str(error)
        }), 500


# ==========================================
# START RECORDING API
# ==========================================

@app.route("/api/start", methods=["POST"])
def start_recording():

    if not serial_status["connected"]:

        return jsonify({
            "success": False,
            "message": "STM32 is not connected."
        }), 400

    config = request.get_json(silent=True) or {}

    mode = config.get("mode")
    interval = config.get("interval")
    duration = config.get("duration", 0)

    if mode not in ("manual", "timed"):

        return jsonify({
            "success": False,
            "message": "Invalid recording mode."
        }), 400

    try:

        interval = float(interval)
        duration = int(duration)

    except (TypeError, ValueError):

        return jsonify({
            "success": False,
            "message": "Invalid interval or duration."
        }), 400

    if interval not in (0.5, 1, 2, 5, 10):

        return jsonify({
            "success": False,
            "message": "Invalid sampling interval."
        }), 400

    if mode == "timed" and not (1 <= duration <= 86400):

        return jsonify({
            "success": False,
            "message": "Duration must be between 1 and 86400 seconds."
        }), 400

    with session_lock:

        if session["active"]:

            return jsonify({
                "success": False,
                "message": "Recording is already running."
            }), 409

        now = datetime.now()

        filename = os.path.join(
            DATA_FOLDER,
            f"NTC_Test_{now.strftime('%Y%m%d_%H%M%S')}.csv"
        )

        try:

            with open(
                filename,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:

                writer = csv.writer(file)

                writer.writerow([
                    "Timestamp",
                    *[
                        f"T{i}_C"
                        for i in range(1, 10)
                    ]
                ])

        except OSError as error:

            return jsonify({
                "success": False,
                "message": str(error)
            }), 500

        if not send_stm32_command("START"):

            return jsonify({
                "success": False,
                "message": "Failed to send START command to STM32."
            }), 503

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
        "message": "Recording started."
    })


# ==========================================
# STOP RECORDING API
# ==========================================

@app.route("/api/stop", methods=["POST"])
def stop_route():

    stopped = stop_recording("Manually Stopped")

    if not stopped:

        return jsonify({
            "success": False,
            "message": "No active recording session."
        }), 400

    return jsonify({
        "success": True,
        "message": "Recording stopped."
    })


# ==========================================
# APPLICATION STARTUP
# ==========================================

if __name__ == "__main__":

    threading.Thread(
        target=read_serial,
        daemon=True
    ).start()

    threading.Thread(
        target=recording_worker,
        daemon=True
    ).start()

    threading.Timer(
        1.5,
        lambda: webbrowser.open(
            "http://127.0.0.1:5000"
        )
    ).start()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )
