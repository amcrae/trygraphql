from pathlib import Path
import yaml

from ariadne import gql, QueryType, ObjectType
from ariadne import make_executable_schema
from ariadne.asgi import GraphQL


class SEEntityServer:
    def __init__(self):
        self.gql_types: str  = None
        self.entity_cache: dict = {}
        self.init_schema()
        self.add_data_from_file(Path("./data/r1.yaml"))
        # print(self.entity_cache)

    def init_schema(self):
        with open("./schemas/syseng.graphql") as f:
            schema_text = f.read()
        self.gql_types = gql(schema_text)

    def add_data_from_file(self, yamlfile: Path):
        with open(yamlfile, "r") as yf:
            data = yaml.load(yf, Loader=yaml.SafeLoader)
        for entity in data["entities"]:
            assert len(entity.keys()) == 1, "Expected only one key for typename"
            typename = list(entity.keys())[0]
            edata = entity[typename]
            id = edata["eid"]
            idk = (typename, id)
            self.entity_cache[idk] = edata
    
    def bind_resolvers(self):
        memcache = self.entity_cache
        sequeries = ObjectType("SEQueries")
        req_result = ObjectType("SE_Requirement")

        @sequeries.field("requirements")
        def resolve_requirements(_, info):
            answer = []
            for idk in memcache:
                entity = memcache[idk]
                # TODO: other matching/filtering
                answer.append(entity)
            return answer

        @req_result.field("eid")
        def resolve_eid(par_obj, info):
            return par_obj["eid"]

        @req_result.field("shortName")
        def resolve_shortName(par_obj, info):
            return par_obj["shortName"]
        
        self.schema = make_executable_schema(
            self.gql_types, sequeries, req_result
        )

    def make_wsgi(self):
        self.bind_resolvers()
        self.wsgi_app = GraphQL(self.schema, debug=True)


print("name is ", __name__)

wsgi_app = None

if __name__ == "readonly_server":
    srv = SEEntityServer()
    srv.make_wsgi()
    wsgi_app = srv.wsgi_app

if __name__ == "__main__":
    srv = SEEntityServer()
    srv.make_wsgi()
    print("TODO: use uvicorn framework directly")
