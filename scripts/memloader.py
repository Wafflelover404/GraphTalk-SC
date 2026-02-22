import os
import glob
from sc_client.client import connect, disconnect, generate_elements_by_scs

def load_scs_directory(directory_path):
    connect("ws://localhost:8090/ws_json")
    
    try:
        scs_files = glob.glob(os.path.join(directory_path, "**/*.scs"), recursive=True)
        
        if not scs_files:
            return "No .scs files found in the specified directory."
        
        scs_contents = []
        file_read_errors = []
        for file_path in scs_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    scs_contents.append(f.read())
            except Exception as e:
                file_read_errors.append((file_path, str(e)))
        
        status_message = []
        if file_read_errors:
            status_message.append(f"Failed to read {len(file_read_errors)} file(s):")
            for file_path, error in file_read_errors:
                status_message.append(f"  ❌ Error reading {file_path}: {error}")
        
        success_count = 0
        failure_count = 0
        if scs_contents:
            results = generate_elements_by_scs(scs_contents)
            
            for file_path, success in zip(scs_files, results):
                if success:
                    success_count += 1
                else:
                    failure_count += 1
                    status_message.append(f"  ❌ Failed to load: {file_path}")
        
        status_message.insert(0, f"Total .scs files found: {len(scs_files)}")
        status_message.append(f"Successfully loaded: {success_count} file(s)")
        status_message.append(f"Failed to load: {failure_count} file(s)")
        
        return "\n".join(status_message)
    
    except Exception as e:
        return f"Fatal error occurred: {str(e)}"
    
    finally:
        disconnect()

# Usage example
status_string = load_scs_directory("./unpacked_kbs/")
print(status_string)