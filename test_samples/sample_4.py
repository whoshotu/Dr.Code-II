# Path Traversal vulnerability
def read_user_file(filename):
    return open("/home/users/" + filename).read()

def get_config(path):
    with open("config/" + path) as f:
        return f.read()

# Using %s formatting
def load_file(filename):
    return open("/var/www/uploads/%s" % filename).read()

# Another pattern
def access_data(user_input):
    path = "/data/" + user_input
    return open(path).read()