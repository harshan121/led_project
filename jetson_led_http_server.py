import json
import time
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingTCPServer
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000

CONTROLLERS = {
    "controller_1": "wled-a062e4.local",
    "controller_2": "wled-415d60.local",
}

TIMEOUT = 5
BRIGHTNESS = 80

FX_SOLID = 0
FX_BLINK = 1
FX_BREATHE = 2
FX_RAINBOW = 9
FX_SCAN = 10
FX_CHASE = 28

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

LAST_STATE = "none"

animation_stop_event = threading.Event()
animation_thread = None
animation_lock = threading.Lock()


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
        response = requests.get(make_url(host, "/json/info"), timeout=TIMEOUT)
        response.raise_for_status()
        return controller_name, True, response.json()
    except Exception as error:
        return controller_name, False, str(error)


def print_result(controller_name, command_name, success, result=""):
    status = "PASS" if success else "FAIL"
    print(f"[{status}] {controller_name} - {command_name}", flush=True)

    if not success:
        print(f"       Error: {result}", flush=True)


def send_parallel(payloads, command_name):
    all_success = True

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = []

        for controller_name, payload in payloads.items():
            futures.append(executor.submit(send_state, controller_name, payload))

        for future in as_completed(futures):
            controller_name, success, result = future.result()
            print_result(controller_name, command_name, success, result)

            if not success:
                all_success = False

    return all_success


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

    for segment_id in range(2, 16):
        segments.append({"id": segment_id, "stop": 0})

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


def reset_both():
    payloads = {
        "controller_1": reset_payload(),
        "controller_2": reset_payload(),
    }
    return send_parallel(payloads, "reset")


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


def four_strip_colors(strip_1, strip_2, strip_3, strip_4, fx=FX_SOLID, speed=128, intensity=128, command_name="four strip colors"):
    payloads = {
        "controller_1": two_strip_payload(strip_1, strip_2, fx, speed, intensity),
        "controller_2": two_strip_payload(strip_3, strip_4, fx, speed, intensity),
    }
    return send_parallel(payloads, command_name)


def stop_animation():
    global animation_thread

    with animation_lock:
        animation_stop_event.set()

        if animation_thread is not None and animation_thread.is_alive():
            animation_thread.join(timeout=2)

        animation_thread = None
        animation_stop_event.clear()


def start_animation(animation_function):
    global animation_thread

    stop_animation()

    animation_thread = threading.Thread(
        target=animation_function,
        daemon=True,
    )
    animation_thread.start()


def moving_right_loop():
    print("Starting continuous moving_right animation", flush=True)

    pattern = [
        [BLUE, BLACK, BLACK, BLACK],
        [BLACK, BLUE, BLACK, BLACK],
        [BLACK, BLACK, BLUE, BLACK],
        [BLACK, BLACK, BLACK, BLUE],
    ]

    while not animation_stop_event.is_set():
        for step in pattern:
            if animation_stop_event.is_set():
                break

            four_strip_colors(
                step[0],
                step[1],
                step[2],
                step[3],
                fx=FX_SOLID,
                command_name="moving_right step",
            )
            time.sleep(0.45)

    print("Stopped moving_right animation", flush=True)


def moving_left_loop():
    print("Starting continuous moving_left animation", flush=True)

    pattern = [
        [BLACK, BLACK, BLACK, PURPLE],
        [BLACK, BLACK, PURPLE, BLACK],
        [BLACK, PURPLE, BLACK, BLACK],
        [PURPLE, BLACK, BLACK, BLACK],
    ]

    while not animation_stop_event.is_set():
        for step in pattern:
            if animation_stop_event.is_set():
                break

            four_strip_colors(
                step[0],
                step[1],
                step[2],
                step[3],
                fx=FX_SOLID,
                command_name="moving_left step",
            )
            time.sleep(0.45)

    print("Stopped moving_left animation", flush=True)


def test_connections():
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


def robot_idle():
    return all_same(SOFT_WHITE, FX_SOLID, command_name="idle")


def robot_serving():
    return all_same(GREEN, FX_SOLID, command_name="serving")


def robot_human_near():
    return all_same(YELLOW, FX_BREATHE, speed=120, intensity=160, command_name="human_near")


def robot_alarm():
    return all_same(RED, FX_BLINK, speed=190, intensity=255, command_name="alarm")


def robot_turn_left():
    return four_strip_colors(
        YELLOW,
        YELLOW,
        BLACK,
        BLACK,
        fx=FX_BLINK,
        speed=160,
        intensity=255,
        command_name="turn_left",
    )


def robot_turn_right():
    return four_strip_colors(
        BLACK,
        BLACK,
        YELLOW,
        YELLOW,
        fx=FX_BLINK,
        speed=160,
        intensity=255,
        command_name="turn_right",
    )


def robot_processing():
    return all_same(CYAN, FX_SCAN, speed=160, intensity=180, command_name="processing")


def robot_success():
    return all_same(GREEN, FX_BREATHE, speed=100, intensity=180, command_name="success")


def robot_warning():
    return four_strip_colors(
        ORANGE,
        BLACK,
        ORANGE,
        BLACK,
        fx=FX_BLINK,
        speed=150,
        intensity=255,
        command_name="warning",
    )


def robot_startup():
    return all_same(BLUE, FX_SCAN, speed=160, intensity=180, command_name="startup")


def pattern_rainbow():
    return all_same(WHITE, FX_RAINBOW, speed=120, intensity=128, command_name="rainbow")


def pattern_chase():
    return all_same(BLUE, FX_CHASE, speed=180, intensity=180, command_name="chase")


def pattern_scan():
    return all_same(WHITE, FX_SCAN, speed=160, intensity=180, command_name="scan")


def command_moving_right():
    start_animation(moving_right_loop)
    return True


def command_moving_left():
    start_animation(moving_left_loop)
    return True


STATE_FUNCTIONS = {
    "startup": robot_startup,
    "idle": robot_idle,
    "serving": robot_serving,
    "human_near": robot_human_near,
    "alarm": robot_alarm,
    "moving_right": command_moving_right,
    "moving_left": command_moving_left,
    "turn_left": robot_turn_left,
    "turn_right": robot_turn_right,
    "processing": robot_processing,
    "success": robot_success,
    "warning": robot_warning,
    "rainbow": pattern_rainbow,
    "chase": pattern_chase,
    "scan": pattern_scan,
    "reset": reset_both,
    "off": all_off,
    "test_connections": test_connections,
}


def run_state(state_name):
    global LAST_STATE

    state_name = state_name.strip().lower()

    if state_name not in STATE_FUNCTIONS:
        return False, f"Unknown state: {state_name}"

    print(f"\nNew command received: {state_name}", flush=True)

    if state_name in ["reset", "off", "test_connections"]:
        stop_animation()

        if state_name == "reset":
            success = reset_both()
        elif state_name == "off":
            success = all_off()
        else:
            success = test_connections()

    elif state_name in ["moving_right", "moving_left"]:
        reset_both()
        success = STATE_FUNCTIONS[state_name]()

    else:
        stop_animation()
        reset_both()
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
            self.send_text(
                200,
                "Jetson LED server running.\n"
                "Use /states, /status, /reset, /off, or /state/<command>\n",
            )
            return

        if path == "/status":
            self.send_json(
                200,
                {
                    "server": "running",
                    "last_state": LAST_STATE,
                    "controllers": CONTROLLERS,
                    "jetson_ip": "192.168.0.214",
                    "available_states": list(STATE_FUNCTIONS.keys()),
                },
            )
            return

        if path == "/states":
            self.send_text(200, available_states_text())
            return

        if path == "/reset":
            success, message = run_state("reset")
            self.send_text(200 if success else 500, message + "\n")
            return

        if path == "/off":
            success, message = run_state("off")
            self.send_text(200 if success else 500, message + "\n")
            return

        if path == "/test_connections":
            success = test_connections()
            self.send_text(
                200 if success else 500,
                "All WLED controllers reachable.\n" if success else "One or more WLED controllers failed.\n",
            )
            return

        if path.startswith("/state/"):
            state_name = path.replace("/state/", "", 1).strip()
            state_name = urllib.parse.unquote(state_name)

            success, message = run_state(state_name)
            self.send_text(200 if success else 400, message + "\n")
            return

        if path == "/state":
            if "name" not in query:
                self.send_text(400, "Missing state name. Example: /state?name=alarm\n")
                return

            state_name = query["name"][0]
            success, message = run_state(state_name)
            self.send_text(200 if success else 400, message + "\n")
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

        try:
            data = json.loads(body)
            state_name = data.get("state", "")
        except json.JSONDecodeError:
            state_name = body

        if not state_name:
            self.send_text(400, "Missing state.\n")
            return

        success, message = run_state(state_name)
        self.send_text(200 if success else 400, message + "\n")

    def log_message(self, format, *args):
        print(f"[HTTP] {self.address_string()} - {format % args}", flush=True)


class ReusableThreadingTCPServer(ThreadingTCPServer):
    allow_reuse_address = True


def main():
    print("Jetson LED HTTP Server Started", flush=True)
    print("--------------------------------", flush=True)
    print("Open from laptop:", flush=True)
    print("  http://192.168.0.214:5000/status", flush=True)
    print("  http://192.168.0.214:5000/states", flush=True)
    print("  http://192.168.0.214:5000/state/moving_right", flush=True)
    print("  http://192.168.0.214:5000/state/moving_left", flush=True)
    print("  http://192.168.0.214:5000/reset", flush=True)
    print("  http://192.168.0.214:5000/off", flush=True)

    print("\nTesting WLED connections...", flush=True)
    test_connections()

    try:
        with ReusableThreadingTCPServer((SERVER_HOST, SERVER_PORT), LEDRequestHandler) as server:
            server.serve_forever()

    except KeyboardInterrupt:
        print("\nServer stopped. Turning LEDs off...", flush=True)
        stop_animation()
        all_off()


if __name__ == "__main__":
    main()