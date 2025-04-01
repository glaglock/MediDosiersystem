import sqlite3

def initialize_database():
    connection = sqlite3.connect('database.db')
    
    with open('schema.sql', encoding='latin-1') as f:
        connection.executescript(f.read())
    
    connection.commit()
    connection.close()

if __name__ == "__main__":
    initialize_database()

    