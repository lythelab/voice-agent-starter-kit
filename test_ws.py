import asyncio
import websockets
import json
import base64

async def test_ws():
    # Attempt to connect to the local server
    uri = "ws://localhost:8000/ws/streaming-pipeline"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Waiting for 'info' event...")
            # Wait for "Session Started"
            msg = await websocket.recv()
            print("Received:", msg)

            print("Sending mock audio chunk...")
            # We will send a mock chunk. Without actual audio, Deepgram may not transcribe.
            # But let's see if we get any errors.
            await websocket.send(json.dumps({
                "type": "user_audio_chunk",
                "audio_b64": base64.b64encode(b"dummy_audio_bytes_not_real_webm").decode()
            }))

            print("Waiting for response... (timeout in 5 seconds)")
            for _ in range(3):
                try:
                    res = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    print("Server Message:", res[:200] + "..." if len(res)>200 else res)
                except asyncio.TimeoutError:
                    print("Timeout waiting for server message.")
                    break
            
            # Close
            await websocket.send(json.dumps({"type": "stop"}))
            print("Test finished.")
    except Exception as e:
        print("Failed to connect or test:", e)

if __name__ == "__main__":
    asyncio.run(test_ws())
