
import serial
import csv
import re
import os
from datetime import datetime

# ==========================================
# SERIAL CONFIGURATION
# ==========================================

PORT = "COM10"
BAUDRATE = 115200

# ==========================================
# CSV CONFIGURATION
# ==========================================

DATA_FOLDER = "Data"

os.makedirs(DATA_FOLDER, exist_ok=True)

filename = datetime.now().strftime("NTC_Test_%Y%m%d_%H%M%S.csv")
filepath = os.path.join(DATA_FOLDER, filename)

# ==========================================
# DATA PARSER
# ==========================================

def parse_serial_line(line):
    pattern = r"T(\d+):([\d.-]+)\s+ADC:(\d+)"
    matches = re.findall(pattern, line)

    result = {}

    for sensor, temperature, adc in matches:
        sensor = int(sensor)

        result[f"T{sensor}"] = float(temperature)
        result[f"ADC{sensor}"] = int(adc)

    return result


# ==========================================
# MAIN PROGRAM
# ==========================================

print("===================================")
print("      STM32 NTC DATA LOGGER")
print("===================================")
print(f"Serial Port : {PORT}")
print(f"Baudrate    : {BAUDRATE}")
print("Starting CSV Logger...")
print("Press CTRL+C to stop logging.")
print("===================================")

try:
    ser = serial.Serial(PORT, BAUDRATE, timeout=2)

    # Header CSV
    headers = ["Timestamp"]

    for i in range(1, 9):
        headers.append(f"T{i}_C")

    for i in range(1, 9):
        headers.append(f"ADC{i}")

    sensor_data = {}

    with open(filepath, "w", newline="", encoding="utf-8") as file:

        writer = csv.writer(file)
        writer.writerow(headers)
        file.flush()

        print(f"\nCSV File: {filepath}\n")

        while True:

            line = ser.readline().decode(
                "utf-8", errors="replace"
            ).strip()

            if not line:
                continue

            print(line)

            parsed = parse_serial_line(line)
            sensor_data.update(parsed)

            # Simpan jika seluruh 8 sensor sudah terbaca
            if all(f"T{i}" in sensor_data for i in range(1, 9)) and \
               all(f"ADC{i}" in sensor_data for i in range(1, 9)):

                timestamp = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                row = [timestamp]

                for i in range(1, 9):
                    row.append(sensor_data[f"T{i}"])

                for i in range(1, 9):
                    row.append(sensor_data[f"ADC{i}"])

                writer.writerow(row)
                file.flush()

                print(">> Data saved to CSV\n")

                sensor_data.clear()

except KeyboardInterrupt:
    print("\nLogging stopped by user.")

except serial.SerialException as error:
    print(f"\nSerial Error: {error}")

finally:
    if "ser" in locals() and ser.is_open:
        ser.close()

    print("Serial connection closed.")
    print("CSV logging finished.")