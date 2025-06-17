from sc_client.client import connect, disconnect, is_connected

url = "ws://localhost:8090/ws_json"

connect(url)

if is_connected():
    print("Connected to the server !")
else:
    print("Failed to connect to the server. Check your sc machine instance and try again.")

disconnect()