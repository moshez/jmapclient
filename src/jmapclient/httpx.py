from . import api

def do_request(client, request):
    response = client.request(request.url, request.method, content=request.body)
    response.raise_for_status()
    return request.parse_results(response.content)

def get_jmap_client(client, base_url):
    response = client.get(base_url + "/.well-known/jmap")
    response.raise_for_status()
    return api.JMapClient.from_well_known(response.content)
