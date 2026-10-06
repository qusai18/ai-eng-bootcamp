from knowledge.engines.a_hyperextract import HyperExtract
from knowledge.engines.b_hypergraphrag import HyperGraphRag
from knowledge.engines.c_hyperbase import Hyperbase

ENGINES = {
    "a": HyperExtract(),
    "b": HyperGraphRag(),
    "c": Hyperbase(),
}
