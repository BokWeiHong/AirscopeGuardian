import sys
import os
import socket
import fcntl
import struct
import subprocess
import math
import json
import yaml
from pathlib import Path
from waveshare_epd import epd2in13_V4
from PIL import Image, ImageDraw, ImageFont
import time
from datetime import datetime

# Resolve project root relative to this file (gpio/ -> project root)
_BASE_DIR = Path(__file__).resolve().parent.parent

def get_ip_address(ifname='wlan0'):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ip = socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,
            struct.pack('256s', ifname[:15].encode('utf-8'))
        )[20:24])
        s.close()
        return ip
    except Exception:
        try:
            s.close()
        except Exception:
            pass

    try:
        s2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s2.connect(('8.8.8.8', 80))
        ip = s2.getsockname()[0]
    except Exception:
        ip = 'No Internet'
    finally:
        try:
            s2.close()
        except Exception:
            pass

    return ip

def check_usb_status():
    try:
        output = subprocess.check_output("lsusb", shell=True).decode("utf-8")
        alfa = "MediaTek" in output or "Realtek" in output or "Atheros" in output
        gps  = "U-Blox" in output or "GNSS" in output or "GPS" in output
        return gps, alfa
    except Exception:
        return False, False

def get_battery_status():
    try:
        base = '/sys/class/power_supply'
        if os.path.isdir(base):
            for name in os.listdir(base):
                path = os.path.join(base, name)
                cap_file = os.path.join(path, 'capacity')
                if os.path.isfile(cap_file):
                    try:
                        with open(cap_file, 'r') as f:
                            val = f.read().strip()
                        if val:
                            return f"{val}%"
                    except Exception:
                        continue
    except Exception:
        pass

    # 2) Try upower if installed
    try:
        out = subprocess.check_output("upower -e", shell=True).decode('utf-8')
        for line in out.splitlines():
            if 'battery' in line.lower():
                try:
                    info = subprocess.check_output(f"upower -i {line}", shell=True).decode('utf-8')
                    for l in info.splitlines():
                        l = l.strip()
                        if l.startswith('percentage:'):
                            return l.split(':', 1)[1].strip()
                except Exception:
                    continue
    except Exception:
        pass

    # 3) Fallback: not available
    return 'N/A'

def get_system_state():
    ip = get_ip_address()
    gps, alfa = check_usb_status()
    battery = get_battery_status()
    return ip, gps, alfa, battery

def check_trackerjacker_active():
    """Returns True if any trackerjacker@ mapping instance is active."""
    try:
        result = subprocess.run(
            ['/bin/systemctl', 'list-units', '--state=active', 'trackerjacker@*', '--no-legend', '--no-pager'],
            check=False, capture_output=True, text=True
        )
        return bool(result.stdout.strip())
    except Exception:
        return False

def check_trackerjacker_track_active():
    """Returns True if the trackerjacker-track (hunt/radar) service is active."""
    try:
        result = subprocess.run(
            ['/bin/systemctl', 'is-active', 'trackerjacker-track.service'],
            check=False, capture_output=True, text=True
        )
        return result.stdout.strip() == 'active'
    except Exception:
        return False

TARGETS_JSON = str(_BASE_DIR / 'app' / 'tracker' / 'saves' / 'targets.json')

def get_targets():
    """Return list of target dicts from the plugin's JSON store."""
    try:
        with open(TARGETS_JSON, 'r') as f:
            data = json.load(f)
        return list(data.values()) if isinstance(data, dict) else []
    except Exception:
        return []

def draw_radar(draw, center_x, center_y, max_radius, targets):
    """Draws a radar UI and places a blip per target scaled by distance."""
    # Concentric rings
    for r_frac in [1.0, 0.6, 0.3]:
        r = int(max_radius * r_frac)
        draw.ellipse(
            (center_x - r, center_y - r, center_x + r, center_y + r),
            outline=0
        )
    # Crosshairs
    draw.line((center_x - max_radius, center_y, center_x + max_radius, center_y), fill=0)
    draw.line((center_x, center_y - max_radius, center_x, center_y + max_radius), fill=0)
    if not targets:
        return
    # Spread targets evenly around the radar at their scaled distances
    scale = max_radius / 10  # 10 m maps to the outer ring
    n = len(targets)
    for i, target in enumerate(targets):
        dist = target.get('dist', 10)
        angle = (360.0 / n) * i + 45
        pixel_dist = min(dist * scale, max_radius)
        blip_x = int(center_x + pixel_dist * math.cos(math.radians(angle)))
        blip_y = int(center_y - pixel_dist * math.sin(math.radians(angle)))
        blip_r = 3
        draw.ellipse(
            (blip_x - blip_r, blip_y - blip_r, blip_x + blip_r, blip_y + blip_r),
            fill=0
        )

def get_wifi_map_stats():
    yaml_path = str(_BASE_DIR / 'app' / 'tracker' / 'saves' / 'wifi_map.yaml')
    try:
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return 0, 0
        ap_count = 0
        device_count = 0
        for ssid, ap_dict in data.items():
            if isinstance(ap_dict, dict):
                for ap_mac, ap_details in ap_dict.items():
                    ap_count += 1
                    if isinstance(ap_details, dict) and isinstance(ap_details.get('devices'), dict):
                        device_count += len(ap_details['devices'])
        return ap_count, device_count
    except Exception:
        return 0, 0

def show_sleep_image(epd, pause=2):
    try:
        epd.Clear(0xFF)

        canvas = Image.new('1', (epd.height, epd.width), 255)
        draw = ImageDraw.Draw(canvas)

        try:
            sleep_img = Image.open(str(_BASE_DIR / 'gpio' / 'img' / 'sleeping.png')).convert('RGBA')
            sleep_img = sleep_img.resize((150, 80), resample=Image.NEAREST)
            canvas.paste(sleep_img, (40, 40), mask=sleep_img)

            draw.text((70, 10), "--- SYSTEM OFF ---", font=font, fill=0)
            draw.text((100, 20), "GG out ~~", font=font, fill=0)
        except IOError:
            print("Sleep image not found. Showing text only.")
            draw.text((70, 10), "--- SYSTEM OFF ---", font=font, fill=0)
            draw.text((100, 25), "GG out ~~", font=font, fill=0)

        epd.display(epd.getbuffer(canvas.rotate(90, expand=True)))
        time.sleep(pause)
        print("Sleep image displayed (left visible).")

        epd.sleep()

    except Exception as e:
        print(f"Error showing sleep image: {e}")
        try:
            epd.Clear(0xFF)
        except Exception:
            pass

try:
    epd = epd2in13_V4.EPD()
    
    try:
        font = ImageFont.truetype(str(_BASE_DIR / 'static' / 'fonts' / 'PressStart2P-Regular.ttf'), 6)
    except IOError:
        print("Custom font not found. Using default.")
        font = ImageFont.load_default()

    try:
        img_gg = Image.open(str(_BASE_DIR / 'gpio' / 'img' / 'gg.png')).convert('RGBA')
        img_gg = img_gg.resize((100, 75), resample=Image.NEAREST)
    except IOError:
        print("Image 'gpio/img/gg.png' not found. Skipping image.")
        img_gg = None

    try:
        img_napping = Image.open(str(_BASE_DIR / 'gpio' / 'img' / 'napping.png')).convert('RGBA')
        img_napping = img_napping.resize((100, 75), resample=Image.NEAREST)
    except IOError:
        print("Image 'gpio/img/napping.png' not found. Skipping image.")
        img_napping = None
    
    try:
        img_happy = Image.open(str(_BASE_DIR / 'gpio' / 'img' / 'happy.png')).convert('RGBA')
        img_happy = img_happy.resize((100, 75), resample=Image.NEAREST)
    except IOError:
        print("Image 'gpio/img/happy.png' not found. Skipping image.")
        img_happy = None

    try:
        img_map1 = Image.open(str(_BASE_DIR / 'gpio' / 'img' / 'mapping1.png')).convert('RGBA')
        img_map1 = img_map1.resize((100, 75), resample=Image.NEAREST)
    except IOError:
        print("Image 'gpio/img/mapping1.png' not found. Skipping image.")
        img_map1 = None
    
    try:
        img_map2 = Image.open(str(_BASE_DIR / 'gpio' / 'img' / 'mapping2.png')).convert('RGBA')
        img_map2 = img_map2.resize((100, 75), resample=Image.NEAREST)
    except IOError:
        print("Image 'gpio/img/mapping2.png' not found. Skipping image.")
        img_map2 = None

    print("Initializing screen...")
    epd.init()
    epd.Clear(0xFF)

    # 1. SETUP CLEAN BASE CANVAS (Only permanent lines and labels)
    base_canvas = Image.new('1', (epd.height, epd.width), 255)
    draw_base = ImageDraw.Draw(base_canvas)

    draw_base.text((5, 5), f"IP:", font=font, fill=0)
    draw_base.text((125, 5), f"Battery:", font=font, fill=0)
    draw_base.text((5, 115), "GPS:", font=font, fill=0)
    draw_base.text((125, 115), "Alfa:", font=font, fill=0)
    draw_base.line((0, 15, epd.height, 15), fill=0, width=1)
    draw_base.line((0, 110, epd.height, 110), fill=0, width=1)

    epd.displayPartBaseImage(epd.getbuffer(base_canvas.rotate(90, expand=True)))

    print("System Monitor Running... (Partial Refresh Active)")
    
    last_state = None
    start_time = time.time()
    is_bored = False
    is_happy = False
    map_frame = False

    # 2. MAIN LOOP
    while True:
        elapsed_time = time.time() - start_time

        current_state = get_system_state()

        should_be_bored = elapsed_time > 10
        should_be_happy = elapsed_time > 20

        if elapsed_time > 30:
            start_time = time.time()

        trackerjacker_active = check_trackerjacker_active()
        trackerjacker_track_active = check_trackerjacker_track_active()

        if (current_state != last_state) or (should_be_bored != is_bored) or (should_be_happy != is_happy) or trackerjacker_active or trackerjacker_track_active:
            ip, gps_ok, alfa_ok, battery_str = current_state

            dynamic_canvas = base_canvas.copy()
            draw_dynamic = ImageDraw.Draw(dynamic_canvas)

            draw_dynamic.text((25, 5), f"{ip}", font=font, fill=0)
            draw_dynamic.text((175, 5), f"{battery_str}", font=font, fill=0)

            if trackerjacker_track_active:
                targets = get_targets()
                closest = min(targets, key=lambda t: t.get('dist', 9999)) if targets else None

                draw_radar(draw_dynamic, 55, 65, 40, targets)

                draw_dynamic.text((110, 25), "== RADAR ==", font=font, fill=0)
                if closest:
                    draw_dynamic.text((110, 37), f"{closest['label']}", font=font, fill=0)
                    draw_dynamic.text((110, 49), f"Dist:{closest['dist']:.1f}m", font=font, fill=0)
                    draw_dynamic.text((110, 61), f"Tgts: {len(targets)}", font=font, fill=0)
                    vendor = (closest.get('vendor') or 'N/A')[:9]
                    draw_dynamic.text((110, 73), vendor, font=font, fill=0)
                else:
                    draw_dynamic.text((110, 37), "Scanning...", font=font, fill=0)
            elif trackerjacker_active:
                ap_count, device_count = get_wifi_map_stats()
                img_map = img_map1 if map_frame else img_map2
                if img_map:
                    dynamic_canvas.paste(img_map, (5, 25), mask=img_map)
                draw_dynamic.text((125, 25), f"Mapping!\nAPs:  {ap_count}\nDevices: {device_count}", font=font, fill=0)
                map_frame = not map_frame
            elif should_be_bored and not should_be_happy:
                if img_napping:
                    dynamic_canvas.paste(img_napping, (5, 25), mask=img_napping)
                draw_dynamic.text((125, 25), "Airscope is \nfeeling bored", font=font, fill=0)
            elif should_be_happy:
                if img_happy:
                    dynamic_canvas.paste(img_happy, (5, 25), mask=img_happy)
                draw_dynamic.text((125, 25), "Airscope is \nfeeling happy", font=font, fill=0)
            else:    
                if img_gg:
                    dynamic_canvas.paste(img_gg, (5, 25), mask=img_gg)
                draw_dynamic.text((125, 25), "Hello, \nAirscope here!", font=font, fill=0)

            # Handle USB Status
            if gps_ok:
                draw_dynamic.text((35, 115), "[OK]", font=font, fill=0)
            else:
                draw_dynamic.text((35, 115), "!ERR!", font=font, fill=0)

            if alfa_ok:
                draw_dynamic.text((160, 115), "[OK]", font=font, fill=0)
            else:
                draw_dynamic.text((160, 115), "!ERR!", font=font, fill=0)

            # Perform the partial refresh
            epd.displayPartial(epd.getbuffer(dynamic_canvas.rotate(90, expand=True)))

            last_state = current_state
            is_bored = should_be_bored
            is_happy = should_be_happy
        time.sleep(1)

except KeyboardInterrupt:    
    print("\nInterrupted by user.")

finally:
    print("Showing sleeping image...")
    try:
        show_sleep_image(epd)
    except Exception as e:
        print(f"Error during exit: {e}")

    print("Exiting now.")
    os._exit(0)