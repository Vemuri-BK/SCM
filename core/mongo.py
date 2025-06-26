import motor.motor_asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Use full URI directly from .env
uri = os.getenv('MONGO_URI')
DB_NAME = os.getenv("MONGO_DB_NAME", "SCMLite")

if uri is None:
    raise ValueError("MONGO_URI not found in environment variables")

# Initialize MongoDB client
client = motor.motor_asyncio.AsyncIOMotorClient(uri)
db = client[DB_NAME]

# Define collections
users_collection = db['users']
shipments_collection = db['shipments']
logins_collection = db['logins']
sensor_data_collection = db['sensor_data']
