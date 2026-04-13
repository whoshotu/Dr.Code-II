# SQL Injection vulnerability
def get_user_by_id(user_id):
    query = "SELECT * FROM users WHERE id = '%s'" % user_id
    return execute(query)

# Another SQL injection pattern
def authenticate(username, password):
    sql = "SELECT * FROM users WHERE name = '%s' AND password = '%s'" % (username, password)
    return db.execute(sql)

# Third pattern
def search_users(search_term):
    query = "SELECT * FROM users WHERE name LIKE '%" + search_term + "%'"
    cursor.execute(query)