import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("Error: The 'websockets' package is not installed.")
    print("Please install it using: pip install websockets")
    print("Or ensure you have activated the virtual environment: source .venv/bin/activate")
    sys.exit(1)

async def test_ws():
    uri = "ws://127.0.0.1:8000/ws/events"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri, open_timeout=20) as websocket:
            print("Connected! Waiting for events...")
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    print(f"Received event: {data}")
                except json.JSONDecodeError as jde:
                    print(f"Error decoding JSON message: {jde}. Raw message: {message}")
    except ConnectionRefusedError:
        print("Error: Connection refused. Is the backend server running on port 8000?")
    except (asyncio.TimeoutError, TimeoutError):
        print("Error: Connection timed out. The server might be under heavy load or unresponsive.")
    except websockets.exceptions.ConnectionClosedOK:
        print("Connection closed cleanly by the server.")
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"Connection closed with error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(test_ws())
    except KeyboardInterrupt:
        print("\nDisconnected by user.")

