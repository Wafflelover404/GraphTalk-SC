from sc_client.client import connect, is_connected, disconnect
from sc_client.models import ScAddr
from sc_client.client import generate_elements, search_links_by_contents_substrings
from sc_client.constants import sc_type
from sc_client.models import ScLinkContent, ScLinkContentType, ScConstruction

def kb_search(search_string):
    """
    Search the knowledge base for content containing the given search string.
    
    Args:
        search_string (str): The search query to look for in the knowledge base
        
    Returns:
        list: List of links containing the search results
    """
    try:
        # Create link with search string
        construction = ScConstruction()
        link_content = ScLinkContent(search_string, ScLinkContentType.STRING)
        construction.generate_link(sc_type.CONST_NODE_LINK, link_content)
        link = generate_elements(construction)[0]

        # Search for links containing the search string
        search_terms = search_string.split()
        links_list = search_links_by_contents_substrings(*search_terms)
        
        # Verify all search terms are found
        assert all(link in links for links in links_list)
        
        return links_list
    except Exception as e:
        print(f"Error during knowledge base search: {e}")
        return []

url = "ws://localhost:8090/ws_json"

# Example usage
if __name__ == "__main__":
    try:
        connect(url)
        if is_connected():
            
            # Example search
            search_results = kb_search("Nika")
            print(f"Search results: {search_results}")
        else:
            print("Not connected to NIKA")
    finally:
        disconnect()