c = get_config()
c.ServerApp.ip = "*"
c.ServerApp.port = 8899
c.ServerApp.open_browser = False
c.ServerApp.allow_root = False
c.ServerApp.allow_password_change = False
c.ContentsManager.untitled_notebook = "MISP Untitled Playbook"


c.ServerApp.root_dir = "/home/playbook/misp-playbooks/playbook/notebooks/"
c.ServerApp.certfile = "/home/playbook/misp-playbooks/playbook/config/playbook-ssl.pem"
c.ServerApp.keyfile = "/home/playbook/misp-playbooks/playbook/config/playbook-ssl.key"
