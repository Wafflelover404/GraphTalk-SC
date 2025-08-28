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

async def kb_search(search_string: str, allowed_files=None) -> list:
    """
    Search the Knowledge Base for links containing the given string or its substrings.
    Args:
        search_string (str): The search query.
        allowed_files (list or None): List of allowed filenames, or None for all.
    Returns:
        list: Sorted unique strings with search results.
    """
    url = "ws://localhost:8090/ws_json"
    if not search_string or not search_string.strip():
        return ["Empty search query."]
    
    # Run the blocking SC-machine operations in a thread pool
    import asyncio
    loop = asyncio.get_event_loop()
    
    def _sync_search():
        try:
            connect(url)
            if not is_connected():
                return ["Not connected to SC-machine"]

            def normalize_kw(kw):
                import re
                kw = kw.lower()
                kw = re.sub(r'\s+', '_', kw)
                kw = re.sub(r'[^a-zа-я0-9_]', '', kw)
                return kw

            def variants(kw):
                norm = normalize_kw(kw)
                cap = norm.capitalize()
                upper = norm.upper()
                orig = kw
                return list({norm, cap, upper, orig})

            raw_terms = search_string.strip().split()
            search_terms = []
            for term in raw_terms:
                search_terms.extend(variants(term))

            tag_terms = [f"<main_keyword>{kw}</main_keyword>" for kw in search_terms]
            all_terms = search_terms + tag_terms

            links_list = search_links_by_contents_substrings(*all_terms)
            result_addrs = {addr for sublist in links_list for addr in sublist}

            decoded_results = set()
            for addr in result_addrs:
                sys_idtf = get_element_system_identifier(addr)
                content = get_link_content_data(addr)
                # If allowed_files is set, filter by filename
                if allowed_files is not None and allowed_files:
                    # Only allow if sys_idtf or content matches allowed files
                    allowed = False
                    if sys_idtf and sys_idtf in allowed_files:
                        allowed = True
                    elif content:
                        # Try to match filename in content (if content is filename)
                        for fname in allowed_files:
                            if fname in content:
                                allowed = True
                                break
                    if not allowed:
                        continue
                # ...existing result formatting...
                if sys_idtf:
                    result = f"Keynode: {sys_idtf}"
                elif content:
                    result = f"Link Content: {content}"
                else:
                    result = f"Unknown Element: {addr}"
                source = find_source_content(addr)
                if source:
                    result += f"\n  -> {source}"
                decoded_results.add(result)

            return sorted(decoded_results)
        except Exception as e:
            return [f"Error during search: {e}"]
        finally:
            disconnect()
    
    return await loop.run_in_executor(None, _sync_search)

if __name__ == "__main__":
    # Example usage:
    results = kb_search("Any query text example: 'How to fix a car' ")
    for r in results:
        print(r)