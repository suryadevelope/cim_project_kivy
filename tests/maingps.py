from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty, ListProperty, NumericProperty
from kivy.core.window import Window
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.tab import MDTabsBase
from kivymd.uix.progressbar import MDProgressBar
from kivy_garden.mapview import MapView, MapMarker
from kivy.factory import Factory
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse

Window.size = (900, 700)

# --- Satellite Bar Widget ---
class SatBar(MDBoxLayout):
    prn = StringProperty()
    snr = NumericProperty()
    system = StringProperty()

# --- Tab Classes ---
class StatusTab(MDBoxLayout, MDTabsBase):
    pass

class SatellitesTab(MDBoxLayout, MDTabsBase):
    pass

class MapTab(MDBoxLayout, MDTabsBase):
    pass

# --- Accuracy Circle Widget ---
class AccuracyCircle(Widget):
    def __init__(self, lat, lon, accuracy_m, mapview, **kwargs):
        super().__init__(**kwargs)
        self.lat = lat
        self.lon = lon
        self.accuracy_m = accuracy_m
        self.mapview = mapview
        self.size_hint = (None, None)
        self.update_circle()

    def update_circle(self, *args):
        # Convert accuracy in meters to pixels (approximate, depends on zoom)
        # For a more accurate conversion, use mapview.get_window_xy_from if available
        scale = 2.0  # You may need to tune this scaling factor
        pixel_radius = self.accuracy_m * scale
        self.size = (pixel_radius * 2, pixel_radius * 2)
        # Get pixel position of lat/lon on the map
        if hasattr(self.mapview, 'get_window_xy_from'):
            x, y = self.mapview.get_window_xy_from(self.lat, self.lon, self.mapview.zoom)
            self.pos = (x - pixel_radius, y - pixel_radius)
        if self.canvas is not None:
            self.canvas.clear()
            with self.canvas:
                Color(0, 0, 1, 0.2)  # Semi-transparent blue
                Ellipse(pos=(0, 0), size=(pixel_radius * 2, pixel_radius * 2))

Builder.load_string('''
<SatBar>:
    orientation: "horizontal"
    size_hint_y: None
    height: "32dp"
    MDLabel:
        text: root.prn
        size_hint_x: 0.2
    MDProgressBar:
        value: root.snr
        max: 60
        size_hint_x: 0.7
        color: (0, 0.7, 0, 1) if root.system == "IRNSS" else (0, 0.5, 1, 1)
    MDLabel:
        text: f"{int(root.snr)}"
        size_hint_x: 0.1

<StatusTab>:
    orientation: "vertical"
    padding: "12dp"
    spacing: "8dp"
    MDLabel:
        text: app.status_text
        font_style: "H6"
        halign: "center"
    MDLabel:
        text: app.fix_type
        halign: "center"
    MDLabel:
        text: app.latlng
        halign: "center"
    MDLabel:
        text: app.speed
        halign: "center"
    MDLabel:
        text: app.accuracy
        halign: "center"
    MDLabel:
        text: app.irnss_signal
        font_style: "H6"
        halign: "center"
        theme_text_color: "Custom"
        text_color: (0, 0.7, 0, 1) if "Detected" in app.irnss_signal else (1, 0, 0, 1)

<SatellitesTab>:
    orientation: "vertical"
    padding: "12dp"
    spacing: "8dp"
    MDLabel:
        text: "IRNSS Satellites"
        font_style: "Subtitle1"
    ScrollView:
        MDBoxLayout:
            id: irnss_box
            orientation: "vertical"
            size_hint_y: None
            height: self.minimum_height
    MDLabel:
        text: "Other Satellites"
        font_style: "Subtitle1"
    ScrollView:
        MDBoxLayout:
            id: other_box
            orientation: "vertical"
            size_hint_y: None
            height: self.minimum_height

<MapTab>:
    orientation: "vertical"
    padding: "0dp"
    MapView:
        id: mapview
        lat: app.map_lat
        lon: app.map_lon
        zoom: 15
''')

class GPSMDApp(MDApp):
    status_text = StringProperty("Waiting for data...")
    fix_type = StringProperty("")
    latlng = StringProperty("")
    speed = StringProperty("")
    accuracy = StringProperty("")
    irnss_signal = StringProperty("")
    map_lat = NumericProperty(0.0)
    map_lon = NumericProperty(0.0)

    def __init__(self, gps_reader, **kwargs):
        super().__init__(**kwargs)
        self.gps_reader = gps_reader
        self.lat_buffer = []
        self.lon_buffer = []
        self.buffer_size = 5  # Moving average window size
        self.accuracy_circle = None
        self.map_marker = None  # <-- Added: single marker instance

    def build(self):
        from kivymd.uix.tab import MDTabs
        from kivymd.uix.boxlayout import MDBoxLayout

        self.tabs = MDTabs()
        self.status_tab = StatusTab(title="Status")
        self.sat_tab = SatellitesTab(title="Satellites")
        self.map_tab = MapTab(title="Map")
        self.tabs.add_widget(self.status_tab)
        self.tabs.add_widget(self.sat_tab)
        self.tabs.add_widget(self.map_tab)
        root = MDBoxLayout(orientation="vertical")
        root.add_widget(self.tabs)
        return root

    def on_start(self):
        import threading
        self.gps_thread = threading.Thread(target=self.gps_reader.read_loop, daemon=True)
        self.gps_thread.start()
        Clock.schedule_interval(self.update_ui, 1)

    def filter_position(self, lat, lon):
        if lat is not None and lon is not None:
            self.lat_buffer.append(lat)
            self.lon_buffer.append(lon)
            if len(self.lat_buffer) > self.buffer_size:
                self.lat_buffer.pop(0)
                self.lon_buffer.pop(0)
            avg_lat = sum(self.lat_buffer) / len(self.lat_buffer)
            avg_lon = sum(self.lon_buffer) / len(self.lon_buffer)
            return avg_lat, avg_lon
        return lat, lon

    def update_ui(self, dt):
        status = self.gps_reader.get_status()
        self.status_text = "3D Fix Acquired!" if status['fix'] else "No 3D Fix"
        self.fix_type = f"Fix Type: {status['fix_type']}"
        self.latlng = f"Lat/Lng: {status['lat']}, {status['lng']}"
        self.speed = f"Speed (km/h): {status['speed']:.2f}" if status['speed'] is not None else "Speed (km/h): N/A"
        self.accuracy = f"Accuracy (HDOP/PDOP/VDOP/NumSats): {status['hdop']}, {status['pdop']}, {status['vdop']}, {status['num_sats']}"
        self.irnss_signal = "IRNSS Signal Detected!" if status['irnss_sats'] and len(status['irnss_sats']) > 0 else "No IRNSS Signal"

        # Satellite bars
        irnss_box = self.sat_tab.ids.irnss_box
        other_box = self.sat_tab.ids.other_box
        irnss_box.clear_widgets()
        other_box.clear_widgets()
        for sat in status['irnss_sats']:
            snr = 0
            try:
                snr = float(sat.get('snr', 0) or 0)
            except Exception:
                snr = 0
            irnss_box.add_widget(SatBar(prn=sat.get('prn', ''), snr=snr, system="IRNSS"))
        for line in status['other_sats']:
            other_box.add_widget(SatBar(prn=line[:10], snr=0, system="Other"))

        # Map - Only update if 3D fix and HDOP < 2.0
        try:
            lat = float(status['lat']) if status['lat'] else 0.0
            lon = float(status['lng']) if status['lng'] else 0.0
            hdop = status['hdop']
            if status['fix'] and hdop is not None and hdop < 2.0:
                lat, lon = self.filter_position(lat, lon)
                self.map_lat = lat
                self.map_lon = lon
                mapview = self.map_tab.ids.mapview

                # Only one marker: create if needed, else move
                if not self.map_marker:
                    self.map_marker = MapMarker(lat=lat, lon=lon)
                    mapview.add_marker(self.map_marker)
                else:
                    self.map_marker.lat = lat
                    self.map_marker.lon = lon

                mapview.center_on(lat, lon)

                # Add/update accuracy circle
                accuracy_m = 10  # Default if not available
                if status['hdop'] is not None and status['hdop'] > 0:
                    accuracy_m = status['hdop'] * 5  # Rough estimate

                # Remove previous circle if it exists
                if self.accuracy_circle:
                    mapview.remove_widget(self.accuracy_circle)
                self.accuracy_circle = AccuracyCircle(lat, lon, accuracy_m, mapview)
                mapview.add_widget(self.accuracy_circle)
            else:
                # Optionally, you can display a warning or skip updating the map
                pass
        except Exception as e:
            print("Map update error:", e)  # For debugging

    def on_stop(self):
        self.gps_reader.stop()

if __name__ == "__main__":
    from gpstest1 import GPSReader  # or paste your class here
    gps_reader = GPSReader(port='COM7', baudrate=9600)
    GPSMDApp(gps_reader).run()
