# Pickle deserialization
import pickle

def load_user_data(data):
    return pickle.loads(data)

def deserialize(payload):
    return pickle.load(open('user.pkl', 'rb'))

class User:
    pass