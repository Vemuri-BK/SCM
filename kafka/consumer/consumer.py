import os
import sys
import time
import json
import pymongo
from kafka import KafkaConsumer

print("[Consumer] 🚀 Starting consumer.py...", flush=True)

# === MongoDB Setup ===
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "SCMLite")
COLLECTION_NAME = os.getenv("COLL_SENSOR", "sensor_data")

if not MONGO_URI:
    print("[Consumer] ❌ Missing MongoDB URI (MONGO_URI). Exiting.", flush=True)
    sys.exit(1)

# === MongoDB Connection ===
db_client, db, collection = None, None, None
for attempt in range(1, 11):
    print(f"[Consumer] Attempt {attempt}/10: Connecting to MongoDB...", flush=True)
    try:
        db_client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db_client.admin.command("ping")
        db = db_client[MONGO_DB_NAME]
        collection = db[COLLECTION_NAME]
        print(f"[Consumer] ✅ Connected to MongoDB. DB: '{MONGO_DB_NAME}', Collection: '{COLLECTION_NAME}'", flush=True)
        break
    except Exception as e:
        print(f"[Consumer] ⚠️ MongoDB connection failed: {e}", flush=True)
        if attempt == 10:
            print("[Consumer] ❌ Max MongoDB attempts reached. Exiting.", flush=True)
            sys.exit(1)
        time.sleep(10)

# === Kafka Setup ===
KAFKA_BROKER = os.getenv("BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("topic_name", "sensor-data")
GROUP_ID = "sensor-data-consumer-group"

consumer = None
for attempt in range(1, 11):
    print(f"[Consumer] Attempt {attempt}/10: Connecting to Kafka at {KAFKA_BROKER}...", flush=True)
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=[KAFKA_BROKER],
            group_id=GROUP_ID,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        )
        print(f"[Consumer] ✅ Connected to Kafka. Subscribed to topic: '{KAFKA_TOPIC}'", flush=True)
        print(f"[Consumer] 🔁 Entering Kafka consumption loop...", flush=True)
        print(f"[Consumer] Subscribed Topics: {consumer.subscription()}", flush=True)
        print(f"[Consumer] Known Topics: {consumer.topics()}", flush=True)
        break
    except Exception as e:
        print(f"[Consumer] ⚠️ Kafka connection failed: {e}", flush=True)
        if attempt == 10:
            print("[Consumer] ❌ Max Kafka attempts reached. Exiting.", flush=True)
            sys.exit(1)
        time.sleep(10)

# === Message Loop ===
try:
    for message in consumer:
        try:
            msg_value = message.value
            print(f"[Consumer] 🔄 Received from Kafka: {msg_value}", flush=True)
            insert_result = collection.insert_one(msg_value)
            print(f"[Consumer] ✅ Inserted to MongoDB with ID: {insert_result.inserted_id}", flush=True)
        except pymongo.errors.PyMongoError as e:
            print(f"[Consumer] ❌ MongoDB Insert Error: {e}", flush=True)
            print(f"[Consumer] Failed Message: {msg_value}", flush=True)
        except Exception as e:
            print(f"[Consumer] ❌ Unexpected Error: {e}", flush=True)
            print(f"[Consumer] Message: {message.value}", flush=True)
except KeyboardInterrupt:
    print("\n[Consumer] 🛑 Keyboard interrupt. Exiting...", flush=True)
except Exception as e:
    print(f"[Consumer] ❌ Fatal error in consumer loop: {e}", flush=True)
finally:
    print("[Consumer] 🔒 Closing Kafka consumer and MongoDB connection...", flush=True)
    if consumer:
        consumer.close()
    if db_client:
        db_client.close()
    print("[Consumer] ✅ Shutdown complete.", flush=True)
