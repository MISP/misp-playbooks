import json
import sys
import uuid
import nbformat
import re
import base64
from datetime import datetime
import jsonschema
import requests


"""
Convert a MISP playbook to CACAO security playbook
Two arguments:
    MISP playbook ("input.ipynb")
    CACAO playbook ("output.json")

Koen Van Impe - 2024
"""


def sanitize_command(text):
    # Avoid failing schema validation
    control_chars = ''.join(map(chr, range(0, 32)))
    allowed_whitespace = '\t\n\r'
    control_chars = ''.join(c for c in control_chars
                            if c not in allowed_whitespace)
    control_char_re = re.compile('[%s]' % re.escape(control_chars))
    return control_char_re.sub('', text)


def extract_playbook_title(misp_playbook):
    # Assume title of our MISP playbook starts with # in the first MD cell we encounter
    for cell in misp_playbook['cells']:
        if cell['cell_type'] == 'markdown':
            source = ''.join(cell['source']).strip()
            if source:
                lines = source.splitlines()
                for line in lines:
                    stripped_line = line.lstrip('#').strip()
                    if stripped_line:
                        return stripped_line
    return 'Converted MISP Playbook'


def extract_labels(misp_playbook):
    # Convert the tags in the introduction MD cell to labels
    labels = []
    for cell in misp_playbook['cells']:
        if cell['cell_type'] == 'markdown':
            source = ''.join(cell['source'])
            lines = source.splitlines()
            for line in lines:
                if line.strip().startswith('- Tags:'):
                    match = re.search(r'- Tags:\s*\[(.*?)\]', line)
                    if match:
                        tags_str = match.group(1)
                        tags = [tag.strip().strip('"').strip("'")
                                for tag in tags_str.split(',')]
                        labels.extend(tags)
                    break
            break
    return labels


def extract_playbook_activities(misp_playbook):
    # Use the 2-nd level headers to list the playbook activities
    activities = []
    activity_pattern = re.compile(r'[A-Z]{2}:[0-9]\s.*$')
    for cell in misp_playbook['cells']:
        if cell['cell_type'] == 'markdown':
            source = ''.join(cell['source'])
            lines = source.splitlines()
            for line in lines:
                if line.startswith('##'):
                    activity = line.lstrip('#').strip()
                    if activity_pattern.match(activity):
                        activities.append(activity)
    return activities


def extract_external_references(misp_playbook):
    # Add these references to the default external references
    external_refs = []
    for cell in misp_playbook['cells']:
        if cell['cell_type'] == 'markdown':
            source = ''.join(cell['source'])
            if '## External references' in source:
                lines = source.splitlines()
                for line in lines:
                    urls = re.findall(r'(https?://\S+)', line)
                    for url in urls:
                        external_refs.append({
                            "url": url,
                            "name": url
                        })
                break
    return external_refs


def misp_playbook_to_cacao_playbook(misp_playbook_path, output_cacao_path):
    with open(misp_playbook_path, 'r', encoding='utf-8') as f:
        misp_playbook = nbformat.read(f, as_version=4)

    playbook_title = extract_playbook_title(misp_playbook)
    labels = extract_labels(misp_playbook)
    playbook_activities = extract_playbook_activities(misp_playbook)
    external_references = [
        {
            "name": "MISP",
            "url": "https://github.com/MISP/MISP"
        },
        {
            "name": "MISP Playbook GitHub Repository",
            "url": "https://github.com/MISP/misp-playbooks"
        }
    ]
    additional_refs = extract_external_references(misp_playbook)
    external_references.extend(additional_refs)

    playbook_id = f"playbook--{str(uuid.uuid4())}"
    playbook = {
        "type": "playbook",
        "spec_version": "cacao-2.0",
        "id": playbook_id,
        "created": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "modified": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "created_by": f"identity--{str(uuid.uuid4())}",
        "name": playbook_title,
        "description": playbook_title,
        "labels": labels,
        "playbook_types": ["investigation"],
        "playbook_activities": playbook_activities,
        "workflow_start": "",
        "workflow": {},
        "agent_definitions": {},
        "target_definitions": {},
        "external_references": external_references
    }

    agent_definitions = {}
    agent_id = f"group--{str(uuid.uuid4())}"
    agent_definitions[agent_id] = {
        "type": "group",
        "name": "MISP playbook users",
        "description": "Users responsible for executing MISP playbooks"
    }
    playbook["agent_definitions"] = agent_definitions

    target_definitions = {}
    target_id = f"security-category--{str(uuid.uuid4())}"
    target_definitions[target_id] = {
        "type": "security-category",
        "name": "MISP playbooks",
        "category": ["MISP playbook", "Jupyter Notebook infrastructure"]
    }
    playbook["target_definitions"] = target_definitions

    previous_step_id = None
    last_markdown_cell = None
    accumulated_code = []

    start_step_id = f"start--{str(uuid.uuid4())}"
    playbook['workflow_start'] = start_step_id
    playbook['workflow'][start_step_id] = {
        "type": "start",
        "name": "Start of Playbook"
    }
    previous_step_id = start_step_id

    end_of_playbook_reached = False
    skip_headings = ['# Playbook', '## Technical details', '## External references']

    idx = -1
    while idx + 1 < len(misp_playbook['cells']):
        idx += 1
        cell = misp_playbook['cells'][idx]

        if end_of_playbook_reached:
            break

        cell_type = cell['cell_type']
        source = ''.join(cell['source']).strip()
        if not source:
            continue

        if cell_type == 'markdown' and any(
                source.strip().startswith(heading) for heading in skip_headings):
            continue

        if 'End of the playbook' in source:
            end_of_playbook_reached = True

        if cell_type == 'markdown':
            first_line = source.split('\n')[0].strip()
            if not first_line.startswith('##'):
                try:
                    if first_line.startswith('# ') and source.split('\n')[1].strip().startswith('## '):
                        activity_name = source.split('\n')[1].lstrip('#').strip()
                    elif first_line.startswith('# ') and source.split('\n')[2].strip().startswith('## '):
                        activity_name = source.split('\n')[2].lstrip('#'). strip()
                    else:
                        continue
                except:
                    continue
            else:
                activity_name = first_line.lstrip('#').strip()

            last_markdown_cell = source

            accumulated_code = []
            next_idx = idx + 1
            while next_idx < len(misp_playbook['cells']):
                next_cell = misp_playbook['cells'][next_idx]
                next_source = ''.join(next_cell['source']).strip()
                if next_cell['cell_type'] == 'code' and next_source:
                    sanitized_code = sanitize_command(next_source)
                    accumulated_code.append(sanitized_code)
                    idx = next_idx
                else:
                    break
                next_idx += 1

            step_id = f"action--{str(uuid.uuid4())}"
            step = {
                "type": "action",
                "name": activity_name,
                "description": last_markdown_cell,
                "commands": [
                    {
                        "type": "manual",
                        "command": '\n'.join(accumulated_code)
                    }
                ],
                "agent": agent_id,
                "targets": [target_id]
            }
            playbook['workflow'][step_id] = step

            if 'on_completion' not in playbook['workflow'][previous_step_id]:
                playbook['workflow'][previous_step_id]['on_completion'] = step_id
            previous_step_id = step_id
            last_markdown_cell = None

    final_action_id = f"action--{str(uuid.uuid4())}"
    with open(misp_playbook_path, 'rb') as f:
        notebook_content = f.read()
    notebook_base64 = base64.b64encode(notebook_content).decode('utf-8')
    final_command = {
        "type": "jupyter",
        "command_b64": notebook_base64
    }
    final_action_step = {
        "type": "action",
        "name": "MISP Playbook",
        "description": "Copy of the MISP Playbook",
        "commands": [final_command],
        "agent": agent_id,
        "targets": [target_id]
    }
    playbook['workflow'][final_action_id] = final_action_step

    if 'on_completion' not in playbook['workflow'][previous_step_id]:
        playbook['workflow'][previous_step_id]['on_completion'] = final_action_id
    previous_step_id = final_action_id

    end_step_id = f"end--{str(uuid.uuid4())}"
    playbook['workflow'][end_step_id] = {
        "type": "end",
        "name": "End of Playbook"
    }

    if 'on_completion' not in playbook['workflow'][previous_step_id]:
        playbook['workflow'][previous_step_id]['on_completion'] = end_step_id

    try:
        schema_url = "https://raw.githubusercontent.com/oasis-open/cacao-json-schemas/main/schemas/playbook.json"
        response = requests.get(schema_url)
        response.raise_for_status()
        schema = response.json()

        jsonschema.validate(instance=playbook, schema=schema)
        print("CACAO playbook is valid according to the schema.")

        with open(output_cacao_path, 'w', encoding='utf-8') as f:
            json.dump(playbook, f, indent=4, ensure_ascii=False)

        print(f"CACAO playbook created at {output_cacao_path}")
        print(f"  Skipped {skip_headings}")

    except jsonschema.ValidationError as e:
        print("Schema validation error:", e.message)
        print("Failed element:", json.dumps(e.instance, indent=4))
        print("Schema path:", list(e.absolute_schema_path))
        sys.exit(1)
    except Exception as e:
        print("An error occurred during validation:", str(e))
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python misp_notebook_to_cacao_playbook.py <input_misp_playbook.ipynb> <output_cacao_playbook.json>")
        sys.exit(1)

    input_misp_playbook = sys.argv[1]
    output_cacao_playbook = sys.argv[2]

    misp_playbook_to_cacao_playbook(input_misp_playbook, output_cacao_playbook)
