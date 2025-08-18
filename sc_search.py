from sc_client.client import connect, is_connected, disconnect, search_links_by_contents_substrings, search_by_template
from sc_client.constants import sc_type
from sc_client.models import ScTemplate
from sc_kpm.utils import get_element_system_identifier, get_link_content_data

def search_outgoing_arcs(addr):
    # Returns list of (arc_addr, src_addr, tgt_addr)
    template = ScTemplate()
    template.triple(addr, sc_type.VAR_PERM_POS_ARC, sc_type.VAR_NODE >> "_target")
    results = search_by_template(template)
    arcs = []
    for result in results:
        arc_addr = result[1]
        src_addr = addr
        tgt_addr = result.get("_target")
        arcs.append((arc_addr, src_addr, tgt_addr))
    return arcs

def find_source_content(addr) -> str:
    # Try to find outgoing arcs to a node or link with idtf or content for 'source_content'
    try:
        outgoing = search_outgoing_arcs(addr)
        for arc in outgoing:
            target = arc[2]
            sys_idtf = get_element_system_identifier(target)
            if sys_idtf and sys_idtf.lower() == "source_content":
                # Try to get content from outgoing arcs of source_content node
                content_links = search_outgoing_arcs(target)
                for cl_arc in content_links:
                    content = get_link_content_data(cl_arc[2])
                    if content:
                        return f"Source content: {content[:120]}..."
                return "Source content node found, but no content attached."
            # Also check if the target itself is a link with content
                content = get_link_content_data(target)
        return None
    except Exception:
        return None

def kb_search(search_string: str) -> list:
    """
    Search the Knowledge Base for links containing the given string or its substrings.
    Args:
        search_string (str): The search query.
    Returns:
        list: Sorted unique strings with search results.
    """
    url = "ws://localhost:8090/ws_json"
    if not search_string or not search_string.strip():
        return ["Empty search query."]
    try:
        connect(url)
        if not is_connected():
            return ["Not connected to SC-machine"]

        search_terms = search_string.strip().split()
        links_list = search_links_by_contents_substrings(*search_terms)
        result_addrs = {addr for sublist in links_list for addr in sublist}

        decoded_results = set()
        for addr in result_addrs:
            sys_idtf = get_element_system_identifier(addr)
            if sys_idtf:
                result = f"Keynode: {sys_idtf}"
            else:
                content = get_link_content_data(addr)
                if content:
                    result = f"Link Content: {content}"
                else:
                    result = f"Unknown Element: {addr}"
            # Try to find source content for this addr
            source = find_source_content(addr)
            if source:
                result += f"\n  -> {source}"
            decoded_results.add(result)

        return sorted(decoded_results)
    except Exception as e:
        return [f"Error during search: {e}"]
    finally:
        disconnect()

if __name__ == "__main__":
    # Example usage:
    results = kb_search("Any query text example: 'How to fix a car' ")
    for r in results:
        print(r)