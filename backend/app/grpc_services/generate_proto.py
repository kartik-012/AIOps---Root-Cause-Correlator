import os
import subprocess
import sys

def generate_protos():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    proto_dir = os.path.join(base_dir, 'protos')
    out_dir = os.path.join(base_dir, 'generated')
    
    os.makedirs(out_dir, exist_ok=True)
    
    # Touch __init__.py so it's a module
    init_file = os.path.join(out_dir, '__init__.py')
    if not os.path.exists(init_file):
        with open(init_file, 'w') as f:
            pass
            
    # Command to run protoc
    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"--python_out={out_dir}",
        f"--grpc_python_out={out_dir}",
        os.path.join(proto_dir, "diagnostics.proto")
    ]
    
    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    
    # Fix import in generated grpc code
    grpc_file = os.path.join(out_dir, 'diagnostics_pb2_grpc.py')
    with open(grpc_file, 'r') as f:
        content = f.read()
    
    content = content.replace('import diagnostics_pb2 as diagnostics__pb2', 'from . import diagnostics_pb2 as diagnostics__pb2')
    
    with open(grpc_file, 'w') as f:
        f.write(content)
        
    print("Generated protobuf files successfully.")

if __name__ == '__main__':
    generate_protos()
