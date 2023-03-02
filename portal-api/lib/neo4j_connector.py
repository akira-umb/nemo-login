import neo4j

POTENTIALLY_MALICIOUS_STRINGS = {";"," delete "," create "," detach "," set ",
                                    " merge ", " call ", " import ", " remove ",
                                    " union ", " drop ", " foreach ", " using ", " unwind "}


class Neo4jConnector:
    ''' 
    This class wraps the Neo4j driver to provide a means of connecting to and
    retrieving data from the Portal Neo4j graph database.
    '''

    def __init__(self, ip_address, bolt_port, username, password):
        ''' Connects to Neo4j server
        '''
        neo4j_uri = "bolt://" + ip_address + ":" + str(bolt_port)
        print("\nConnecting to Neo4j server: {}\n".format(neo4j_uri))
        self.driver = neo4j.GraphDatabase.driver(neo4j_uri, auth=(username, password))

    def close(self):
        self.driver.close()

    def execute_safe_query(self, cypher, **kwargs):
        ''' First verifies that cypher is free of malicious strings. Then runs
        a cypher read transaction.
        Returns cypher results as list of objects.
        '''
        lower_cy = cypher.lower()
        for pms in POTENTIALLY_MALICIOUS_STRINGS:
            if pms in lower_cy:
                print("Potentially unsafe cypher detected: " + cypher)
                print("Skipping")
                raise Exception("Potentially unsafe cypher detected: " + cypher)

        # cypher is now considered safe
        data = []

        try:
            with self.driver.session() as session:
                # Executes a unit of work in managed read transaction. automatically commits and performs 
                # retries on transaction_function
                data = session.read_transaction(self.run_cypher_transaction, cypher, **kwargs)

        except Exception as e:
            print("Error running cypher: ", e)

        return data


    def run_cypher_transaction(self, transaction, cypher, **kwargs):
        ''' Neo4j transaction function that performs a unit of work.
        neo4j.Result.data() returns the retrieved data into a JSON-compatiable structure.
        '''
        result = transaction.run(cypher, **kwargs)
        return result.data()
    
