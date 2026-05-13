import subprocess
output = subprocess.call(['sudo','ntfsfix','/dev/sda1'])
if output != 1:
    output = subprocess.call(['sudo','mount','/dev/sda1'])



    