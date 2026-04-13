# Command Injection vulnerabilities
import os
import subprocess

def ping_host(hostname):
    os.system("ping -c 1 " + hostname)

def run_command(user_input):
    cmd = "ls -la " + user_input
    subprocess.call(cmd, shell=True)

def execute_script(script_name):
    subprocess.run("python " + script_name, shell=True)

# Another pattern
def process_file(filename):
    os.system(f"cat {filename}")