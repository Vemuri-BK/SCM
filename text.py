from dotenv import load_dotenv
import os

load_dotenv()
print(repr(os.getenv("JWT_ACCESS_TOKEN_EXPIRES")))