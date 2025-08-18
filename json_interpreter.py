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
    try:
        addr = ScKeynodes[norm_id]
        log = f"Node exists: {norm_id} (from '{original_text}') -> {addr}"
    except Exception as e:
        try:
            addr = generate_node(sc_type.CONST_NODE)
            log = f"Node created: {norm_id} (from '{original_text}') -> {addr}"
        except Exception as e2:
            log = f"Failed to create node: {norm_id} (from '{original_text}') | {e2}"
            return None, log
    
    # Attach original text as link content
    try:
        label_link = generate_link(original_text)
        generate_binary_relation(sc_type.CONST_PERM_POS_ARC, addr, label_link)
        log += f" | Label attached"
    except Exception as e:
        log += f" | Label attach failed: {e}"
        
    # Connect to source if provided and different
    if source_addr and addr != source_addr:
        try:
            generate_binary_relation(sc_type.CONST_PERM_POS_ARC, addr, source_addr)
            log += f" | Connected to source"
        except Exception as e:
            log += f" | Source connection failed: {e}"
    return addr, log

def create_segment_nodes(segments: dict, source_content_addr, upload_id=None):
    """Create nodes for text segments and attach content"""
    segment_nodes = {}
    logs = []

    # Create special relation for segment connection
    seg_rel_addr, log = create_node_with_label("nrel_segment")
    logs.append(log)

    for seg_id, seg_text in segments.items():
        # Add <id> and <upload_id> tag to segment text
        tagged_text = f"{seg_text}\n<id>{seg_id}</id>"
        if upload_id:
            tagged_text += f"\n<upload_id>{upload_id}</upload_id>"
        # Create node for segment ID
        seg_node, log = create_node_with_label(seg_id)
        logs.append(log)

        # Create and attach segment content
        try:
            seg_link = generate_link(tagged_text)
            generate_binary_relation(sc_type.CONST_PERM_POS_ARC, seg_node, seg_link)
            logs.append(f"Segment content attached: {seg_id}")

            # Connect segment to main source
            generate_role_relation(source_content_addr, seg_node, seg_rel_addr)
            logs.append(f"Segment connected: {seg_id} → Source content")
        except Exception as e:
            logs.append(f"Segment processing failed: {seg_id} | {e}")

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
                    generate_role_relation(
                        concept_addr, 
                        segment_nodes[seg_id], 
                        seg_relation_addr
                    )
                    logs.append(f"Segment relation: {concept} → {seg_id}")
                except Exception as e:
                    logs.append(f"Segment relation failed: {concept} → {seg_id} | {e}")
    
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
                        generate_role_relation(subj_addr, obj_addr, rel_addr)
                        logs.append(f"Relation: {subj} -[{rel}]-> {obj}")
                    except Exception as e:
                        logs.append(f"Relation failed: {subj} -[{rel}]-> {obj} | {e}")
            else:
                obj_addr, log = create_node_with_label(objects, source_content_addr)
                logs.append(log)
                try:
                    generate_role_relation(subj_addr, obj_addr, rel_addr)
                    logs.append(f"Relation: {subj} -[{rel}]-> {objects}")
                except Exception as e:
                    logs.append(f"Relation failed: {subj} -[{rel}]-> {objects} | {e}")
    
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
                generate_role_relation(node_addr, attr_addr, member_rel_addr)
                logs.append(f"Membership: {node} → {attr}")
            except Exception as e:
                logs.append(f"Membership failed: {node} → {attr} | {e}")
    
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

                # Attach full text
                try:
                    content_link = generate_link(full_text)
                    generate_binary_relation(sc_type.CONST_PERM_POS_ARC, source_content_addr, content_link)
                    logs.append("Full source text attached")
                except Exception as e:
                    logs.append(f"Full text attach failed: {e}")

                # Create segment nodes
                seg_nodes, seg_logs = create_segment_nodes(segments, source_content_addr, upload_id=upload_id)
                segment_nodes = seg_nodes
                logs.extend(seg_logs)
            else:
                # Old format (single string)
                try:
                    content_link = generate_link(data[source_content_id])
                    generate_binary_relation(sc_type.CONST_PERM_POS_ARC, source_content_addr, content_link)
                    logs.append("Source content attached (old format)")
                except Exception as e:
                    logs.append(f"Source content attach failed: {e}")

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