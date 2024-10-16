import json
import sys
import uuid
import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell
import re
import base64


"""
Convert a CACAO security playbook to MISP playbook
Two arguments:
    CACAO playbook ("input.json")
    MISP playbook ("output.ipynb")

Koen Van Impe - 2024
"""


def cacao_playbook_to_misp_playbook(playbook_path, output_misp_playbook_path):
    with open(playbook_path, 'r', encoding='utf-8') as f:
        playbook = json.load(f)

    nb = new_notebook()
    cells = []

    workflow = playbook.get('workflow', {})
    workflow_start = playbook.get('workflow_start')

    visited = set()
    steps = []

    def traverse_workflow(step_id):
        # inline def to walk through the workflow steps
        if step_id in visited or step_id not in workflow:
            return
        visited.add(step_id)
        step = workflow[step_id]
        steps.append((step_id, step))

        on_completion = step.get('on_completion')   # Continue based on 'on_completion'
        if isinstance(on_completion, str):
            traverse_workflow(on_completion)
        elif isinstance(on_completion, list):
            for next_step_id in on_completion:
                traverse_workflow(next_step_id)

    traverse_workflow(workflow_start)

    for step_id, step in steps:
        step_type = step.get('type')
        if step_type == 'action':
            name = step.get('name', '')
            description = step.get('description', '')

            # Don't add the MISP playbook from the b64command
            if name == 'MISP Playbook' and description == 'Copy of the MISP Playbook':
                continue

            commands = step.get('commands', [])

            markdown_content = f"{description}"
            if len(markdown_content.strip()) > 0:
                if not description.startswith("#"):
                    markdown_content = f"# {name} \n{markdown_content}"
                cells.append(new_markdown_cell(markdown_content))

            for command in commands:
                command_type = command.get('type')
                if command_type == 'manual':
                    code_content = command.get('command', '')
                    if len(code_content.strip()) > 0:
                        cells.append(new_code_cell(code_content))
                elif command_type == 'jupyter':
                    notebook_b64 = command.get('command_b64', '')
                    notebook_json = base64.b64decode(notebook_b64).decode('utf-8')
                    embedded_nb = nbformat.reads(notebook_json, as_version=4)
                    cells.extend(embedded_nb.cells)
                else:
                    code_content = command.get('command', '')
                    if len(code_content.strip()) > 0:
                        markdown_content = f"Execute as type `{command_type}`\n\n```{code_content}```\n"
                        cells.append(new_markdown_cell(markdown_content))

        elif step_type == 'start' or step_type == 'end':
            continue
        else:
            pass

    nb['cells'] = cells

    with open(output_misp_playbook_path, 'w', encoding='utf-8') as f:
        nbformat.write(nb, f)

    print(f"MISP playbook created at {output_misp_playbook_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Convert a CACAO security playbook to a MISP Playbook.")
        print("Usage: python cacao_playbook_to_misp_playbook.py <input_playbook.json> <output_misp_playbook.ipynb>")
        sys.exit(1)

    input_playbook_path = sys.argv[1]
    output_misp_playbook = sys.argv[2]

    cacao_playbook_to_misp_playbook(input_playbook_path, output_misp_playbook)
