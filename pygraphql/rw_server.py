from typing import Any, List, Dict, AsyncGenerator
from collections import OrderedDict
from pathlib import Path
import yaml

import asyncio
from asyncio import Queue, QueueEmpty

from graphql import GraphQLResolveInfo

from ariadne import gql, QueryType, ObjectType, SubscriptionType
from ariadne import make_executable_schema
from ariadne.asgi import GraphQL

from ariadne.asgi.handlers import GraphQLWSHandler


class SEEntityServer:
    def __init__(self):
        self.gql_types: str  = None
        self.entity_cache: dict = {}
        self.init_schema()
        self.add_data_from_file(Path("./data/r1.yaml"))
        self.nextId = 1001
        self.new_entity_events = Queue(1000)
        # print(self.entity_cache)

    def init_schema(self):
        with open("./schemas/syseng.graphql") as f:
            schema_text = f.read()
        self.gql_types = gql(schema_text)
        print("Ariadne schema check was OK.")

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
        
        # Ariadne has some built-in default resolvers
        # apparently which can return the fields of dicts.
        """  
        @req_result.field("eid")
        def resolve_eid(par_obj, info):
            return par_obj["eid"]

        @req_result.field("shortName")
        def resolve_shortName(par_obj, info):
            return par_obj["shortName"]
        """

        semutations = ObjectType("SEMutations")
        
        @semutations.field("createRequirement")
        def resolve_create_requirement(par_obj, info, newreq):
            eid = "R%05d" % self.nextId
            self.nextId += 1
            typename = "SERequirement"
            idk = (typename, eid)
            entity = OrderedDict(newreq)
            entity["eid"] = eid
            memcache[idk] = entity
            self.new_entity_events.put_nowait(entity)
            return entity

        sesubs = SubscriptionType()

        @sesubs.source("newReqs")
        async def gen_newreqs(
            obj: Any, 
            info: GraphQLResolveInfo
        ) -> AsyncGenerator[List[Dict], None]:
            batch = []
            print("Starting sub loop")
            while True:
                print("checking event queue with wait")
                ne = await self.new_entity_events.get()
                batch.append(ne)
                print("appended a new event")
                try:
                    while True:     # exit by exception
                        print("checking event queue instantly")
                        ne = await self.new_entity_events.get_nowait()
                        batch.append(ne)
                        print("appended a new event")
                        await asyncio.sleep(delay=0.05)
                except QueueEmpty as qe:
                    pass
                print("yielding event batch", batch)
                yield batch
                batch = []

        
        @sesubs.field("newReqs")
        def resolve_newreqs(reqs:List[Dict], info):
            return reqs

        self.schema = make_executable_schema(
            self.gql_types, sequeries, req_result, 
            semutations, sesubs
        )

    def make_wsgi(self):
        self.bind_resolvers()
        self.wsgi_app = GraphQL(
            self.schema, 
            websocket_handler=GraphQLWSHandler(), 
            debug=True
        )


print("name is ", __name__)

wsgi_app = None

if __name__ == "rw_server":
    srv = SEEntityServer()
    srv.make_wsgi()
    wsgi_app = srv.wsgi_app

if __name__ == "__main__":
    srv = SEEntityServer()
    srv.make_wsgi()
    print("TODO: use uvicorn framework directly")
