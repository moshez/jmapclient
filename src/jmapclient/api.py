from __future__ import annotations

import attrs
import collections
import enum
import json
import uuid

@enum.unique
class _JMAPMethod(enum.Enum):
    set = enum.auto()
    get = enum.auto()
    query = enum.auto()

@enum.unique
class _JMAPMailKind(enum.Enum):
    
    mailbox = enum.auto()
    email = enum.auto()
    thread = enum.auto()
    
    def account_type(self):
        return "urn:ietf:params:jmap:mail"

@attrs.frozen
class JMapClient:
    _api_url: str
    _accounts: Mapping[str, str]
    
    @classmethod
    def from_well_known(cls, well_known_response):
        details = json.loads(well_known_response)
        accounts = details["primaryAccounts"]
        api_url = details["apiUrl"]
        return cls(api_url=api_url, accounts=accounts)

    @property
    def mail(self):
        return _JMapSpecificClient(self._build_query, _JMAPMailKind)
    
    def _build_query(self, kind, method):
        def builder(**kwargs):
            kwargs["accountId"] = self._accounts[kind.account_type()]
            result = _Query(
            full_method=f"{kind.name.capitalize()}/{method.name}",
                params=kwargs,
                query_id=str(uuid.uuid4()),
            )
            return result
        return builder
    
    def make_request(*queries):
        dependent_queries = collections.deque(queries)
        method_calls = []
        while len(dependent_queries) > 0:
            current_query = dependent_queries.popleft()
            params = current_query.get_params(dependent_queries)
            method_calls.append([current_query.full_method, params, current_query.query_id])
        method_calls.reverse()
        post_data = dict(
            using=[ "urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
            method_calls=method_calls,
        )
        body = json.dumps(post_data)
        def parse_results(body):
            details = json.loads(body)
            results = {
                key: contents
                for name, contents, key
                in details["methodResponses"]
            }
            return [result[query.query_id] for query in queries]

        return Request(
            url=self._api_url,
            method="POST",
            body=body,
            parse_results=parse_results,
        )



@attrs.frozen
class _JMapSpecificClient:
    _build_query: Any
    _kind_cls: Any
    
    def __getattr__(self, name):
        kind = getattr(self._kind_cls, name)
        return _KindQuery(self._build_query, kind)

@attrs.frozen
class _KindQuery:
    _build_query: Any
    _kind: Any

    def __getattr__(self, name):
        method = getattr(_JMAPMethod, name)
        return self._build_query(self._kind, method)

@attrs.frozen
class _QueryPath:
    query: Query
    path: str
    
@attrs.frozen
class _Query:
    full_method: str
    query_id: str
    _params: Mapping[str,Any]
    
    def __truediv__(self, name):
        return _QueryPath(self, "/" + name)
    
    def get_params(self, dependent_queries):
        params = self._params.copy()
        for key, value in self._params.items():
            if not isinstance(value, _QueryPath):
                continue
            params.pop(key)
            query = value.query
            dependent_queries.insert(0, query)
            params["#" + key] = dict(resultOf=query.query_id, name=query.full_method, path=value.path)
        return params
