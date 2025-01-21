c = get_config()
c.ServerApp.ip = "127.0.0.1"
c.ServerApp.port = 8899
c.ServerApp.open_browser = False
c.ServerApp.allow_root = False
c.ServerApp.allow_password_change = False
c.ContentsManager.untitled_notebook = "MISP Untitled Playbook"

c.ServerApp.root_dir = "/home/azureuser/misp-playbooks/playbooks/my-playbooks/"
c.ServerApp.certfile = "/home/azureuser/misp-playbooks/playbooks/config/playbook-ssl.pem"
c.ServerApp.keyfile = "/home/azureuser/misp-playbooks/playbooks/config/playbook-ssl.key"