import requests, zipfile, io

STATIC_URL = "https://www.spokanetransit.com/gtfs"
OUT_DIR = "data/gtfs_static"

def main():
    resp = requests.get(STATIC_URL, timeout=30)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        z.extractall(OUT_DIR)
    print("Static GTFS downloaded and extracted.")

if __name__ == "__main__":
    main()
