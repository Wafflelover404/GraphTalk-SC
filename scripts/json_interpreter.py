import json
from sc_kpm import ScKeynodes
from sc_kpm.utils.common_utils import generate_node
from sc_kpm.utils import generate_link, generate_binary_relation, generate_role_relation
from sc_client.constants import sc_type
from sc_kpm import ScServer
import unicodedata
import re
import hashlib

def normalize_identifier(identifier: str) -> str:
    """Normalize identifiers for SC-machine compatibility"""
    try:
        from unidecode import unidecode
        identifier = unidecode(identifier)
    except ImportError:
        identifier = unicodedata.normalize('NFKD', identifier).encode('ascii', 'ignore').decode('ascii')
    identifier = identifier.lower()
    identifier = re.sub(r'\s+', '_', identifier)
    identifier = re.sub(r'[^a-z0-9_]', '', identifier)
    return identifier

def create_node_with_label(original_text: str, source_addr=None):
    """Create SC-node with attached text label"""
    norm_id = normalize_identifier(original_text)
    logs = []
    try:
        logs.append(f"[SC] Attempting to get node: {norm_id} (from '{original_text}')")
        addr = ScKeynodes[norm_id]
        logs.append(f"[SC] Node exists: {norm_id} (from '{original_text}') -> {addr}")
    except Exception as e:
        try:
            logs.append(f"[SC] Node not found, creating: {norm_id} (from '{original_text}')")
            addr = generate_node(sc_type.CONST_NODE)
            logs.append(f"[SC] Node created: {norm_id} (from '{original_text}') -> {addr}")
        except Exception as e2:
            logs.append(f"[SC] Failed to create node: {norm_id} (from '{original_text}') | {e2}")
            return None, '\n'.join(logs)

    # Attach original text as link content
    try:
        logs.append(f"[SC] Creating label link for node {norm_id}: '{original_text}'")
        label_link = generate_link(original_text)
        logs.append(f"[SC] Label link created: {label_link}")
        generate_binary_relation(sc_type.CONST_PERM_POS_ARC, addr, label_link)
        logs.append(f"[SC] Label attached to node {norm_id} -> {label_link}")
    except Exception as e:
        logs.append(f"[SC] Label attach failed for node {norm_id}: {e}")

    # Connect to source if provided and different
    if source_addr and addr != source_addr:
        try:
            logs.append(f"[SC] Connecting node {norm_id} to source {source_addr}")
            generate_binary_relation(sc_type.CONST_PERM_POS_ARC, addr, source_addr)
            logs.append(f"[SC] Connected node {norm_id} to source {source_addr}")
        except Exception as e:
            logs.append(f"[SC] Source connection failed for node {norm_id}: {e}")
    return addr, '\n'.join(logs)

def create_segment_nodes(segments: dict, source_content_addr, upload_id=None):
    """Create nodes for text segments and attach content"""
    segment_nodes = {}
    logs = []

    # Create special relation for segment connection
    seg_rel_addr, log = create_node_with_label("nrel_segment")
    logs.append(log)

    # Always get main_keywords from source_content_addr if set, else empty
    main_keywords = getattr(source_content_addr, 'main_keywords', [])

    for seg_id, seg_data in segments.items():
        # seg_data can be dict with 'content' and 'keywords'
        seg_text = seg_data.get('content') if isinstance(seg_data, dict) else seg_data
        seg_keywords = seg_data.get('keywords', []) if isinstance(seg_data, dict) else []

        # Attach all main_keywords as tags directly to segment content
        main_kw_tags = "\n".join([f"<main_keyword>{normalize_identifier(kw)}</main_keyword>" for kw in main_keywords])

        # Add <id> and <upload_id> tag to segment text
        tagged_text = f"{seg_text}\n<id>{seg_id}</id>"
        if upload_id:
            tagged_text += f"\n<upload_id>{upload_id}</upload_id>"
        if main_kw_tags:
            tagged_text += f"\n{main_kw_tags}"

        # Create node for segment ID
        seg_node, log = create_node_with_label(seg_id)
        logs.append(log)

        # Create and attach segment content
        try:
            logs.append(f"[SC] Creating segment link for {seg_id} with content: {tagged_text}")
            seg_link = generate_link(tagged_text)
            logs.append(f"[SC] Segment link created: {seg_link}")
            generate_binary_relation(sc_type.CONST_PERM_POS_ARC, seg_node, seg_link)
            logs.append(f"[SC] Segment content attached: {seg_id} -> {seg_link}")

            # Attach ALL normalized main_keywords to segment node
            for kw in main_keywords:
                norm_kw = normalize_identifier(kw)
                kw_node, kw_log = create_node_with_label(norm_kw)
                logs.append(kw_log)
                try:
                    logs.append(f"[SC] Attaching main keyword {norm_kw} to segment {seg_id}")
                    generate_role_relation(seg_node, kw_node, sc_type.CONST_PERM_POS_ARC)
                    logs.append(f"[SC] Main keyword attached to segment {seg_id}: {norm_kw}")
                except Exception as e:
                    logs.append(f"[SC] Main keyword attach failed for {seg_id}: {norm_kw} | {e}")

            # Attach ALL normalized segment-specific keywords to segment node
            for kw in seg_keywords:
                norm_kw = normalize_identifier(kw)
                kw_node, kw_log = create_node_with_label(norm_kw)
                logs.append(kw_log)
                try:
                    logs.append(f"[SC] Attaching segment keyword {norm_kw} to segment {seg_id}")
                    generate_role_relation(seg_node, kw_node, sc_type.CONST_PERM_POS_ARC)
                    logs.append(f"[SC] Segment keyword attached to segment {seg_id}: {norm_kw}")
                except Exception as e:
                    logs.append(f"[SC] Segment keyword attach failed for {seg_id}: {norm_kw} | {e}")

            # Connect segment to main source
            logs.append(f"[SC] Connecting segment {seg_id} to source content via nrel_segment")
            generate_role_relation(source_content_addr, seg_node, seg_rel_addr)
            logs.append(f"[SC] Segment connected: {seg_id} → Source content")
        except Exception as e:
            logs.append(f"[SC] Segment processing failed: {seg_id} | {e}")

        segment_nodes[seg_id] = seg_node

    return segment_nodes, logs

def process_relations(data: dict, source_content_addr, segment_nodes):
    """Process all semantic relations in the JSON"""
    logs = []
    
    # Process segment relations first
    if "Относиться к сегменту" in data:
        seg_relation_addr, log = create_node_with_label("Относиться к сегменту")
        logs.append(log)
        
        for concept, segment_ref in data["Относиться к сегменту"].items():
            # Handle both single segment and array of segments
            segments = [segment_ref] if isinstance(segment_ref, str) else segment_ref
            
            for seg_id in segments:
                if seg_id not in segment_nodes:
                    log = f"Missing segment node: {seg_id}"
                    logs.append(log)
                    continue
                    
                concept_addr, log = create_node_with_label(concept, source_content_addr)
                logs.append(log)
                
                try:
                    logs.append(f"[SC] Creating segment relation: {concept_addr} (concept) → {segment_nodes[seg_id]} (segment) via {seg_relation_addr}")
                    generate_role_relation(
                        concept_addr, 
                        segment_nodes[seg_id], 
                        seg_relation_addr
                    )
                    logs.append(f"[SC] Segment relation: {concept} → {seg_id}")
                except Exception as e:
                    logs.append(f"[SC] Segment relation failed: {concept} → {seg_id} | {e}")
    
    # Process other semantic relations
    for rel, subjects in data.items():
        if rel in ("Source content", "membership", "Относиться к сегменту"):
            continue
            
        rel_addr, log = create_node_with_label(rel, source_content_addr)
        logs.append(log)
        
        for subj, objects in subjects.items():
            subj_addr, log = create_node_with_label(subj, source_content_addr)
            logs.append(log)
            
            if isinstance(objects, list):
                for obj in objects:
                    obj_addr, log = create_node_with_label(obj, source_content_addr)
                    logs.append(log)
                    try:
                        logs.append(f"[SC] Creating relation: {subj_addr} (subj) -[{rel_addr}]-> {obj_addr} (obj)")
                        generate_role_relation(subj_addr, obj_addr, rel_addr)
                        logs.append(f"[SC] Relation: {subj} -[{rel}]-> {obj}")
                    except Exception as e:
                        logs.append(f"[SC] Relation failed: {subj} -[{rel}]-> {obj} | {e}")
            else:
                obj_addr, log = create_node_with_label(objects, source_content_addr)
                logs.append(log)
                try:
                    logs.append(f"[SC] Creating relation: {subj_addr} (subj) -[{rel_addr}]-> {obj_addr} (obj)")
                    generate_role_relation(subj_addr, obj_addr, rel_addr)
                    logs.append(f"[SC] Relation: {subj} -[{rel}]-> {objects}")
                except Exception as e:
                    logs.append(f"[SC] Relation failed: {subj} -[{rel}]-> {objects} | {e}")
    
    return logs

def process_membership(data: dict, source_content_addr):
    """Process membership attributes"""
    logs = []
    if "membership" not in data:
        return logs
        
    # Create special relation for membership
    member_rel_addr, log = create_node_with_label("nrel_membership")
    logs.append(log)
    
    for node, attributes in data["membership"].items():
        node_addr, log = create_node_with_label(node, source_content_addr)
        logs.append(log)
        
        for attr in attributes:
            attr_addr, log = create_node_with_label(attr, source_content_addr)
            logs.append(log)
            
            try:
                logs.append(f"[SC] Creating membership: {node_addr} (node) → {attr_addr} (attr) via {member_rel_addr}")
                generate_role_relation(node_addr, attr_addr, member_rel_addr)
                logs.append(f"[SC] Membership: {node} → {attr}")
            except Exception as e:
                logs.append(f"[SC] Membership failed: {node} → {attr} | {e}")
    
    return logs

def load_data_to_sc(server_url: str, data: dict, upload_id=None):
    server = ScServer(server_url)
    logs = []
    segment_nodes = {}

    try:
        with server.start():
            # Create main source content node
            source_content_id = 'Source content'
            source_content_addr, log = create_node_with_label(source_content_id)
            logs.append(log)

            # Handle both old and new source content formats
            if isinstance(data[source_content_id], dict):
                # New format with segments
                source_content = data[source_content_id]
                full_text = source_content.get('full_text', '')
                segments = source_content.get('segments', {})
                main_keywords = source_content.get('main_keywords', source_content.get('keywords', []))

                # Attach full text
                try:
                    logs.append(f"[SC] Creating full text link for source content: {full_text}")
                    content_link = generate_link(full_text)
                    logs.append(f"[SC] Full text link created: {content_link}")
                    generate_binary_relation(sc_type.CONST_PERM_POS_ARC, source_content_addr, content_link)
                    logs.append("[SC] Full source text attached")
                except Exception as e:
                    logs.append(f"[SC] Full text attach failed: {e}")

                # Attach main_keywords to source_content_addr for segment node use
                setattr(source_content_addr, 'main_keywords', main_keywords)

                # Create segment nodes
                seg_nodes, seg_logs = create_segment_nodes(segments, source_content_addr, upload_id=upload_id)
                segment_nodes = seg_nodes
                logs.extend(seg_logs)
            else:
                # Old format (single string)
                try:
                    logs.append(f"[SC] Creating source content link (old format): {data[source_content_id]}")
                    content_link = generate_link(data[source_content_id])
                    logs.append(f"[SC] Source content link created: {content_link}")
                    generate_binary_relation(sc_type.CONST_PERM_POS_ARC, source_content_addr, content_link)
                    logs.append("[SC] Source content attached (old format)")
                except Exception as e:
                    logs.append(f"[SC] Source content attach failed: {e}")

            # Process semantic relations
            rel_logs = process_relations(data, source_content_addr, segment_nodes)
            logs.extend(rel_logs)

            # Process membership attributes
            member_logs = process_membership(data, source_content_addr)
            logs.extend(member_logs)

            print("Data loaded successfully")
    except Exception as e:
        logs.append(f"Error loading data: {e}")
    finally:
        print("\n--- Detailed Log ---")
        for entry in logs:
            print(entry)

    return logs

if __name__ == '__main__':
    SERVER_URL = 'ws://localhost:8090/ws_json'
    with open('output.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    load_data_to_sc(SERVER_URL, data)