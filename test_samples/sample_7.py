# Eval/Exec usage
user_input = input("Enter code: ")
result = eval(user_input)

def run_dynamic(code):
    exec(code)

def calculate(expression):
    return eval(expression)