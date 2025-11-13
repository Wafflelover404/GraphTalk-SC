# sc-search-total.py

from sc_client.client import connect, is_connected, disconnect, search_by_template
from sc_client.models import ScAddr, ScConstruction, ScLinkContent, ScLinkContentType, ScTemplate
from sc_client.constants import sc_type

# Import utilities
from sc_kpm.utils import get_element_system_identifier, get_link_content_data

def kb_search(search_string, max_depth=2):
    """
    Search the knowledge base and retrieve connected elements in all directions.
    
    Args:
        search_string (str): Search query
        max_depth (int): Maximum depth to traverse connections
        
    Returns:
        list: Nested dictionary structure of search results and connections
    """
    try:
        # Initial search using available function
        search_terms = search_string.split()
        links_list = search_links_by_contents_substrings(*search_terms)
        
        # Deduplicate addresses
        result_addrs = list(set(addr for sublist in links_list for addr in sublist))
        
        # Process each result with recursive traversal
        full_results = []
        for addr in result_addrs:
            result = {
                "element": decode_sc_element(addr),
                "connections": {
                    "child": traverse_connections(addr, max_depth, visited=set(), direction="child"),
                    "parent": traverse_connections(addr, max_depth, visited=set(), direction="parent"),
                    "adjacent": traverse_connections(addr, max_depth, visited=set(), direction="adjacent")
                }
            }
            full_results.append(result)
            
        return full_results
        
    except Exception as e:
        print(f"Error during knowledge base search: {e}")
        return []

def decode_sc_element(addr: ScAddr) -> dict:
    """Convert ScAddr to human-readable information with proper type checking"""
    result = {
        "address": str(addr),
        "type": "Unknown",
        "value": str(addr)
    }
    
    try:
        # First get the element's type
        element_types = get_elements_types(addr)
        if not element_types:
            return result
            
        element_type = element_types[0]
        
        # Check if it's a node
        if element_type.is_node():
            # Try system identifier first
            sys_idtf = get_element_system_identifier(addr)
            if sys_idtf:
                result["type"] = "Keynode"
                result["value"] = sys_idtf
            else:
                result["type"] = "Node"
                result["value"] = f"Node_{addr.value}"
            return result
                
        # Check if it's a link
        if element_type.is_link():
            # Only get content for links
            link_content = get_link_content_data(addr)
            if link_content:
                result["type"] = "Link Content"
                result["value"] = link_content
            else:
                result["type"] = "Empty Link"
                result["value"] = f"Link_{addr.value}"
            return result
            
        # Handle connectors
        if element_type.is_connector():
            result["type"] = "Connector"
            result["value"] = f"Connector_{addr.value}"
            return result
            
        return result
        
    except Exception as e:
        print(f"Error decoding element: {e}")
        return result

def traverse_connections(start_addr: ScAddr, max_depth: int, visited: set, direction: str, current_depth=1) -> list:
    """
    Recursively traverse connections in specified direction
    
    Args:
        start_addr: Starting element address
        max_depth: Maximum depth to traverse
        visited: Set of visited addresses to prevent cycles
        direction: Direction to traverse ("child", "parent", "adjacent")
        current_depth: Current traversal depth
        
    Returns:
        list: Nested list of connected elements
    """
    if current_depth > max_depth or start_addr in visited:
        return []
        
    visited.add(start_addr)
    connections = []
    
    try:
        # Create template based on direction
        template = ScTemplate()
        
        if direction == "child":
            # Outgoing connections (child nodes)
            template.triple(
                start_addr,
                sc_type.VAR_PERM_POS_ARC >> "_arc",
                sc_type.VAR_NODE >> "_target"
            )
        elif direction == "parent":
            # Incoming connections (parent nodes)
            template.triple(
                sc_type.VAR_NODE >> "_source",
                sc_type.VAR_PERM_POS_ARC >> "_arc",
                start_addr
            )
        else:  # "adjacent"
            # Both directions (combine child and parent patterns)
            template.triple(
                start_addr,
                sc_type.VAR_PERM_POS_ARC >> "_arc1",
                sc_type.VAR_NODE >> "_target"
            )
            template.triple(
                sc_type.VAR_NODE >> "_source",
                sc_type.VAR_PERM_POS_ARC >> "_arc2",
                start_addr
            )
        
        results = search_by_template(template)
        
        if results:
            for result in results:
                # Get all possible targets from the template
                targets = []
                
                if direction == "child" and result.get("_target"):
                    targets.append(result.get("_target"))
                elif direction == "parent" and result.get("_source"):
                    targets.append(result.get("_source"))
                elif direction == "adjacent":
                    if result.get("_target"):
                        targets.append(result.get("_target"))
                    if result.get("_source"):
                        targets.append(result.get("_source"))
                
                for target_addr in targets:
                    if target_addr and target_addr.is_valid():
                        element = decode_sc_element(target_addr)
                        
                        # Recursively get deeper connections
                        children = traverse_connections(
                            target_addr, 
                            max_depth, 
                            visited.copy(),
                            direction,
                            current_depth + 1
                        )
                        
                        connections.append({
                            "element": element,
                            "depth": current_depth + 1,
                            "connections": children
                        })
                        
    except Exception as e:
        print(f"Error traversing connections: {e}")
        
    return connections

def print_results(results):
    """Recursively print search results in tree format"""
    for item in results:
        print_element(item["element"])
        
        if item["connections"]["child"]:
            print("  Child connections:")
            print_connections(item["connections"]["child"], 2)
            
        if item["connections"]["parent"]:
            print("  Parent connections:")
            print_connections(item["connections"]["parent"], 2)
            
        if item["connections"]["adjacent"]:
            print("  Adjacent connections:")
            print_connections(item["connections"]["adjacent"], 2)

def print_element(element):
    print(f"- {element['type']}: {element['value']}")

def print_connections(connections, indent):
    for conn in connections:
        print(f"{' ' * indent}- {conn['element']['type']}: {conn['element']['value']}")
        if conn["connections"]:
            print_connections(conn["connections"], indent + 2)

# Connection URL
url = "ws://localhost:8090/ws_json"

# Helper functions from client
def get_elements_types(*addrs: ScAddr):
    """Get element types from KB"""
    from sc_client.client import get_elements_types as client_get_types
    return client_get_types(*addrs)

def search_links_by_contents_substrings(*contents: str):
    """Search links by content substrings"""
    from sc_client.client import search_links_by_contents_substrings as client_search
    return client_search(*contents)

def search_by_template(template):
    """Search using SC template"""
    from sc_client.client import search_by_template as client_search
    return client_search(template)

# Example usage
if __name__ == "__main__":
    try:
        connect(url)
        if is_connected():
            # Example search with max depth 2
            search_results = kb_search("OSTIS technology", max_depth=2)
            print("Search results:")
            print_results(search_results)
        else:
            print("Not connected to SC-machine")
    finally:
        disconnect()