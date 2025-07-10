from sc_client.client import connect, is_connected, disconnect, search_links_by_contents_substrings, generate_elements
from sc_client.models import ScConstruction, ScLinkContent, ScLinkContentType
from sc_client.constants import sc_type
from sc_kpm.utils import get_element_system_identifier, get_link_content_data

def kb_search(search_string):
    """
    This function performs a quick and non-recursive search through the Knowledge Base graph using OSTIS technology libraries.
    
    Args:
        search_string (str): The search query to look for in the knowledge base
        
    Returns:
        list: A list of unique strings containing the search results.
    """
    url = "ws://localhost:8090/ws_json"
    
    try:
        # Establish connection
        connect(url)
        
        if not is_connected():
            return ["Not connected to SC-machine"]
            
        # Create search context link
        construction = ScConstruction()
        link_content = ScLinkContent(search_string, ScLinkContentType.STRING)
        construction.generate_link(sc_type.CONST_NODE_LINK, link_content)
        generate_elements(construction)
        
        # Perform search
        search_terms = search_string.split()
        links_list = search_links_by_contents_substrings(*search_terms)
        result_addrs = [addr for sublist in links_list for addr in sublist]
        
        # Deduplicate by address
        unique_addrs = set(result_addrs)

        # Process and display results, deduplicate by result string
        decoded_results = set()
        for addr in unique_addrs:
            sys_idtf = get_element_system_identifier(addr)
            if sys_idtf:
                decoded_results.add(f"Keynode: {sys_idtf}")
            else:
                content = get_link_content_data(addr)
                if content:
                    decoded_results.add(f"Link Content: {content}")
                else:
                    decoded_results.add(f"Unknown Element: {addr}")

        return list(decoded_results)
        
    except Exception as e:
        return [f"Error during search: {e}"]
    finally:
        disconnect()

if __name__ == "__main__":
    kb_search()