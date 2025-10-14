"""
Create a JSON file of all available playbooks.
Koen Van Impe

Output:
- Two JSON files are created
    - playbook_json: JSON file with all details of the playbooks
    - playbooks_JupyterUniverse_json: JSON file which can be submitted to JupyterUniverse (https://github.com/fr0gger/JupyterUniverse)

Usage:

Configuration:
- playbook_directory: directory where the playbooks can be found (make sure it ends with '/')
- playbook_exclude: playbooks to exclude (typically those with output, to avoid doubles)
- playbook_authors: playbook authors
- playbook_base_url: URL which points to the GitHub repository

"""
import glob
import json
import re

playbook_directory = "misp-playbooks/"
playbook_exclude = "-with_output"
playbook_authors = ["Koen Van Impe"]
playbook_default_tags = ["misp", "playbook", "Threat Intel", "IOC"]
playbook_base_url = "https://github.com/MISP/misp-playbooks/blob/main/"

playbook_json = "playbook.json"
playbooks_JupyterUniverse_json = "playbook_JupyterUniverse.json"
playbooks = []
playbooks_JupyterUniverse = []

# Read all the playbook files
ipynb_files = glob.glob(playbook_directory + 'pb*.ipynb')
for file_path in ipynb_files:
    with open(file_path, 'r', encoding='utf-8') as f:
        if playbook_exclude in f.name:
            continue
        notebook_content = json.load(f)

        # Read first cell
        first_cell_content = notebook_content["cells"][0]["source"]

        # Get the title
        first_line = first_cell_content[0].split("\n")[0] 
        first_line_without_markup = re.sub(r'<.*?>', '', first_line)
        first_line_without_markup = re.sub(r'^\s*#*\s*', '', first_line_without_markup)
        playbook_title = first_line_without_markup

        # Build the URL to the repo
        playbook_url = "{}/{}".format(playbook_base_url, f.name)

        # Extract playbook purpose
        match = re.search(r'- Purpose:(.*?)\n- Tags:', ''.join(first_cell_content), re.DOTALL)
        playbook_purpose = ""
        if match:
            purpose_text = match.group(1).strip()
            playbook_purpose = re.sub(r'\*\*|\[.*?\]|\n|- |\*', '', purpose_text).strip()
            playbook_purpose = re.sub(r'\s+', ' ', playbook_purpose)

        # Extract elements
        for t in first_cell_content:
            if "- Tags" in t:
                tag_line = t.split("Tags: ")[1].strip()
                tag_line = json.loads(tag_line)
                playbook_tags = playbook_default_tags + tag_line             
            if "- Started from" in t:
                pattern = r'\((.*?)\)'
                playbook_issue = re.search(pattern, t).group(1)
            if "- UUID" in t:
                pattern = r'\*\*(.*?)\*\*'
                playbook_uuid = re.search(pattern, t).group(1)

        # Add to our list
        playbooks.append({"description": playbook_title, "tags": playbook_tags, "link": playbook_url, "authors": playbook_authors, "uuid": playbook_uuid, "issue": playbook_issue, "purpose": playbook_purpose})
        playbooks_JupyterUniverse.append({"description": playbook_title, "tags": playbook_tags, "link": playbook_url, "authors": playbook_authors})

# Write out the JSON files
if len(playbooks) > 0:
    with open(playbook_json, 'w') as f:
        json.dump(playbooks, f, indent=4)
    print("File {} written".format(playbook_json))
    with open(playbooks_JupyterUniverse_json, 'w') as f:
        json.dump(playbooks_JupyterUniverse, f, indent=4)
    print("File {} written".format(playbooks_JupyterUniverse_json))    
else:
    print("No playbooks found, no JSON files written.")
