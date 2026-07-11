from google.transit import gtfs_realtime_pb2
import requests
import sys

def test_feed(url):
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(resp.content)
    print(f"URL: {url}")
    print(f"Feed timestamp: {feed.header.timestamp}")
    print(f"Entity count: {len(feed.entity)}")
    trip_updates = [e for e in feed.entity if e.HasField("trip_update")]
    vehicle_positions = [e for e in feed.entity if e.HasField("vehicle")]
    print(f"trip_update entities: {len(trip_updates)}")
    print(f"vehicle_position entities: {len(vehicle_positions)}")
    if trip_updates:
        print("Sample trip_update:")
        print(trip_updates[0])
    return feed.header.timestamp

if __name__ == "__main__":
    url = sys.argv[1]
    test_feed(url)
