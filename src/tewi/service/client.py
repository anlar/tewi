from typing import TypedDict

from transmission_rpc import Client as TransmissionClient


class ClientMeta(TypedDict):
    name: str
    version: str


class Client:

    def __init__(self,
                 host: str, port: str,
                 username: str = None, password: str = None):

        self.client = TransmissionClient(host=host,
                                         port=port,
                                         username=username,
                                         password=password)

    def meta(self) -> ClientMeta:
        return {
                'name': 'Transmission',
                'version': self.client.get_session().version
        }
