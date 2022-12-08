from ariadne import gql

with open("schemas/syseng.graphql") as f:
    schema_text = f.read()

schema_or_error = gql(schema_text)
print("ariadne checked schema without error.")
