from __future__ import print_function

from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

from bytesprod import BytesProducer

agent = Agent(reactor)
body = BytesProducer(b"twisted, matrix")
d = agent.request(
    b'POST',
    b'http://examplewebsite.com/post',
    Headers({'ZERO-MQ': ['Client side twisted'],
             'Content-Type': ['text/x-greeting']}),
    body)

def cbResponse(ignored):
    print('Response received')
d.addCallback(cbResponse)

def cbShutdown(ignored):
    reactor.stop()
d.addBoth(cbShutdown)

reactor.run()