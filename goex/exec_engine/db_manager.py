from exec_engine.docker_sandbox import DockerSandbox
import json

"""
    This module will handle all database interactions
    The DBManager class is the base class for all database managers
"""

class DBManager:
    """Base class for all DB connectors.

    Attributes:
        connection_config (type): JSON Config for connection.

    Methods:
        connect: Establish connections to the DB
        execute_db_call: Execute DB call
        commit_db_calls: Commit DB calls
        rollback_db_calls: Rollback DB calls
        close: Close the connection to the database

    """

    def __init__(self, connection_config):
        """Initialize the DBManager.
        
        Args:
            connection_config (dict): Configuration for connecting to the database. This can be a path for file-based databases or connection details for server-based databases.

        """
        self.connection_config = connection_config
        self.docker_sandbox = None

    def connect(self):
        """Establish connection to the database."""
        raise NotImplementedError
    
    def get_schema_as_string(self):
        prompt = ""
        for table_name, schema in self.schema.items():
            prompt += f"Table '{table_name}':\n"
            for column in schema:
                column_name, column_type, is_nullable, key, default, extra = column
                prompt += f"- Column '{column_name}' of type '{column_type}'"
                if is_nullable == 'NO':
                    prompt += ", not nullable"
                if key == 'PRI':
                    prompt += ", primary key"
                prompt += "\n"
            prompt += "\n"
        return prompt
    
    def task_to_prompt(self, task_description, forward=True):
        """Format the schemas of all tables into a prompt for GPT, including a task description."""
        prompt = ""

        if self.schema == None:
            raise Exception("Please connect to the database first.")
        
        if self.schema:
            "No schema information available."
            prompt += "Given the following table schemas in a sqlite database:\n\n"
            prompt += self.get_schema_as_string()
        
        if forward:
            prompt += f"Task: {task_description}\n\n"
            prompt += "Based on the task, select the most appropriate table and generate an SQL command to complete the task. In the output, only include SQL code."
        else:
            prompt += f"SQL command: {task_description}\n\n"
            prompt += "Based on the SQL command and the given table schemas, generate a reverse command to reverse the SQL command. In the output, only include SQL code."
        return prompt

    def execute_db_call(self, call):
        """Execute DB call.
        
        Args:
            call (str): DB call to execute.
        """
        raise NotImplementedError
    
    def fetch_db_call(self, call):
        raise NotImplementedError
    
    def commit_db_calls(self):
        """Commit DB calls."""
        raise NotImplementedError
    
    def rollback_db_calls(self):
        """Rollback DB calls not committed"""
        raise NotImplementedError

    def close(self):
        """Close the connection to the database."""
        raise NotImplementedError


class SQLiteManager(DBManager):
    """SQLite database manager.
    
    Attributes:
        _sqlite_imported (bool): flag to check if sqlite3 is imported.
        
    Methods:
        connect: Establish connections to the DB
        execute_db_call: Execute SQL call
        commit_db_calls: Commit SQL calls
        rollback_db_calls: Rollback SQL calls
        close: Close the connection to the database
    """
    _sqlite_imported = False  # flag to check if sqlite3 is imported
    db_type = "sqlite"
    TEST_CONFIG = "" # No config required to access sqlite
    def __init__(self, connection_config, docker_sandbox: DockerSandbox = None):
        """Initialize the SQLLiteManager.

        Args:
            connection_config(str): path to the database file.
        """
        if not SQLiteManager._sqlite_imported:
            global sqlite3
            import sqlite3
            SQLiteManager._sqlite_imported = True
        keys = connection_config.keys()

        if any(key not in keys for key in ['path']):
            raise ValueError("Failed to initialize SQLite Manager due to bad configs")

        self.db_path = connection_config['path']
        if not self.db_path:
            raise ValueError("Failed to initialize SQLite Manager due to missing path")

    def update_schema_info(self):
        schema_info = {}
        
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = self.cursor.fetchall()
        for (table_name,) in tables:
            self.cursor.execute(f"PRAGMA table_info({table_name});")
            schema_info[table_name] = self.cursor.fetchall()
        
        self.schema = schema_info

    def connect(self):
        """Establish connection to the SQLLite3 database and create a cursor."""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.update_schema_info()
        
    
    def execute_db_call(self, call):
        if not self.conn:
            self.connect()
        try:
            commands_list = [cmd.strip() for cmd in call.split(';') if cmd.strip() and not cmd.strip().startswith('--')]
            for command in commands_list:
                if command.upper().startswith('SELECT'):
                    self.cursor.execute(command)
                    print(self.cursor.fetchall())
                else:
                    self.cursor.execute(command)
            self.update_schema_info()
            return 0
        except Exception as e:
            return 1

    
    def fetch_db_call(self, call):
        if not self.conn:
            self.connect()
        try:
            self.cursor.execute(call)
            ret_val = self.cursor.fetchall()
            self.update_schema_info()
            return ret_val
        except Exception as e:
            return []

    def commit_db_calls(self):
        """Commit SQL calls."""
        if not self.conn:
            self.connect()
        self.conn.commit()

    def rollback_db_calls(self):
        """Rollback SQL calls not committed"""
        if not self.conn:
            self.connect()
        self.conn.rollback()
        self.close()
        self.connect()

    def close(self):
        if self.conn:
            self.cursor.close()
            self.conn.close()


class MySQLManager(DBManager):
    """MySQL database manager.
    
    Attributes:
        _mysql_imported (bool): flag to check if pymysql is imported.
        
    Methods:
        connect: Establish connections to the DB
        execute_db_call: Execute SQL call
        commit_db_calls: Commit SQL calls
        rollback_db_calls: Rollback SQL calls
        close: Close the connection to the database
    """
    _mysql_imported = False
    db_type = "mysql"
    TEST_CONFIG = "{'host': '127.0.0.1', 'user': 'root', 'password': ''}\n Use Pymysql and make sure to create the database using subprocess before connection."
    def __init__(self, connection_config, docker_sandbox: DockerSandbox = None):
        """Initialize the MySQLManager.

        Args:
            connection_config (dict): configuration for the database connection, including keys for 'user', 'password', 'host', and 'database'.
        """
        if not MySQLManager._mysql_imported:
            global pymysql
            import pymysql
            MySQLManager._mysql_imported = True
        
        keys = connection_config.keys()

        if any(key not in keys for key in ['host', 'user', 'password', 'database']):
            raise ValueError("Failed to initialize MySQL Manager due to bad configs")
        elif any([not connection_config['host'], not connection_config['user'], not connection_config['password'], not connection_config['database']]):
            raise ValueError("Failed to initialize MySQL Manager due to missing configs")

        self.connection_config = {
            'host': connection_config['host'],
            'user': connection_config['user'],
            'password': connection_config['password'],
            'database': connection_config['database'],
            "client_flag": pymysql.constants.CLIENT.MULTI_STATEMENTS
        }

    def connect(self):
        """Establish connection to the MySQL database and create a cursor."""
        self.conn = pymysql.connect(**self.connection_config)
        self.cursor = self.conn.cursor()
        self.update_schema_info()

    def update_schema_info(self):
        schema_info = {}
        
        self.cursor.execute("SHOW TABLES")
        tables = self.cursor.fetchall()
        for (table_name,) in tables:
            self.cursor.execute(f"DESCRIBE {table_name}")
            schema_info[table_name] = self.cursor.fetchall()
        
        self.schema = schema_info
    
    def execute_db_call(self, call):
        """Execute a SQL call using the cursor."""
        if not self.conn:
            self.connect()
        try:
            self.cursor.execute(call)
            self.update_schema_info()
            return 0
        except Exception as e:
            return 1

    def fetch_db_call(self, call: str) -> list[dict]:
        """Execute a SQL call and return the results.
        
        Args:
            call (str): SQL query to execute.
        
        Returns:
            list[dict]: A list of dictionaries representing each row in the query result.
        """
        if not self.conn:
            self.connect()
        try:
            self.cursor.execute(call)
            ret_val = self.cursor.fetchall()
            self.update_schema_info()
            return ret_val
        except Exception as e:
            return []

    def commit_db_calls(self):
        """Commit SQL calls."""
        if not self.conn:
            self.connect()
        self.conn.commit()

    def rollback_db_calls(self):
        """Rollback SQL calls not committed."""
        if not self.conn:
            self.connect()
        self.conn.rollback()

    def close(self):
        """Close the cursor and the connection to the database."""
        if self.conn:
            self.cursor.close()
            self.conn.close()

class PostgreSQLManager(DBManager):
    """PostgreSQL database manager.
    
    Attributes:
        _postgresql_imported (bool): flag to check if postgresql is imported.
        
    Methods:
        connect: Establish connections to the DB
        execute_db_call: Execute SQL call
        commit_db_calls: Commit SQL calls
        rollback_db_calls: Rollback SQL calls
        close: Close the connection to the database
    """
    _postgresql_imported = False
    db_type = "postgresql"
    TEST_CONFIG = "{'host': '127.0.0.1', 'user': 'root', 'password': ''}\n Use psycopg2 and make sure to create the database using subprocess before connection."
    def __init__(self, connection_config, docker_sandbox: DockerSandbox = None):
        """Initialize the PostgreSQLManager.

        Args:
            connection_config (dict): configuration for the database connection, including keys for 'user', 'password', 'host', and 'database'.
        """
        if not PostgreSQLManager._postgresql_imported:
            global psycopg2
            import psycopg2
            PostgreSQLManager._postgresql_imported = True
        
        keys = connection_config.keys()

        if any(key not in keys for key in ['host', 'user', 'password', 'database']):
            raise ValueError("Failed to initialize PostgreSQL Manager due to bad configs")
        elif any([not connection_config['host'], not connection_config['user'], not connection_config['password'], not connection_config['database']]):
            raise ValueError("Failed to initialize PostgreSQL Manager due to missing configs")

        self.connection_config = {
            'dbname': connection_config['database'] if 'database' in connection_config else 'postgres',
            'user': connection_config['user'] if 'user' in connection_config else 'postgres',
            'password': connection_config['password'] if 'password' in connection_config else '',
            'host': connection_config['host'] if 'host' in connection_config else '127.0.0.1'
        }

    def connect(self):
        """Establish connection to the MySQL database and create a cursor."""
        connection = None
        try:
            connection = psycopg2.connect(**self.connection_config)
            self.conn = connection
            self.cursor = connection.cursor()
            self.update_schema_info()
        except Exception as e:
            if connection:
                connection.close()
            print("Failed to connect to the database. Error:", e)

    def update_schema_info(self):
        schema_info = {}
        get_all_tables_query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        """
        self.cursor.execute(get_all_tables_query)
        tables = self.cursor.fetchall()
        for (table_name,) in tables:
            self.cursor.execute(f"SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name = '{table_name}';")
            schema_info[table_name] = self.cursor.fetchall()
        
        self.schema = schema_info
    
    def execute_db_call(self, call):
        """Execute a SQL call using the cursor."""
        if not self.conn:
            self.connect()
        try:
            self.cursor.execute(call)
            self.update_schema_info()
            return 0
        except Exception as e:
            return 1

    def fetch_db_call(self, call: str) -> list[dict]:
        """Execute a SQL call and return the results.
        
        Args:
            call (str): SQL query to execute.
        
        Returns:
            list[dict]: A list of dictionaries representing each row in the query result.
        """
        if not self.conn:
            self.connect()
        try:
            self.cursor.execute(call)
            ret_val = self.cursor.fetchall()
            self.update_schema_info()
            return ret_val
        except Exception as e:
            return []

    def commit_db_calls(self):
        """Commit SQL calls."""
        if not self.conn:
            self.connect()
        self.conn.commit()

    def rollback_db_calls(self):
        """Rollback SQL calls not committed."""
        if not self.conn:
            self.connect()
        self.conn.rollback()

    def close(self):
        """Close the cursor and the connection to the database."""
        if self.conn:
            self.cursor.close()
            self.conn.close()

class MongoDBManager(DBManager):
    """MongoDB database manager.
    
    Attributes:
        _mongodb_imported (bool): flag to check if mongodb is imported.
        
    Methods:
        connect: Establish connections to the DB
        execute_db_call: Execute SQL call
        commit_db_calls: Commit SQL calls
        rollback_db_calls: Rollback SQL calls
        close: Close the connection to the database
    """
    _mongodb_imported = False
    db_type = "mongodb"
    TEST_CONFIG = "{'host': '127.0.0.1', 'user': 'root', 'password': ''}\n Use pymongo and make sure to create the database using subprocess before connection."
    def __init__(self, connection_config, docker_sandbox: DockerSandbox = None):
        """Initialize the MongoDBManager.

        Args:
            connection_config (dict): configuration for the database connection, including keys for 'user', 'password', 'host', and 'database'.
        """
        if not MongoDBManager._mongodb_imported:
            global pymongo
            global Code
            import pymongo
            from bson.code import Code
            MongoDBManager._mongodb_imported = True
        
        keys = connection_config.keys()

        if 'host' not in keys:
            raise ValueError("Failed to initialize MongoDB Manager due to bad configs")

        self.connection_config = {
            'host': connection_config['host'] if 'host' in connection_config else '127.0.0.1',
            'port': connection_config['port'] if 'port' in connection_config else '27017',
            'password': connection_config['password'] if 'password' in connection_config else '',
            'dbname': connection_config['database'] if 'database' in connection_config else 'mydb',
        }

    def connect(self):
        """Establish connection to the MySQL database and create a cursor."""
        connection = None
        try:
            connection = pymongo.MongoClient(self.connection_config['host'], self.connection_config['port'])
            self.conn = connection
            self.db = connection[self.connection_config['dbname']]
            self.update_schema_info()
        except Exception as e:
            if connection:
                connection.close()
            print("Failed to connect to the database. Error:", e)
    
    def update_schema_info(self):
        """
        MongoDB does not have a schema, so this function will list all collections in the database.
        """
        schema_info = {}
        filter = {"name": {"$regex": r"^(?!system\.)"}}
        collections = self.db.list_collection_names(filter=filter)
        for collection in collections:
            schema_info[collection] = self.db[collection].find_one()
        self.schema = schema_info

    def execute_db_call(self, call):
        """
        Executes a MongoDB operation based on a JSON-formatted string command.
        Args:
            call (str): JSON-formatted string command
        """
        if not self.conn:
            self.connect()
        try:
            # Parse the command string (assumes JSON format)
            command = json.loads(call)

            # Extract operation details
            operation = command.get("operation")
            collection_name = command.get("collection")
            data = command.get("data", {})
            query = command.get("query", {})
            options = command.get("options", {})
            
            # For aggregate, the data field is expected to be the pipeline
            if operation == 'aggregate':
                result = self.db[collection_name].aggregate(data, **options)
                print(list(result))

            # Insert operations
            elif operation == 'insert_one':
                result = self.db[collection_name].insert_one(data)
                print({"inserted_id": result.inserted_id})
            
            elif operation == 'insert_many':
                result = self.db[collection_name].insert_many(data)
                print({"inserted_ids": result.inserted_ids})

            # Find operations
            elif operation == 'find':
                results = self.db[collection_name].find(query, **options)
                print(list(results))
            
            elif operation == 'find_one':
                result = self.db[collection_name].find_one(query, **options)
                print(result)

            # Update operations
            elif operation == 'update_one':
                result = self.db[collection_name].update_one(query, data, **options)
                print({"matched_count": result.matched_count, "modified_count": result.modified_count})
            
            elif operation == 'update_many':
                result = self.db[collection_name].update_many(query, data, **options)
                print({"matched_count": result.matched_count, "modified_count": result.modified_count})

            # Delete operations
            elif operation == 'delete_one':
                result = self.db[collection_name].delete_one(query)
                print({"deleted_count": result.deleted_count})
            
            elif operation == 'delete_many':
                result = self.db[collection_name].delete_many(query)
                print({"deleted_count": result.deleted_count})

            # MongoDB command (e.g., serverStatus, dbStats)
            elif operation == 'command':
                result = self.db.command(data, **options)
                print(result)

            else:
                raise ValueError("Unsupported operation type")
            self.update_schema_info()
            return 0

        except Exception as e:
            print("Error:", e)
            return 1
    
    def fetch_db_call(self, call):
        """
        Executes a MongoDB operation based on a JSON-formatted string command.
        Args:
            call (str): JSON-formatted string command
        """
        if not self.conn:
            self.connect()
        try:
            # Parse the command string (assumes JSON format)
            command = json.loads(call)

            # Extract operation details
            operation = command.get("operation")
            collection_name = command.get("collection")
            data = command.get("data", {})
            query = command.get("query", {})
            options = command.get("options", {})
            
            # For aggregate, the data field is expected to be the pipeline
            if operation == 'aggregate':
                result = self.db[collection_name].aggregate(data, **options)
                return list(result)

            # Insert operations
            elif operation == 'insert_one':
                result = self.db[collection_name].insert_one(data)
                return {"inserted_id": result.inserted_id}
            
            elif operation == 'insert_many':
                result = self.db[collection_name].insert_many(data)
                return {"inserted_ids": result.inserted_ids}

            # Find operations
            elif operation == 'find':
                results = self.db[collection_name].find(query, **options)
                return list(results)
            
            elif operation == 'find_one':
                result = self.db[collection_name].find_one(query, **options)
                return result

            # Update operations
            elif operation == 'update_one':
                result = self.db[collection_name].update_one(query, data, **options)
                return {"matched_count": result.matched_count, "modified_count": result.modified_count}
            
            elif operation == 'update_many':
                result = self.db[collection_name].update_many(query, data, **options)
                return {"matched_count": result.matched_count, "modified_count": result.modified_count}

            # Delete operations
            elif operation == 'delete_one':
                result = self.db[collection_name].delete_one(query)
                return {"deleted_count": result.deleted_count}
            
            elif operation == 'delete_many':
                result = self.db[collection_name].delete_many(query)
                return {"deleted_count": result.deleted_count}

            # MongoDB command (e.g., serverStatus, dbStats)
            elif operation == 'command':
                result = self.db.command(data, **options)
                return result

            else:
                raise ValueError("Unsupported operation type")
            self.update_schema_info()
            return 0

        except Exception as e:
            print("Error:", e)
            return 1
    
    def commit_db_calls(self):
        print("MongoDB does not support transactions. Changes are automatically committed to the database.")
    
    def rollback_db_calls(self):
        print("MongoDB does not support transactions. Changes are automatically committed to the database.")

    def close(self):
        """Close the cursor and the connection to the database."""
        if self.conn:
            self.conn.close()
    
    # def fetch_db_call(self, call):
    #     if not self.conn:
    #         self.connect()
    #     try:
    #         self.conn.eval(call)

    
if __name__ == '__main__':
    mongodb_manager = MongoDBManager({'host': 'localhost', 'port': 27017, 'database': 'test_db'})
    mongodb_manager.connect()
    print(mongodb_manager.db)
    mongodb_manager.update_schema_info()
    print(mongodb_manager.schema)
    sample_command = '''
    {
        "operation": "insert_one",
        "collection": "test_c",
        "data": {
            "name": "Adrian",
            "age": 99
        }
    }
    '''
    mongodb_manager.fetch_db_call(sample_command)
    mongodb_manager.commit_db_calls()
    mongodb_manager.close()
