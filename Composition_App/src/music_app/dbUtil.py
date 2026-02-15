import os
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()
mongodb_username = os.getenv("MONGODB_USERNAME")
mongodb_password = os.getenv("MONGODB_PASSWORD")
uri = f"mongodb+srv://{mongodb_username}:{mongodb_password}@cluster0.oumt9ro.mongodb.net/?appName=Cluster0"

# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)
    exit(1)

# Connect to database and collection
db = client['MuseAid']  # Replace with your preferred database name
collection = db['Comps']       # Replace with your preferred collection name

def add_entry(id, data, code=None):
    entry = {
        "id": id,
        "data": data,
        "code": code
    }
    
    try:
        result = collection.insert_one(entry)
        print(f"Entry added successfully! Document ID: {result.inserted_id}")
        return result.inserted_id
    except Exception as e:
        print(f"Error adding entry: {e}")
        return None

def get_entry_by_id(id):
    """
    Get an entry from the database by ID, returning all fields
    
    Args:
        id (int): The ID to search for
        
    Returns:
        dict or None: The entry document if found, None otherwise
    """
    try:
        result = collection.find_one({"id": id})
        if result:
            print(f"Entry found: {result}")
            return result
        else:
            print(f"No entry found with id: {id}")
            return None
    except Exception as e:
        print(f"Error retrieving entry: {e}")
        return None

def entry_exists(id):
    """
    Check if an entry with the given ID exists in the database
    
    Args:
        id (int): The ID to check for
        
    Returns:
        bool: True if the entry exists, False otherwise
    """
    try:
        result = collection.find_one({"id": id}, {"_id": 1})  # Only retrieve _id field for efficiency
        exists = result is not None
        print(f"Entry with id {id} {'exists' if exists else 'does not exist'}")
        return exists
    except Exception as e:
        print(f"Error checking entry existence: {e}")
        return False
