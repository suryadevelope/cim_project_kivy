import serial
import pynmea2
import threading
import tkinter as tk
from tkinter import ttk
from typing import Optional

class GPSReader:
    def __init__(self, port='COM7', baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.gga_msg = None
        self.gsa_msg = None
        self.rmc_msg = None
        self.irnss_sats = []
        self.other_sats = []
        self.running = False
        self.lock = threading.Lock()

    def parse_nmea_sentence(self, sentence):
        try:
            msg = pynmea2.parse(sentence)
            return msg
        except pynmea2.ParseError:
            return None

    def is_3d_fix(self):
        if self.gsa_msg and int(getattr(self.gsa_msg, 'mode_fix_type', 0)) == 3:
            return True
        if self.gga_msg and int(getattr(self.gga_msg, 'gps_qual', 0)) > 1:
            return True
        return False

    def fix_type(self):
        # 0: No fix, 1: 2D, 2: 3D, 3: IRNSS fix
        if self.gsa_msg:
            mode = int(getattr(self.gsa_msg, 'mode_fix_type', 0))
            prns = self.get_gsa_prns()
            irnss_in_fix = [prn for prn in prns if prn and prn.startswith('8')]
            if mode == 3 and irnss_in_fix:
                return "3D Fix (IRNSS)"
            elif mode == 3:
                return "3D Fix"
            elif mode == 2:
                return "2D Fix"
        if self.gga_msg and int(getattr(self.gga_msg, 'gps_qual', 0)) > 0:
            return "Fix"
        return "No Fix"

    def parse_irgsv(self, sentence):
        if '*' in sentence:
            sentence = sentence.split('*')[0]
        fields = sentence.split(',')
        sats = []
        for i in range(4, len(fields), 4):
            if i+3 < len(fields):
                prn = fields[i]
                el = fields[i+1]
                az = fields[i+2]
                snr = fields[i+3]
                if prn:
                    sats.append({'prn': prn, 'elevation': el, 'azimuth': az, 'snr': snr})
        return sats

    def get_gsa_prns(self):
        if not self.gsa_msg:
            return []
        return [getattr(self.gsa_msg, f'sv_id{i}', None) for i in range(1, 13)]

    def get_lat_lng(self):
        if self.gga_msg:
            return (self.gga_msg.latitude, self.gga_msg.longitude)
        return (None, None)

    def get_speed(self):
        if self.rmc_msg:
            try:
                spd = getattr(self.rmc_msg, 'spd_over_grnd', None)
                if spd is not None and spd != '':
                    return float(spd) * 1.852
                else:
                    return None
            except Exception:
                return None
        return None

    def get_accuracy(self):
        # Returns (HDOP, PDOP, VDOP, num_sats)
        def safe_float(sval: str) -> Optional[float]:
            sval = sval.strip().lower()
            if sval == '' or sval == 'none' or sval == 'nan':
                return None
            try:
                return float(sval)
            except Exception:
                return None
        def safe_int(sval: str) -> Optional[int]:
            sval = sval.strip().lower()
            if sval == '' or sval == 'none' or sval == 'nan':
                return None
            try:
                return int(float(sval))
            except Exception:
                return None
        def to_str(val) -> str:
            return '' if val is None else str(val)
        hdop = pdop = vdop = None
        if self.gsa_msg:
            try:
                pdop_val = to_str(getattr(self.gsa_msg, 'pdop', None))
                hdop_val = to_str(getattr(self.gsa_msg, 'hdop', None))
                vdop_val = to_str(getattr(self.gsa_msg, 'vdop', None))
                pdop = safe_float(pdop_val)
                hdop = safe_float(hdop_val)
                vdop = safe_float(vdop_val)
            except Exception:
                pass
        num_sats = None
        if self.gga_msg:
            try:
                num_sats_val = to_str(getattr(self.gga_msg, 'num_sats', None))
                num_sats = safe_int(num_sats_val)
            except Exception:
                pass
        return (hdop, pdop, vdop, num_sats)

    def read_loop(self):
        self.running = True
        with serial.Serial(self.port, self.baudrate, timeout=1) as ser:
            while self.running:
                try:
                    line = ser.readline().decode(errors='ignore').strip()
                except Exception:
                    continue
                if not line.startswith('$'):
                    continue
                msg = self.parse_nmea_sentence(line)
                with self.lock:
                    if msg:
                        sentence_type = getattr(msg, 'sentence_type', None)
                        if sentence_type == 'GGA':
                            self.gga_msg = msg
                        elif sentence_type == 'GSA':
                            self.gsa_msg = msg
                        elif sentence_type == 'RMC':
                            self.rmc_msg = msg
                        elif sentence_type == 'GSV':
                            if line.startswith('$IRGSV'):
                                self.irnss_sats.extend(self.parse_irgsv(line))
                            else:
                                self.other_sats.append(line)
                    else:
                        if line.startswith('$IRGSV'):
                            self.irnss_sats.extend(self.parse_irgsv(line))
                        elif line.startswith('$GPGSV') or line.startswith('$GAGSV'):
                            self.other_sats.append(line)

    def stop(self):
        self.running = False

    def get_status(self):
        with self.lock:
            gga = self.gga_msg
            gsa = self.gsa_msg
            rmc = self.rmc_msg
            irnss = list(self.irnss_sats)
            others = list(self.other_sats)
        fix = self.is_3d_fix()
        fix_type = self.fix_type()
        gsa_prns = self.get_gsa_prns()
        irnss_in_fix = [prn for prn in gsa_prns if prn and prn.startswith('8')]
        lat, lng = self.get_lat_lng()
        speed = self.get_speed()
        hdop, pdop, vdop, num_sats = self.get_accuracy()
        return {
            'fix': fix,
            'fix_type': fix_type,
            'gga': gga,
            'gsa': gsa,
            'rmc': rmc,
            'irnss_in_fix': irnss_in_fix,
            'irnss_sats': irnss,
            'other_sats': others,
            'lat': lat,
            'lng': lng,
            'speed': speed,
            'hdop': hdop,
            'pdop': pdop,
            'vdop': vdop,
            'num_sats': num_sats
        }

class GPSUI:
    def __init__(self, gps_reader):
        self.gps_reader = gps_reader
        self.root = tk.Tk()
        self.root.title("GPS/IRNSS Monitor")
        self.root.geometry("750x600")

        self.status_label = ttk.Label(self.root, text="Waiting for data...", font=("Arial", 14))
        self.status_label.pack(pady=10)

        self.fix_type_label = ttk.Label(self.root, text="Fix Type: ", font=("Arial", 12))
        self.fix_type_label.pack(anchor="w", padx=10)

        self.gga_label = ttk.Label(self.root, text="GGA: ", font=("Arial", 10), wraplength=700, justify="left")
        self.gga_label.pack(anchor="w", padx=10)

        self.gsa_label = ttk.Label(self.root, text="GSA: ", font=("Arial", 10), wraplength=700, justify="left")
        self.gsa_label.pack(anchor="w", padx=10)

        self.latlng_label = ttk.Label(self.root, text="Lat/Lng: ", font=("Arial", 12))
        self.latlng_label.pack(anchor="w", padx=10)

        self.speed_label = ttk.Label(self.root, text="Speed (km/h): ", font=("Arial", 12))
        self.speed_label.pack(anchor="w", padx=10)

        self.accuracy_label = ttk.Label(self.root, text="Accuracy (HDOP/PDOP/VDOP/NumSats): ", font=("Arial", 12))
        self.accuracy_label.pack(anchor="w", padx=10)

        self.irnss_label = ttk.Label(self.root, text="IRNSS PRNs in fix: ", font=("Arial", 10))
        self.irnss_label.pack(anchor="w", padx=10)

        self.irnss_sats_label = ttk.Label(self.root, text="IRNSS Satellites: ", font=("Arial", 10), wraplength=700, justify="left")
        self.irnss_sats_label.pack(anchor="w", padx=10)

        self.other_sats_label = ttk.Label(self.root, text="Other Satellites: ", font=("Arial", 10), wraplength=700, justify="left")
        self.other_sats_label.pack(anchor="w", padx=10)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Start the GPS reading thread
        self.gps_thread = threading.Thread(target=self.gps_reader.read_loop, daemon=True)
        self.gps_thread.start()

        # Start UI update loop
        self.update_ui()

    def update_ui(self):
        status = self.gps_reader.get_status()
        if status['fix']:
            self.status_label.config(text="3D Fix Acquired!", foreground="green")
        else:
            self.status_label.config(text="No 3D Fix", foreground="red")

        self.fix_type_label.config(text=f"Fix Type: {status['fix_type']}")
        self.gga_label.config(text=f"GGA: {status['gga']}")
        self.gsa_label.config(text=f"GSA: {status['gsa']}")
        self.latlng_label.config(text=f"Lat/Lng: {status['lat']}, {status['lng']}")
        self.speed_label.config(text=f"Speed (km/h): {status['speed']:.2f}" if status['speed'] is not None else "Speed (km/h): N/A")
        self.accuracy_label.config(text=f"Accuracy (HDOP/PDOP/VDOP/NumSats): {status['hdop']}, {status['pdop']}, {status['vdop']}, {status['num_sats']}")
        self.irnss_label.config(text=f"IRNSS PRNs in fix: {status['irnss_in_fix']}")
        self.irnss_sats_label.config(text=f"IRNSS Satellites: {status['irnss_sats']}")
        self.other_sats_label.config(text=f"Other Satellites: {status['other_sats']}")

        # IRNSS Signal Indicator
        if status['irnss_sats'] and len(status['irnss_sats']) > 0:
            if not hasattr(self, 'irnss_signal_label'):
                self.irnss_signal_label = ttk.Label(self.root, font=("Arial", 14))
                self.irnss_signal_label.pack(pady=10)
            self.irnss_signal_label.config(text="IRNSS Signal Detected!", foreground="green")
        else:
            if not hasattr(self, 'irnss_signal_label'):
                self.irnss_signal_label = ttk.Label(self.root, font=("Arial", 14))
                self.irnss_signal_label.pack(pady=10)
            self.irnss_signal_label.config(text="No IRNSS Signal", foreground="red")

        self.root.after(1000, self.update_ui)

    def on_close(self):
        self.gps_reader.stop()
        self.root.destroy()

# if __name__ == "__main__":
#     gps_reader = GPSReader(port='COM7', baudrate=9600)
#     app = GPSUI(gps_reader)
#     app.root.mainloop()
