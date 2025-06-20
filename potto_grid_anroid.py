import os
import shutil
import logging
import exifread
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("photo_sorter.log", encoding='utf-8'), logging.StreamHandler()]
)

def get_decimal_from_dms(dms, ref):
    degrees, minutes, seconds = [v.num / v.den for v in dms]
    dec = degrees + minutes/60 + seconds/3600
    return -dec if ref in ['S', 'W'] else dec


def extract_gps_exifread(path):
    with open(path, 'rb') as f:
        tags = exifread.process_file(f, details=False)
    try:
        lat = get_decimal_from_dms(tags['GPS GPSLatitude'].values, tags['GPS GPSLatitudeRef'].values)
        lon = get_decimal_from_dms(tags['GPS GPSLongitude'].values, tags['GPS GPSLongitudeRef'].values)
        return lat, lon
    except KeyError:
        return None


def extract_gps_pillow(path):
    img = Image.open(path)
    info = img._getexif()
    if not info:
        return None
    gps_info = {GPSTAGS.get(k, k): v for k, v in info.get(34853, {}).items()}
    if 'GPSLatitude' in gps_info and 'GPSLongitude' in gps_info:
        return (
            get_decimal_from_dms(gps_info['GPSLatitude'], gps_info['GPSLatitudeRef']),
            get_decimal_from_dms(gps_info['GPSLongitude'], gps_info['GPSLongitudeRef'])
        )
    return None


def extract_gps(path):
    gps = extract_gps_exifread(path)
    if gps:
        logging.info(f"exifread GPS OK: {gps}")
        return gps
    gps = extract_gps_pillow(path)
    if gps:
        logging.info(f"Pillow GPS OK: {gps}")
        return gps
    logging.warning(f"No GPS found: {path}")
    return None


def reverse_geocode(lat, lon):
    geolocator = Nominatim(user_agent="geo_photo_sorter")
    try:
        loc = geolocator.reverse((lat, lon), language='ko')
        addr = loc.raw.get('address', {}) if loc else {}

        road = addr.get('road')
        city = addr.get('city') or addr.get('state') or ""
        district = addr.get('suburb') or addr.get('town') or addr.get('county') or ""

        if road:
            folder_name = f"{city}_{district}_{road}"
        elif city or district:
            folder_name = f"{city}_{district}"
        else:
            folder_name = f"{lat}_{lon}"

        return folder_name.replace(" ", "_")

    except GeocoderTimedOut:
        logging.warning(f"Geocoder timeout for: {lat}, {lon}")
        return f"{lat}_{lon}"
    except Exception as e:
        logging.error(f"Reverse geocode error: {e}")
        return f"{lat}_{lon}"


def move_photo(path, base):
    gps = extract_gps(path)
    folder = reverse_geocode(*gps) if gps else "No_GPS"
    target = os.path.join(base, folder)
    os.makedirs(target, exist_ok=True)
    shutil.move(path, os.path.join(target, os.path.basename(path)))
    logging.info(f"Moved: {folder} ← {os.path.basename(path)}")



def sort_photos(folder):
    logging.info(f"Start: {folder}")
    for f in os.listdir(folder):
        if f.lower().endswith(".jpg"):
            move_photo(os.path.join(folder, f), folder)
    logging.info("Completed")

if __name__ == "__main__":
    print("📂 정리할 사진 폴더 경로를 입력하세요 (예: /Users/xxx/Downloads/photos)")
    input_path = input("경로 입력 (Enter로 기본값 사용): ").strip()

    if not input_path:
        input_path = "/Users/hyunchu/git/python/sample_potto_android"

    if not os.path.exists(input_path):
        print(f"❌ 경로가 존재하지 않습니다: {input_path}")
    else:
        sort_photos(input_path)