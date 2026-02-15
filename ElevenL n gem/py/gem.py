# TEST FILE 

from google import genai
import os
from dotenv import load_dotenv
# The client gets the API key from the environment variable `GEMINI_API_KEY`.
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

response = client.models.generate_content(
    model="gemini-3-flash-preview", contents="Give me a chord progression in the style of Chopin."
)
print(response.text)