import sys
import os
from notebook.auth import passwd

config_file = sys.argv[1]

if os.path.isfile(config_file):
    print("Please provide a password for the Jupyter Lab server.\nNote that if you run this command multiple times then multiple 'ServerApp.password' are added but the server will only take into account the last entry.\n\n")
    notebook_pw = passwd()
    if notebook_pw:
        fp = open(config_file, "a+")
        fp.write("\nc.ServerApp.password=\"{}\"\n".format(notebook_pw))
        fp.close()
        print("Password added to {}".format(config_file))
    else:
        print("No password provided. No changes done.")

else:
    print("Configuration file {} does not exist.".format(config_file))