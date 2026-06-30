import json
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingTCPServer

import requests


# =========================================================
# JETSON HTTP SERVER SETTINGS
# =========================================================

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000


# =========================================================
# WLED CONTROLLER SETTINGS
# =========================================================
# Change these IPs if your WLED controller IPs are different.

CONTROLLERS = {
    "controller_1": {
        "url": "http://192.168.0.226/json/state",
        "zones": {
            "zone_1": {"id": 0, "start": 0, "stop": 200},
            "zone_2": {"id": 1, "start": 200, "stop": 400},
            "zone_3": {"id": 2, "start": 400, "stop": 600},
        },
    },
    "controller_2": {
        "url": "http://192.168.0.105/json/state",
        "zones": {
            "zone_4": {"id": 0, "start": 0, "stop": 200},
            "zone_5": {"id": 1, "start": 200, "stop": 400},
            "zone_6": {"id": 2, "start": 400, "stop": 600},
        },
    },
}


# =========================================================
# GENERAL SETTINGS
# =========================================================

BRIGHTNESS = 120
TIMEOUT = 1.0


# =========================================================
# WLED EFFECT IDS
# =========================================================

FX_SOLID = 0
FX_BLINK = 1
FX_BREATH = 2
FX_RAINBOW = 9
FX_SCAN = 10
FX_CHASE = 28


# =========================================================
# COLORS
# =========================================================

RED = [255, 0, 0]
GREEN = [0, 255, 0]
BLUE = [0, 0, 255]
YELLOW = [255, 180, 0]
ORANGE = [255, 80, 0]
WHITE = [255, 255, 255]
OFF = [0, 0, 0]


# =========================================================
# GLOBAL STATE
# =========================================================

LAST_STATE = "none"


# =========================================================
# BASIC WLED FUNCTIONS
# =========================================================

def send_payload(controller_name, payload):
    url = CONTROLLERS[controller_name]["url"]

    try:
        response = requests.post(url, json=payload, timeout=TIMEOUT)

        if response.status_code == 200:
            print(f"[OK] Sent command to {controller_name}", flush=True)
            return True

        print(f"[FAIL] {controller_name}: HTTP {response.status_code}", flush=True)
        print(response.text, flush=True)
        return False

    except requests.exceptions.RequestException as error:
        print(f"[ERROR] Cannot reach {controller_name}: {error}", flush=True)
        return False


def make_segment(segment_info, color, effect=FX_SOLID, speed=128, intensity=128, brightness=255):
    return {
        "id": segment_info["id"],
        "start": segment_info["start"],
        "stop": segment_info["stop"],
        "on": True,
        "bri": brightness,
        "col": [color],
        "fx": effect,
        "sx": speed,
        "ix": intensity,
    }


def set_controller_zones(controller_name, zone_commands):
    controller = CONTROLLERS[controller_name]
    segments = []

    for zone_name, segment_info in controller["zones"].items():
        command = zone_commands.get(zone_name)

        if command is None:
            color = OFF
            effect = FX_SOLID
            speed = 128
            intensity = 128
            brightness = 0
        else:
            color = command.get("color", OFF)
            effect = command.get("effect", FX_SOLID)
            speed = command.get("speed", 128)
            intensity = command.get("intensity", 128)
            brightness = command.get("brightness", 255)

        segments.append(
            make_segment(
                segment_info=segment_info,
                color=color,
                effect=effect,
                speed=speed,
                intensity=intensity,
                brightness=brightness,
            )
        )

    payload = {
        "on": True,
        "bri": BRIGHTNESS,
        "seg": segments,
    }

    return send_payload(controller_name, payload)


def set_all_zones(zone_commands):
    success = True

    for controller_name in CONTROLLERS:
        result = set_controller_zones(controller_name, zone_commands)
        success = success and result

    return success


def turn_everything_off():
    payload = {
        "on": False,
        "bri": 0,
    }

    success = True

    for controller_name in CONTROLLERS:
        result = send_payload(controller_name, payload)
        success = success and result

    return success


# =========================================================
# ROBOT LED STATES
# =========================================================

def state_idle():
    commands = {
        "zone_1": {"color": BLUE, "effect": FX_BREATH, "speed": 80, "intensity": 120},
        "zone_2": {"color": BLUE, "effect": FX_BREATH, "speed": 80, "intensity": 120},
        "zone_3": {"color": BLUE, "effect": FX_BREATH, "speed": 80, "intensity": 120},
        "zone_4": {"color": BLUE, "effect": FX_BREATH, "speed": 80, "intensity": 120},
        "zone_5": {"color": BLUE, "effect": FX_BREATH, "speed": 80, "intensity": 120},
        "zone_6": {"color": BLUE, "effect": FX_BREATH, "speed": 80, "intensity": 120},
    }

    return set_all_zones(commands)


def state_moving_left():
    commands = {
        "zone_1": {"color": YELLOW, "effect": FX_CHASE, "speed": 180, "intensity": 150},
        "zone_2": {"color": YELLOW, "effect": FX_CHASE, "speed": 180, "intensity": 150},
        "zone_3": {"color": OFF, "effect": FX_SOLID, "brightness": 0},
        "zone_4": {"color": OFF, "effect": FX_SOLID, "brightness": 0},
        "zone_5": {"color": YELLOW, "effect": FX_CHASE, "speed": 180, "intensity": 150},
        "zone_6": {"color": YELLOW, "effect": FX_CHASE, "speed": 180, "intensity": 150},
    }

    return set_all_zones(commands)


def state_moving_right():
    commands = {
        "zone_1": {"color": OFF, "effect": FX_SOLID, "brightness": 0},
        "zone_2": {"color": YELLOW, "effect": FX_CHASE, "speed": 180, "intensity": 150},
        "zone_3": {"color": YELLOW, "effect": FX_CHASE, "speed": 180, "intensity": 150},
        "zone_4": {"color": YELLOW, "effect": FX_CHASE, "speed": 180, "intensity": 150},
        "zone_5": {"color": YELLOW, "effect": FX_CHASE, "speed": 180, "intensity": 150},
        "zone_6": {"color": OFF, "effect": FX_SOLID, "brightness": 0},
    }

    return set_all_zones(commands)


def state_serving():
    commands = {
        "zone_1": {"color": GREEN, "effect": FX_SOLID},
        "zone_2": {"color": GREEN, "effect": FX_SOLID},
        "zone_3": {"color": GREEN, "effect": FX_SOLID},
        "zone_4": {"color": GREEN, "effect": FX_SOLID},
        "zone_5": {"color": GREEN, "effect": FX_SOLID},
        "zone_6": {"color": GREEN, "effect": FX_SOLID},
    }

    return set_all_zones(commands)


def state_human_near():
    commands = {
        "zone_1": {"color": ORANGE, "effect": FX_BREATH, "speed": 120, "intensity": 180},
        "zone_2": {"color": ORANGE, "effect": FX_BREATH, "speed": 120, "intensity": 180},
        "zone_3": {"color": ORANGE, "effect": FX_BREATH, "speed": 120, "intensity": 180},
        "zone_4": {"color": ORANGE, "effect": FX_BREATH, "speed": 120, "intensity": 180},
        "zone_5": {"color": ORANGE, "effect": FX_BREATH, "speed": 120, "intensity": 180},
        "zone_6": {"color": ORANGE, "effect": FX_BREATH, "speed": 120, "intensity": 180},
    }

    return set_all_zones(commands)


def state_alarm():
    commands = {
        "zone_1": {"color": RED, "effect": FX_BLINK, "speed": 220, "intensity": 255},
        "zone_2": {"color": RED, "effect": FX_BLINK, "speed": 220, "intensity": 255},
        "zone_3": {"color": RED, "effect": FX_BLINK, "speed": 220, "intensity": 255},
        "zone_4": {"color": RED, "effect": FX_BLINK, "speed": 220, "intensity": 255},
        "zone_5": {"color": RED, "effect": FX_BLINK, "speed": 220, "intensity": 255},
        "zone_6": {"color": RED, "effect": FX_BLINK, "speed": 220, "intensity": 255},
    }

    return set_all_zones(commands)


def state_rainbow():
    commands = {
        "zone_1": {"color": WHITE, "effect": FX_RAINBOW, "speed": 120, "intensity": 150},
        "zone_2": {"color": WHITE, "effect": FX_RAINBOW, "speed": 120, "intensity": 150},
        "zone_3": {"color": WHITE, "effect": FX_RAINBOW, "speed": 120, "intensity": 150},
        "zone_4": {"color": WHITE, "effect": FX_RAINBOW, "speed": 120, "intensity": 150},
        "zone_5": {"color": WHITE, "effect": FX_RAINBOW, "speed": 120, "intensity": 150},
        "zone_6": {"color": WHITE, "effect": FX_RAINBOW, "speed": 120, "intensity": 150},
    }

    return set_all_zones(commands)


def state_test_zones():
    zones = ["zone_1", "zone_2", "zone_3", "zone_4", "zone_5", "zone_6"]

    for active_zone in zones:
        print(f"Testing {active_zone}", flush=True)

        commands = {}

        for zone in zones:
            if zone == active_zone:
                commands[zone] = {"color": WHITE, "effect": FX_SOLID}
            else:
                commands[zone] = {"color": OFF, "effect": FX_SOLID, "brightness": 0}

        set_all_zones(commands)
        time.sleep(1.5)

    return turn_everything_off()


# =========================================================
# STATE DISPATCHER
# =========================================================

STATE_FUNCTIONS = {
    "idle": state_idle,
    "moving_left": state_moving_left,
    "moving_right": state_moving_right,
    "serving": state_serving,
    "human_near": state_human_near,
    "alarm": state_alarm,
    "rainbow": state_rainbow,
    "test_zones": state_test_zones,
    "off": turn_everything_off,
}


def run_state(state_name):
    global LAST_STATE

    state_name = state_name.strip().lower()

    if state_name not in STATE_FUNCTIONS:
        return False, f"Unknown state: {state_name}"

    print(f"\nNew command received: {state_name}", flush=True)

    success = STATE_FUNCTIONS[state_name]()

    if success:
        LAST_STATE = state_name
        return True, f"State changed to: {state_name}"

    return False, f"State command sent, but one or more WLED controllers failed: {state_name}"


def available_states_text():
    text = "Available states:\n"

    for state in STATE_FUNCTIONS:
        text += f"  {state}\n"

    return text


# =========================================================
# HTTP SERVER
# =========================================================

class LEDRequestHandler(BaseHTTPRequestHandler):
    def send_text(self, status_code, text):
        encoded = text.encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_json(self, status_code, data):
        encoded = json.dumps(data, indent=2).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path == "/":
            text = (
                "Jetson LED HTTP Server is running.\n\n"
                "Use these URLs from your laptop:\n"
                "  http://JETSON_IP:5000/state/idle\n"
                "  http://JETSON_IP:5000/state/moving_left\n"
                "  http://JETSON_IP:5000/state/moving_right\n"
                "  http://JETSON_IP:5000/state/serving\n"
                "  http://JETSON_IP:5000/state/human_near\n"
                "  http://JETSON_IP:5000/state/alarm\n"
                "  http://JETSON_IP:5000/state/rainbow\n"
                "  http://JETSON_IP:5000/state/test_zones\n"
                "  http://JETSON_IP:5000/state/off\n\n"
                "Other URLs:\n"
                "  http://JETSON_IP:5000/status\n"
                "  http://JETSON_IP:5000/states\n"
            )
            self.send_text(200, text)
            return

        if path == "/status":
            self.send_json(
                200,
                {
                    "server": "running",
                    "last_state": LAST_STATE,
                    "available_states": list(STATE_FUNCTIONS.keys()),
                    "wled_controllers": list(CONTROLLERS.keys()),
                },
            )
            return

        if path == "/states":
            self.send_text(200, available_states_text())
            return

        if path.startswith("/state/"):
            state_name = path.replace("/state/", "", 1).strip()
            state_name = urllib.parse.unquote(state_name)

            success, message = run_state(state_name)

            if success:
                self.send_text(200, message + "\n")
            else:
                self.send_text(400, message + "\n\n" + available_states_text())
            return

        if path == "/state":
            if "name" not in query:
                self.send_text(
                    400,
                    "Missing state name.\nExample: /state?name=alarm\n",
                )
                return

            state_name = query["name"][0]
            success, message = run_state(state_name)

            if success:
                self.send_text(200, message + "\n")
            else:
                self.send_text(400, message + "\n\n" + available_states_text())
            return

        self.send_text(404, "Not found.\n")

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path != "/state":
            self.send_text(404, "Not found. Use POST /state\n")
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8").strip()

        state_name = ""

        try:
            data = json.loads(body)
            state_name = data.get("state", "")
        except json.JSONDecodeError:
            state_name = body

        if not state_name:
            self.send_text(
                400,
                "Missing state.\n"
                "Send JSON like: {\"state\": \"alarm\"}\n"
                "Or send plain text: alarm\n",
            )
            return

        success, message = run_state(state_name)

        if success:
            self.send_text(200, message + "\n")
        else:
            self.send_text(400, message + "\n\n" + available_states_text())

    def log_message(self, format, *args):
        print(f"[HTTP] {self.address_string()} - {format % args}", flush=True)


class ReusableThreadingTCPServer(ThreadingTCPServer):
    allow_reuse_address = True


def main():
    print("Jetson LED HTTP Server Started", flush=True)
    print("--------------------------------", flush=True)
    print(f"Listening on: http://{SERVER_HOST}:{SERVER_PORT}", flush=True)
    print("\nAvailable states:", flush=True)

    for state in STATE_FUNCTIONS:
        print(f"  {state}", flush=True)

    print("\nFrom laptop, open:", flush=True)
    print("  http://JETSON_IP:5000/status", flush=True)
    print("  http://JETSON_IP:5000/state/alarm", flush=True)

    try:
        with ReusableThreadingTCPServer((SERVER_HOST, SERVER_PORT), LEDRequestHandler) as server:
            server.serve_forever()

    except KeyboardInterrupt:
        print("\nServer stopped by user.", flush=True)
        print("Turning LEDs off...", flush=True)
        turn_everything_off()


if __name__ == "__main__":
    main()