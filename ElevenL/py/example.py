from elevenlabs.client import ElevenLabs

client = ElevenLabs(api_key="your_api_key")

# Get raw response with headers
response = client.text_to_speech.with_raw_response.convert(
    text="Hello, world!",
    voice_id="voice_id"
)

# Access character cost from headers
char_cost = response.headers.get("x-character-count")
request_id = response.headers.get("request-id")
audio_data = response.data
