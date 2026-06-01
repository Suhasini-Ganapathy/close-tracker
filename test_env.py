from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")
print("API key loaded successfully" if api_key else "API key not found")
