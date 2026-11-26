
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

# Mengambil lokasi folder tempat CSV_Logger.py berada
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Menyimpan CSV ke folder Monitor/Data
DATA_FOLDER = os.path.join(BASE_DIR, "Data")

# Membuat folder Data jika belum tersedia
os.makedirs(DATA_FOLDER, exist_ok=True)

# Membuat nama file berdasarkan waktu logging
filename = datetime.now().strftime("NTC_Test_%Y%m%d_%H%M%S.csv")
filepath = os.path.join(DATA_FOLDER, filename)

print("Lokasi CSV:", os.path.abspath(filepath))


# ==========================================
# DATA PARSER
# ==========================================

def parse_serial_line(line):
    pattern = r"T(\d+):([\d.-]+)\s+ADC:(\d+)"
    matches = re.findall(pattern, line)

    result = {}

    for sensor, temperature, adc in matches:
        sensor = int(sensor)

        if 1 <= sensor <= 9:
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

ser = None

try:
    # Membuka koneksi serial
    ser = serial.Serial(PORT, BAUDRATE, timeout=2)

    # Membuat header CSV
    headers = ["Timestamp"]

    for i in range(1, 10):
        headers.append(f"T{i}_C")

    for i in range(1, 10):
        headers.append(f"ADC{i}")

    sensor_data = {}

    # Membuka file CSV
    with open(filepath, "w", newline="", encoding="utf-8") as file:

        writer = csv.writer(file)

        # Menulis header
        writer.writerow(headers)
        file.flush()

        print(f"\nCSV File: {filepath}\n")

        while True:

            # Membaca data serial dari STM32
            line = ser.readline().decode(
                "utf-8", errors="replace"
            ).strip()

            if not line:
                continue

            print(line)

            # Mengambil data suhu dan ADC
            parsed = parse_serial_line(line)
            sensor_data.update(parsed)

            # Memastikan seluruh 9 sensor sudah terbaca
            if all(f"T{i}" in sensor_data for i in range(1, 10)) and \
               all(f"ADC{i}" in sensor_data for i in range(1, 10)):

                # Membuat timestamp
                timestamp = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

                row = [timestamp]

                # Menambahkan data temperatur T1-T9
                for i in range(1, 10):
                    row.append(sensor_data[f"T{i}"])

                # Menambahkan data ADC1-ADC9
                for i in range(1, 10):
                    row.append(sensor_data[f"ADC{i}"])

                # Menyimpan satu baris data ke CSV
                writer.writerow(row)
                file.flush()

                print(">> Data 9 sensors saved to CSV\n")

                # Mengosongkan data untuk siklus berikutnya
                sensor_data.clear()

except KeyboardInterrupt:
    print("\nLogging stopped by user.")

except serial.SerialException as error:
    print(f"\nSerial Error: {error}")

finally:
    if ser is not None and ser.is_open:
        ser.close()

    print("Serial connection closed.")
    print("CSV logging finished.")
