#!/usr/bin/env python3

import argparse
import sys
import os
import yaml

def main():
    parser = argparse.ArgumentParser(
        description="Generates phntm_bridge.yaml for a demo robot from yaml file"
    )
    parser.add_argument("yaml_file", help="Path to YAML file")
    args = parser.parse_args()

    try:
        with open(args.yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"File not found: {args.yaml_file}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Invalid YAML: {e}", file=sys.stderr)
        sys.exit(1)

    id_demo = next(iter(data))
    print(f"id_demo: {id_demo}")
    print(f"id_robot: {data[id_demo]['id_robot']}")
    print(f"robot_key: {data[id_demo]['robot_key']}")
    print(f"name: {data[id_demo]['name']}")
    print(f"bridge_server_address: {data[id_demo]['bridge_server_address']}")
    print(f"location: {data[id_demo]['location']}")
    print(f"demo_url: {data[id_demo]['demo_url']}")
    
    # Read template
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_file = os.path.join(script_dir, "phntm_bridge.templ.yaml")
    try:
        with open(template_file, "r", encoding="utf-8") as f:
            result = f.read()
    except FileNotFoundError:
        print(f"Template not found: {template_file}", file=sys.stderr)
        sys.exit(1)
    
    # Replace %ID_LOL% and write output
    output_file = os.path.join(script_dir, "phntm_bridge.yaml")
    result = result.replace("%SRC_FILE%", str(args.yaml_file))
    result = result.replace("%ID_ROBOT%", str(data[id_demo]['id_robot']))
    result = result.replace("%ROBOT_KEY%", str(data[id_demo]['robot_key']))
    result = result.replace("%NAME%", str(data[id_demo]['name']))
    result = result.replace("%BRIDGE_SERVER_ADDRESS%", str(data[id_demo]['bridge_server_address']))
    result = result.replace("%LOCATION%", str(data[id_demo]['location']))
    result = result.replace("%DEMO_URL%", str(data[id_demo]['demo_url']))
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(result)
    
    print(f"Processed: {output_file}")

if __name__ == "__main__":
    main()