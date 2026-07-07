import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://woody:41538bc6dd@127.0.0.1/davinci")

# Initialize MongoDB Client
client = MongoClient(MONGO_URI)

def get_db():
    """
    Returns the MongoDB database instance.
    The database name is inferred from the connection string.
    """
    return client.get_database()
