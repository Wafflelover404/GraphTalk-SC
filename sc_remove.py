from sc_client.client import connect, is_connected, disconnect, erase_elements
from sc_client.constants import sc_type
from sc_kpm import ScKeynodes
from sc_client.models import ScAddr
# Utility to remove a node and all its outgoing/incoming arcs
# (You may want to extend this for more complex semantic structures)
def remove_sc_node(addr):
    url = "ws://localhost:8090/ws_json"
    connect(url)
    if not is_connected():
        raise Exception("Not connected to SC-machine")
    from sc_client.models import ScAddr
    try:
        addr_int = int(addr)
        sc_addr = ScAddr(addr_int)
    except Exception:
        raise Exception(f"Invalid SC address: {addr}")
    erase_elements(sc_addr)
    disconnect()
    return True

# Remove by identifier (system idtf)

def remove_by_identifier(identifier_or_addr):
    url = "ws://localhost:8090/ws_json"
    connect(url)
    if not is_connected():
        raise Exception("Not connected to SC-machine")

    # Try to interpret as int address first
    try:
        addr_int = int(identifier_or_addr)
        return remove_sc_node(addr_int)
    except (ValueError, TypeError):
        pass
    # If not int, try as identifier
    try:
        addr = ScKeynodes.get(identifier_or_addr)
        if not addr or int(addr) == 0:
            disconnect()
            raise Exception(f"Identifier '{identifier_or_addr}' not found in KB")
        disconnect()
        return remove_sc_node(addr)
    except Exception as e:
        disconnect()
        raise Exception(f"Could not remove by identifier or address: {identifier_or_addr} | {e}")