import serial
import time

ser = serial.Serial("COM10", 115200, timeout=2)
time.sleep(2)

print("Terhubung ke STM32 melalui COM10")
print("Menunggu data...")

try:
    while True:
        data = ser.readline().decode("utf-8", errors="replace").strip()
        if data:
            print(repr(data))
except KeyboardInterrupt:
    print("Pengujian dihentikan.")
finally:
    ser.close()
