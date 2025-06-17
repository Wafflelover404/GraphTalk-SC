from sc_client.client import connect, is_connected, disconnect, search_links_by_contents_substrings, generate_elements
from sc_client.models import ScAddr, ScConstruction, ScLinkContent, ScLinkContentType
from sc_client.constants import sc_type

# Import utilities for resolving identifiers and link content
from sc_kpm.utils import get_element_system_identifier, get_link_content_data

def kb_search(search_string):
    """
    Search the knowledge base for content containing the given search string.
    Decodes ScAddr to human-readable identifiers or link content.
    
    Args:
        search_string (str): The search query to look for in the knowledge base
        
    Returns:
        list: List of decoded results (system identifiers or link content)
    """
    try:
        # Create link with search string for search context
        construction = ScConstruction()
        link_content = ScLinkContent(search_string, ScLinkContentType.STRING)
        construction.generate_link(sc_type.CONST_NODE_LINK, link_content)
        generate_elements(construction)  # Fire and forget

        # Search for links containing the search string
        search_terms = search_string.split()
        links_list = search_links_by_contents_substrings(*search_terms)

        # Collect all unique link addresses from results
        result_addrs = [addr for sublist in links_list for addr in sublist]
        
        # Decode ScAddr to human-readable content
        decoded_results = []
        for addr in result_addrs:
            # Try to get system identifier (keynode name)
            sys_idtf = get_element_system_identifier(addr)
            if sys_idtf:
                decoded_results.append(f"Keynode: {sys_idtf}")
            else:
                # If not a keynode, check if it's a link with content
                link_content = get_link_content_data(addr)
                if link_content:
                    decoded_results.append(f"Link Content: {link_content}")
                else:
                    decoded_results.append(f"Unknown Element: {addr}")
                    
        return decoded_results
        
    except Exception as e:
        print(f"Error during knowledge base search: {e}")
        return []

# Connection URL
url = "ws://localhost:8090/ws_json"

# Example usage
if __name__ == "__main__":
    try:
        connect(url)
        if is_connected():
            # Example search
            search_results = kb_search("Когда защита первой лабы?")
            print(f"Search results:")
            for item in search_results:
                print(f" - {item}")
        else:
            print("Not connected to NIKA")
    finally:
        disconnect()