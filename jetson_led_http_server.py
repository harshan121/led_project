import json
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingTCPServer
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


# =========================================================
# JETSON HTTP SERVER SETTINGS
# =========================================================

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000


# =========================================================
# WORKING WLED CONTROLLER NAMES
# =========================================================
# These names are taken from your working code.
#
# controller_1 = strip 1 + strip 2
# controller_2 = strip 3 + strip 4
#
# Each controller has:
#   strip 1: LEDs 0-300
#   strip 2: LEDs 300-600

CONTROLLERS = {
    "controller_1": "wled-a062e4.local",
    "controller_2": "wled-415d60.local",
}


# =========================================================
# LED SETTINGS
# =========================================================

TIMEOUT = 5
BRIGHTNESS = 80

LEDS_PER_STRIP = 300
LEDS_PER_CONTROLLER = 600


# =========================================================
# WLED EFFECT IDS
# =========================================================

FX_SOLID = 0
FX_BLINK = 1
FX_BREATHE = 2
FX_RAINBOW = 9
FX_SCAN = 10
FX_CHASE = 28


# =========================================================
# COLORS
# =========================================================

BLACK = [0, 0, 0]
WHITE = [255, 255, 255]
SOFT_WHITE = [80, 80, 80]

RED = [255, 0, 0]
GREEN = [0, 255, 0]
BLUE = [0, 0, 255]
YELLOW = [255, 180, 0]
ORANGE = [255, 80, 0]
PURPLE = [180, 0, 255]
CYAN = [0, 255, 255]


# =========================================================
# GLOBAL STATE
# =========================================================

LAST_STATE = "none"


# =========================================================
# BASIC HTTP FUNCTIONS
# =========================================================

def make_url(host, endpoint):
    return f"http://{host}{endpoint}"


def send_state(controller_name, payload):
    host = CONTROLLERS[controller_name]

    try:
        response = requests.post(
            make_url(host, "/json/state"),
            json=payload,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return controller_name, True, response.text

    except Exception as error:
        return controller_name, False, str(error)


def get_info(controller_name):
    host = CONTROLLERS[controller_name]

    try:
        response = requests.get(
            make_url(host, "/json/info"),
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return controller_name, True, response.json()

    except Exception as error:
        return controller_name, False, str(error)


def print_result(controller_name, command_name, success, result=""):
    status = "PASS" if success else "FAIL"
    print(f"[{status}] {controller_name} - {command_name}", flush=True)

    if not success:
        print(f"       Error: {result}", flush=True)


def wait(seconds):
    time.sleep(seconds)


# =========================================================
# PARALLEL COMMAND SENDER
# =========================================================

def send_parallel(payloads, command_name):
    all_success = True

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = []

        for controller_name, payload in payloads.items():
            futures.append(
                executor.submit(send_state, controller_name, payload)
            )

        for future in as_completed(futures):
            controller_name, success, result = future.result()
            print_result(controller_name, command_name, success, result)

            if not success:
                all_success = False

    return all_success


# =========================================================
# PAYLOAD BUILDERS
# =========================================================

def two_strip_payload(strip_1_color, strip_2_color, fx=FX_SOLID, speed=128, intensity=128):
    return {
        "on": True,
        "bri": BRIGHTNESS,
        "transition": 0,
        "seg": [
            {
                "id": 0,
                "start": 0,
                "stop": 300,
                "on": True,
                "bri": BRIGHTNESS,
                "col": [[strip_1_color[0], strip_1_color[1], strip_1_color[2]]],
                "fx": fx,
                "sx": speed,
                "ix": intensity,
            },
            {
                "id": 1,
                "start": 300,
                "stop": 600,
                "on": True,
                "bri": BRIGHTNESS,
                "col": [[strip_2_color[0], strip_2_color[1], strip_2_color[2]]],
                "fx": fx,
                "sx": speed,
                "ix": intensity,
            },
        ],
    }


def reset_payload():
    segments = [
        {
            "id": 0,
            "start": 0,
            "stop": 300,
            "on": True,
            "bri": BRIGHTNESS,
            "col": [[0, 0, 0]],
            "fx": FX_SOLID,
            "sx": 128,
            "ix": 128,
        },
        {
            "id": 1,
            "start": 300,
            "stop": 600,
            "on": True,
            "bri": BRIGHTNESS,
            "col": [[0, 0, 0]],
            "fx": FX_SOLID,
            "sx": 128,
            "ix": 128,
        },
    ]

    # Delete old extra segments if WLED has saved them
    for segment_id in range(2, 16):
        segments.append(
            {
                "id": segment_id,
                "stop": 0,
            }
        )

    return {
        "on": True,
        "bri": BRIGHTNESS,
        "transition": 0,
        "seg": segments,
    }


def off_payload():
    return {
        "on": False,
        "transition": 0,
    }


# =========================================================
# GLOBAL LED CONTROL
# =========================================================

def reset_both():
    payloads = {
        "controller_1": reset_payload(),
        "controller_2": reset_payload(),
    }

    return send_parallel(payloads, "reset segments")


def all_off():
    payloads = {
        "controller_1": off_payload(),
        "controller_2": off_payload(),
    }

    return send_parallel(payloads, "off")


def all_same(color, fx=FX_SOLID, speed=128, intensity=128, command_name="all same"):
    payloads = {
        "controller_1": two_strip_payload(color, color, fx, speed, intensity),
        "controller_2": two_strip_payload(color, color, fx, speed, intensity),
    }

    return send_parallel(payloads, command_name)


def four_strip_colors(
    strip_1,
    strip_2,
    strip_3,
    strip_4,
    fx=FX_SOLID,
    speed=128,
    intensity=128,
    command_name="four strip colors",
):
    payloads = {
        "controller_1": two_strip_payload(strip_1, strip_2, fx, speed, intensity),
        "controller_2": two_strip_payload(strip_3, strip_4, fx, speed, intensity),
    }

    return send_parallel(payloads, command_name)


def only_strip(strip_number, color, command_name="only strip"):
    strips = [BLACK, BLACK, BLACK, BLACK]
    strips[strip_number - 1] = color

    return four_strip_colors(
        strips[0],
        strips[1],
        strips[2],
        strips[3],
        command_name=f"{command_name} {strip_number}",
    )


# =========================================================
# CONNECTION TEST
# =========================================================

def test_connections():
    print("\n=================================================", flush=True)
    print("CONNECTION TEST", flush=True)
    print("=================================================", flush=True)

    all_ok = True

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = []

        for controller_name in CONTROLLERS:
            futures.append(executor.submit(get_info, controller_name))

        for future in as_completed(futures):
            controller_name, success, result = future.result()
            print_result(controller_name, "connection", success, result)

            if success:
                print(f"       WLED name: {result.get('name')}", flush=True)
                print(f"       IP: {result.get('ip')}", flush=True)
                print(f"       Version: {result.get('ver')}", flush=True)
                print(f"       Configured LEDs: {result.get('leds', {}).get('count')}", flush=True)
            else:
                all_ok = False

    return all_ok


# =========================================================
# ROBOT COMMANDS
# =========================================================

def robot_startup():
    print("\nROBOT COMMAND: STARTUP", flush=True)
    return all_same(
        BLUE,
        fx=FX_SCAN,
        speed=160,
        intensity=180,
        command_name="startup blue scan",
    )


def robot_idle():
    print("\nROBOT COMMAND: IDLE", flush=True)
    return all_same(
        SOFT_WHITE,
        fx=FX_SOLID,
        command_name="idle soft white",
    )


def robot_serving():
    print("\nROBOT COMMAND: SERVING", flush=True)
    return all_same(
        GREEN,
        fx=FX_SOLID,
        command_name="serving green",
    )


def robot_human_near():
    print("\nROBOT COMMAND: HUMAN_NEAR", flush=True)
    return all_same(
        YELLOW,
        fx=FX_BREATHE,
        speed=120,
        intensity=160,
        command_name="human near yellow breathe",
    )


def robot_alarm():
    print("\nROBOT COMMAND: ALARM", flush=True)
    return all_same(
        RED,
        fx=FX_BLINK,
        speed=190,
        intensity=255,
        command_name="alarm red blink",
    )


def robot_emergency_stop():
    print("\nROBOT COMMAND: EMERGENCY_STOP", flush=True)

    success = True

    for _ in range(6):
        success = all_same(
            RED,
            fx=FX_SOLID,
            command_name="emergency red on",
        ) and success
        wait(0.4)

        success = all_same(
            BLACK,
            fx=FX_SOLID,
            command_name="emergency red off",
        ) and success
        wait(0.25)

    success = all_same(
        RED,
        fx=FX_SOLID,
        command_name="emergency final red",
    ) and success

    return success


def robot_moving_right():
    print("\nROBOT COMMAND: MOVING_RIGHT", flush=True)

    success = True

    for _ in range(3):
        success = only_strip(1, BLUE, "moving right") and success
        wait(0.7)

        success = only_strip(2, BLUE, "moving right") and success
        wait(0.7)

        success = only_strip(3, BLUE, "moving right") and success
        wait(0.7)

        success = only_strip(4, BLUE, "moving right") and success
        wait(0.7)

    success = all_same(BLACK, command_name="moving right clear") and success
    return success


def robot_moving_left():
    print("\nROBOT COMMAND: MOVING_LEFT", flush=True)

    success = True

    for _ in range(3):
        success = only_strip(4, PURPLE, "moving left") and success
        wait(0.7)

        success = only_strip(3, PURPLE, "moving left") and success
        wait(0.7)

        success = only_strip(2, PURPLE, "moving left") and success
        wait(0.7)

        success = only_strip(1, PURPLE, "moving left") and success
        wait(0.7)

    success = all_same(BLACK, command_name="moving left clear") and success
    return success


def robot_turn_left():
    print("\nROBOT COMMAND: TURN_LEFT", flush=True)

    success = True

    for _ in range(5):
        success = four_strip_colors(
            YELLOW,
            YELLOW,
            BLACK,
            BLACK,
            command_name="turn left on",
        ) and success
        wait(0.5)

        success = four_strip_colors(
            BLACK,
            BLACK,
            BLACK,
            BLACK,
            command_name="turn left off",
        ) and success
        wait(0.3)

    return success


def robot_turn_right():
    print("\nROBOT COMMAND: TURN_RIGHT", flush=True)

    success = True

    for _ in range(5):
        success = four_strip_colors(
            BLACK,
            BLACK,
            YELLOW,
            YELLOW,
            command_name="turn right on",
        ) and success
        wait(0.5)

        success = four_strip_colors(
            BLACK,
            BLACK,
            BLACK,
            BLACK,
            command_name="turn right off",
        ) and success
        wait(0.3)

    return success


def robot_processing():
    print("\nROBOT COMMAND: PROCESSING", flush=True)

    patterns = [
        [CYAN, BLACK, BLACK, BLACK],
        [BLACK, CYAN, BLACK, BLACK],
        [BLACK, BLACK, CYAN, BLACK],
        [BLACK, BLACK, BLACK, CYAN],
        [BLACK, BLACK, CYAN, BLACK],
        [BLACK, CYAN, BLACK, BLACK],
    ]

    success = True

    for _ in range(3):
        for pattern in patterns:
            success = four_strip_colors(
                pattern[0],
                pattern[1],
                pattern[2],
                pattern[3],
                command_name="processing wave",
            ) and success
            wait(0.5)

    success = all_same(BLACK, command_name="processing clear") and success
    return success


def robot_success():
    print("\nROBOT COMMAND: SUCCESS", flush=True)

    success = True

    for _ in range(3):
        success = all_same(
            GREEN,
            fx=FX_SOLID,
            command_name="success green",
        ) and success
        wait(0.5)

        success = all_same(
            BLACK,
            fx=FX_SOLID,
            command_name="success off",
        ) and success
        wait(0.3)

    success = all_same(
        GREEN,
        fx=FX_SOLID,
        command_name="success final green",
    ) and success

    return success


def robot_warning():
    print("\nROBOT COMMAND: WARNING", flush=True)

    success = True

    for _ in range(6):
        success = four_strip_colors(
            ORANGE,
            BLACK,
            ORANGE,
            BLACK,
            command_name="warning pattern A",
        ) and success
        wait(0.5)

        success = four_strip_colors(
            BLACK,
            ORANGE,
            BLACK,
            ORANGE,
            command_name="warning pattern B",
        ) and success
        wait(0.5)

    success = all_same(BLACK, command_name="warning clear") and success
    return success


def robot_off():
    print("\nROBOT COMMAND: OFF", flush=True)
    return all_off()


# =========================================================
# ADVANCED PATTERNS
# =========================================================

def pattern_rainbow_all():
    print("\nADVANCED PATTERN: RAINBOW_ALL", flush=True)
    return all_same(
        WHITE,
        fx=FX_RAINBOW,
        speed=120,
        intensity=128,
        command_name="rainbow all",
    )


def pattern_chase_all():
    print("\nADVANCED PATTERN: CHASE_ALL", flush=True)
    return all_same(
        BLUE,
        fx=FX_CHASE,
        speed=180,
        intensity=180,
        command_name="blue chase",
    )


def pattern_scan_all():
    print("\nADVANCED PATTERN: SCAN_ALL", flush=True)
    return all_same(
        WHITE,
        fx=FX_SCAN,
        speed=160,
        intensity=180,
        command_name="white scan",
    )


def pattern_police():
    print("\nADVANCED PATTERN: POLICE", flush=True)

    success = True

    for _ in range(8):
        success = four_strip_colors(
            RED,
            RED,
            BLUE,
            BLUE,
            command_name="police red blue",
        ) and success
        wait(0.4)

        success = four_strip_colors(
            BLUE,
            BLUE,
            RED,
            RED,
            command_name="police blue red",
        ) and success
        wait(0.4)

    success = all_same(BLACK, command_name="police clear") and success
    return success


def pattern_loading_bar():
    print("\nADVANCED PATTERN: LOADING_BAR", flush=True)

    steps = [
        [CYAN, BLACK, BLACK, BLACK],
        [CYAN, CYAN, BLACK, BLACK],
        [CYAN, CYAN, CYAN, BLACK],
        [CYAN, CYAN, CYAN, CYAN],
        [BLACK, BLACK, BLACK, BLACK],
    ]

    success = True

    for _ in range(3):
        for pattern in steps:
            success = four_strip_colors(
                pattern[0],
                pattern[1],
                pattern[2],
                pattern[3],
                command_name="loading bar",
            ) and success
            wait(0.8)

    success = all_same(BLACK, command_name="loading clear") and success
    return success


def pattern_heartbeat():
    print("\nADVANCED PATTERN: HEARTBEAT", flush=True)

    success = True

    for _ in range(5):
        success = all_same(
            RED,
            fx=FX_SOLID,
            command_name="heartbeat strong",
        ) and success
        wait(0.2)

        success = all_same(
            BLACK,
            fx=FX_SOLID,
            command_name="heartbeat off 1",
        ) and success
        wait(0.15)

        success = all_same(
            RED,
            fx=FX_SOLID,
            command_name="heartbeat weak",
        ) and success
        wait(0.2)

        success = all_same(
            BLACK,
            fx=FX_SOLID,
            command_name="heartbeat off 2",
        ) and success
        wait(0.8)

    success = all_same(BLACK, command_name="heartbeat clear") and success
    return success


def pattern_center_out():
    print("\nADVANCED PATTERN: CENTER_OUT", flush=True)

    success = True

    for _ in range(4):
        success = four_strip_colors(
            BLACK,
            GREEN,
            GREEN,
            BLACK,
            command_name="center",
        ) and success
        wait(0.6)

        success = four_strip_colors(
            GREEN,
            BLACK,
            BLACK,
            GREEN,
            command_name="outer",
        ) and success
        wait(0.6)

        success = four_strip_colors(
            BLACK,
            BLACK,
            BLACK,
            BLACK,
            command_name="center out clear",
        ) and success
        wait(0.3)

    return success


def pattern_color_rotation():
    print("\nADVANCED PATTERN: COLOR_ROTATION", flush=True)

    patterns = [
        [RED, GREEN, BLUE, YELLOW],
        [YELLOW, RED, GREEN, BLUE],
        [BLUE, YELLOW, RED, GREEN],
        [GREEN, BLUE, YELLOW, RED],
    ]

    success = True

    for _ in range(4):
        for pattern in patterns:
            success = four_strip_colors(
                pattern[0],
                pattern[1],
                pattern[2],
                pattern[3],
                command_name="color rotation",
            ) and success
            wait(0.7)

    success = all_same(BLACK, command_name="rotation clear") and success
    return success


# =========================================================
# STATE DISPATCHER
# =========================================================

STATE_FUNCTIONS = {
    "startup": robot_startup,
    "idle": robot_idle,
    "serving": robot_serving,
    "human_near": robot_human_near,
    "alarm": robot_alarm,
    "emergency": robot_emergency_stop,
    "emergency_stop": robot_emergency_stop,
    "moving_right": robot_moving_right,
    "moving_left": robot_moving_left,
    "turn_left": robot_turn_left,
    "turn_right": robot_turn_right,
    "processing": robot_processing,
    "success": robot_success,
    "warning": robot_warning,
    "rainbow": pattern_rainbow_all,
    "chase": pattern_chase_all,
    "scan": pattern_scan_all,
    "police": pattern_police,
    "loading": pattern_loading_bar,
    "heartbeat": pattern_heartbeat,
    "center": pattern_center_out,
    "rotation": pattern_color_rotation,
    "off": robot_off,
    "reset": reset_both,
    "test_connections": test_connections,
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
                "  http://JETSON_IP:5000/state/startup\n"
                "  http://JETSON_IP:5000/state/idle\n"
                "  http://JETSON_IP:5000/state/moving_left\n"
                "  http://JETSON_IP:5000/state/moving_right\n"
                "  http://JETSON_IP:5000/state/turn_left\n"
                "  http://JETSON_IP:5000/state/turn_right\n"
                "  http://JETSON_IP:5000/state/serving\n"
                "  http://JETSON_IP:5000/state/human_near\n"
                "  http://JETSON_IP:5000/state/processing\n"
                "  http://JETSON_IP:5000/state/success\n"
                "  http://JETSON_IP:5000/state/warning\n"
                "  http://JETSON_IP:5000/state/alarm\n"
                "  http://JETSON_IP:5000/state/emergency\n"
                "  http://JETSON_IP:5000/state/rainbow\n"
                "  http://JETSON_IP:5000/state/chase\n"
                "  http://JETSON_IP:5000/state/scan\n"
                "  http://JETSON_IP:5000/state/police\n"
                "  http://JETSON_IP:5000/state/loading\n"
                "  http://JETSON_IP:5000/state/heartbeat\n"
                "  http://JETSON_IP:5000/state/center\n"
                "  http://JETSON_IP:5000/state/rotation\n"
                "  http://JETSON_IP:5000/state/off\n\n"
                "Other URLs:\n"
                "  http://JETSON_IP:5000/status\n"
                "  http://JETSON_IP:5000/states\n"
                "  http://JETSON_IP:5000/test_connections\n"
            )
            self.send_text(200, text)
            return

        if path == "/status":
            self.send_json(
                200,
                {
                    "server": "running",
                    "last_state": LAST_STATE,
                    "controllers": CONTROLLERS,
                    "leds_per_strip": LEDS_PER_STRIP,
                    "leds_per_controller": LEDS_PER_CONTROLLER,
                    "brightness": BRIGHTNESS,
                    "available_states": list(STATE_FUNCTIONS.keys()),
                },
            )
            return

        if path == "/states":
            self.send_text(200, available_states_text())
            return

        if path == "/test_connections":
            success = test_connections()

            if success:
                self.send_text(200, "All WLED controllers are reachable.\n")
            else:
                self.send_text(500, "One or more WLED controllers failed.\n")

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


# =========================================================
# MAIN
# =========================================================

def main():
    print("Jetson LED HTTP Server Started", flush=True)
    print("--------------------------------", flush=True)
    print(f"Listening on: http://{SERVER_HOST}:{SERVER_PORT}", flush=True)
    print()
    print("Controller names:", flush=True)

    for controller_name, host in CONTROLLERS.items():
        print(f"  {controller_name}: {host}", flush=True)

    print()
    print("LED setup:", flush=True)
    print("  2 WLED controllers", flush=True)
    print("  4 strips total", flush=True)
    print("  300 LEDs per strip", flush=True)
    print("  600 LEDs per controller", flush=True)
    print("  Brightness:", BRIGHTNESS, flush=True)

    print()
    print("Testing WLED connections now...", flush=True)
    test_connections()

    print()
    print("From laptop, open:", flush=True)
    print("  http://JETSON_IP:5000/status", flush=True)
    print("  http://JETSON_IP:5000/test_connections", flush=True)
    print("  http://JETSON_IP:5000/state/idle", flush=True)
    print("  http://JETSON_IP:5000/state/alarm", flush=True)

    try:
        with ReusableThreadingTCPServer((SERVER_HOST, SERVER_PORT), LEDRequestHandler) as server:
            server.serve_forever()

    except KeyboardInterrupt:
        print("\nServer stopped by user.", flush=True)
        print("Turning LEDs off...", flush=True)
        all_off()


if __name__ == "__main__":
    main()