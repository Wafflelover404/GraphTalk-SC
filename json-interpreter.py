import json
from sc_kpm import ScKeynodes
from sc_kpm.utils.common_utils import generate_node
from sc_kpm.utils import generate_link, generate_binary_relation, generate_role_relation
from sc_client.constants import sc_type
from sc_kpm import ScServer
import unicodedata
import re

# Load JSON data from file
with open('output.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

def normalize_identifier(identifier: str) -> str:
    try:
        from unidecode import unidecode
        identifier = unidecode(identifier)
    except ImportError:
        identifier = unicodedata.normalize('NFKD', identifier).encode('ascii', 'ignore').decode('ascii')
    identifier = identifier.lower()
    identifier = re.sub(r'\s+', '_', identifier)
    identifier = re.sub(r'[^a-z0-9_]', '', identifier)
    return identifier

def create_node_with_label(original_text: str):
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
    # Attach the original text as a link
    try:
        label_link = generate_link(original_text)
        generate_binary_relation(sc_type.CONST_PERM_POS_ARC, addr, label_link)
        log += f" | Label attached"
    except Exception as e:
        log += f" | Label attach failed: {e}"
    return addr, log

def load_data_to_sc(server_url: str):
    server = ScServer(server_url)
    logs = []
    try:
        with server.start():
            # Add Source content as a link node
            content_id = 'Source content'
            content_addr, log = create_node_with_label(content_id)
            logs.append(log)
            try:
                content_link = generate_link(data[content_id])
                generate_binary_relation(sc_type.CONST_PERM_POS_ARC, content_addr, content_link)
                logs.append(f"Source content link attached: {data[content_id]}")
            except Exception as e:
                logs.append(f"Source content link attach failed: {e}")

            # Process all relations except membership and Source content
            for rel, subjects in data.items():
                if rel in ('membership', 'Source content'):
                    continue
                rel_addr, log = create_node_with_label(rel)
                logs.append(log)
                for subj, objects in subjects.items():
                    subj_addr, log = create_node_with_label(subj)
                    logs.append(log)
                    if isinstance(objects, list):
                        for obj in objects:
                            obj_addr, log = create_node_with_label(obj)
                            logs.append(log)
                            try:
                                generate_role_relation(subj_addr, obj_addr, rel_addr)
                                logs.append(f"Relation created: {subj} -[{rel}]-> {obj}")
                            except Exception as e:
                                logs.append(f"Relation failed: {subj} -[{rel}]-> {obj} | {e}")
                    else:
                        obj_addr, log = create_node_with_label(objects)
                        logs.append(log)
                        try:
                            generate_role_relation(subj_addr, obj_addr, rel_addr)
                            logs.append(f"Relation created: {subj} -[{rel}]-> {objects}")
                        except Exception as e:
                            logs.append(f"Relation failed: {subj} -[{rel}]-> {objects} | {e}")

            # Ensure all membership nodes exist
            for item in data.get('membership', {}):
                addr, log = create_node_with_label(item)
                logs.append(log)

            print("Data loaded successfully")
    except Exception as e:
        logs.append(f"Error loading data: {e} (normalized: '{norm_id}', original: '{original_text}')")
    finally:
        print("\n--- Detailed Log ---")
        for entry in logs:
            print(entry)

if __name__ == '__main__':
    SERVER_URL = 'ws://localhost:8090/ws_json'
    load_data_to_sc(SERVER_URL)
